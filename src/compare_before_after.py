#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import random
import re
import statistics
import sys
import time
import urllib.error
import urllib.request
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


SCORE_KEYS = [
    "diagnostic_essence",
    "faithfulness",
    "prognostic_staging_capture",
    "reasoning_quality",
    "conclusion_quality",
    "overall_usefulness",
    "reasoning_prognostic_feature_score",
    "conclusion_prognostic_feature_score",
    "reasoning_faithfulness_score",
    "conclusion_faithfulness_score",
]

ID_KEY_CANDIDATES = [
    "report_id",
    "case_id",
    "case_submitter_id",
    "submitter_id",
    "patient_id",
    "sample_id",
    "id",
]

TEXT_KEY_CANDIDATES = [
    "text",
    "output",
    "generation",
    "generated_text",
    "response",
    "completion",
    "summary",
    "answer",
]

ORIGINAL_TEXT_KEY = "ocr_text"

ORIGINAL_KEYWORDS = [
    "final diagnosis",
    "diagnosis",
    "synoptic",
    "tumor",
    "carcinoma",
    "sarcoma",
    "melanoma",
    "lymph node",
    "lymphovascular",
    "margin",
    "metast",
    "invasion",
    "grade",
    "stage",
    "pt",
    "pn",
    "pm",
    "specimen",
    "pathologic",
    "cytology",
]


@dataclass
class LoadedTexts:
    source_name: str
    texts: dict[str, str] = field(default_factory=dict)
    total_records: int = 0
    parsed_files: list[str] = field(default_factory=list)
    duplicate_counts: Counter[str] = field(default_factory=Counter)
    empty_text_ids: set[str] = field(default_factory=set)
    id_key_counts: Counter[str] = field(default_factory=Counter)
    text_key_counts: Counter[str] = field(default_factory=Counter)
    warnings: list[str] = field(default_factory=list)

    @property
    def unique_count(self) -> int:
        return len(self.texts)

    @property
    def duplicate_ids(self) -> list[str]:
        return sorted([report_id for report_id, count in self.duplicate_counts.items() if count > 1])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Align before/after model generations with OCR reports and optionally judge them."
    )
    parser.add_argument("--generated-dir", default="generated_token_original_prompt")
    parser.add_argument("--original-dir", default="original_reports")
    parser.add_argument("--out-dir", default="model_comparison_500")
    parser.add_argument("--n", type=int, default=500)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--judge-model", default=os.getenv("JUDGE_MODEL", "gpt-4.1"))
    parser.add_argument(
        "--judge-mode",
        choices=["auto", "local", "openai", "none"],
        default="auto",
        help="auto uses local judging unless OPENAI_API_KEY is set; local uses deterministic in-process scoring.",
    )
    parser.add_argument("--max-original-chars", type=int, default=16000)
    parser.add_argument("--max-output-chars", type=int, default=6000)
    return parser.parse_args()


def resolve_generated_dir(requested_dir: Path) -> tuple[Path, list[str]]:
    warnings: list[str] = []
    if requested_dir.exists():
        return requested_dir, warnings

    typo_fallback = requested_dir.parent / "genrated_token_original_prompt"
    if requested_dir.name == "generated_token_original_prompt" and typo_fallback.exists():
        warnings.append(
            f"Requested generated directory {requested_dir} was not found; "
            f"using existing typo-named directory {typo_fallback}."
        )
        return typo_fallback, warnings

    return requested_dir, warnings


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def parse_json_line(line: str, path: Path, line_number: int, warnings: list[str]) -> dict[str, Any] | None:
    try:
        parsed = json.loads(line)
    except json.JSONDecodeError as error:
        warnings.append(f"{path}:{line_number}: invalid JSON skipped ({error}).")
        return None
    if not isinstance(parsed, dict):
        warnings.append(f"{path}:{line_number}: non-object JSONL record skipped.")
        return None
    return parsed


def get_case_insensitive(record: dict[str, Any], candidates: list[str]) -> tuple[str | None, Any]:
    lower_to_actual = {str(key).lower(): key for key in record.keys()}
    for candidate in candidates:
        actual_key = lower_to_actual.get(candidate.lower())
        if actual_key is not None:
            return str(actual_key), record[actual_key]
    return None, None


def stringify_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        string_items = [item.strip() for item in value if isinstance(item, str) and item.strip()]
        if string_items:
            return "\n".join(string_items)
    if isinstance(value, dict):
        nested_key, nested_value = get_case_insensitive(value, TEXT_KEY_CANDIDATES)
        if nested_key is not None:
            return stringify_text(nested_value)
    return str(value).strip()


def choose_longest_non_empty(existing_text: str | None, candidate_text: str) -> str:
    if existing_text is None:
        return candidate_text
    if candidate_text and not existing_text:
        return candidate_text
    if candidate_text and len(candidate_text) > len(existing_text):
        return candidate_text
    return existing_text


def detect_generated_fields(record: dict[str, Any]) -> tuple[str | None, str | None, Any, Any]:
    id_key, report_id_value = get_case_insensitive(record, ID_KEY_CANDIDATES)
    text_key, text_value = get_case_insensitive(record, TEXT_KEY_CANDIDATES)

    if text_key is None:
        string_fields = [
            (str(key), value)
            for key, value in record.items()
            if isinstance(value, str) and str(key) != id_key
        ]
        if string_fields:
            text_key, text_value = max(string_fields, key=lambda item: len(item[1] or ""))

    return id_key, text_key, report_id_value, text_value


def load_generated_outputs(generated_dir: Path, label: str) -> LoadedTexts:
    loaded = LoadedTexts(source_name=label)
    jsonl_paths = sorted(generated_dir.glob(f"*{label}*.jsonl"))
    if not jsonl_paths:
        loaded.warnings.append(f"No *{label}*.jsonl files found in {generated_dir}.")
        return loaded

    seen_ids: Counter[str] = Counter()
    for jsonl_path in jsonl_paths:
        loaded.parsed_files.append(str(jsonl_path))
        with jsonl_path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                record = parse_json_line(line, jsonl_path, line_number, loaded.warnings)
                if record is None:
                    continue

                id_key, text_key, report_id_value, text_value = detect_generated_fields(record)
                if id_key is None or text_key is None:
                    loaded.warnings.append(
                        f"{jsonl_path}:{line_number}: could not detect report ID/text keys; skipped."
                    )
                    continue

                report_id = stringify_text(report_id_value)
                generated_text = stringify_text(text_value)
                if not report_id:
                    loaded.warnings.append(f"{jsonl_path}:{line_number}: empty report ID skipped.")
                    continue

                loaded.total_records += 1
                loaded.id_key_counts[id_key] += 1
                loaded.text_key_counts[text_key] += 1
                seen_ids[report_id] += 1
                if not generated_text:
                    loaded.empty_text_ids.add(report_id)
                loaded.texts[report_id] = choose_longest_non_empty(
                    loaded.texts.get(report_id), generated_text
                )

    loaded.duplicate_counts = seen_ids
    return loaded


def iter_original_records(parsed_json: Any, path: Path, warnings: list[str]) -> list[tuple[str, str]]:
    records: list[tuple[str, str]] = []
    if isinstance(parsed_json, dict):
        if ORIGINAL_TEXT_KEY in parsed_json:
            id_key, report_id_value = get_case_insensitive(parsed_json, ID_KEY_CANDIDATES)
            if id_key is not None:
                records.append((stringify_text(report_id_value), stringify_text(parsed_json[ORIGINAL_TEXT_KEY])))
            else:
                warnings.append(f"{path}: top-level ocr_text exists but no ID key was detected.")
            return records

        for report_id_value, report_payload in parsed_json.items():
            if isinstance(report_payload, dict) and ORIGINAL_TEXT_KEY in report_payload:
                records.append((stringify_text(report_id_value), stringify_text(report_payload[ORIGINAL_TEXT_KEY])))
            elif isinstance(report_payload, str) and ORIGINAL_TEXT_KEY.lower() in str(report_id_value).lower():
                warnings.append(f"{path}: found string under {report_id_value}, but no report ID was available.")
        return records

    if isinstance(parsed_json, list):
        for record_index, record in enumerate(parsed_json, start=1):
            if not isinstance(record, dict) or ORIGINAL_TEXT_KEY not in record:
                continue
            id_key, report_id_value = get_case_insensitive(record, ID_KEY_CANDIDATES)
            if id_key is None:
                warnings.append(f"{path}: list record {record_index} has ocr_text but no ID key.")
                continue
            records.append((stringify_text(report_id_value), stringify_text(record[ORIGINAL_TEXT_KEY])))
        return records

    warnings.append(f"{path}: unsupported original JSON top-level type {type(parsed_json).__name__}.")
    return records


def load_original_reports(original_dir: Path) -> LoadedTexts:
    loaded = LoadedTexts(source_name="original")
    json_paths = sorted(original_dir.glob("*.json"))
    if not json_paths:
        loaded.warnings.append(f"No .json files found in {original_dir}.")
        return loaded

    seen_ids: Counter[str] = Counter()
    for json_path in json_paths:
        loaded.parsed_files.append(str(json_path))
        try:
            parsed_json = read_json(json_path)
        except json.JSONDecodeError as error:
            loaded.warnings.append(f"{json_path}: invalid JSON skipped ({error}).")
            continue

        for report_id, original_text in iter_original_records(parsed_json, json_path, loaded.warnings):
            if not report_id:
                loaded.warnings.append(f"{json_path}: empty original report ID skipped.")
                continue
            loaded.total_records += 1
            loaded.id_key_counts["top_level_report_id"] += 1
            loaded.text_key_counts[ORIGINAL_TEXT_KEY] += 1
            seen_ids[report_id] += 1
            if not original_text:
                loaded.empty_text_ids.add(report_id)
            loaded.texts[report_id] = choose_longest_non_empty(loaded.texts.get(report_id), original_text)

    loaded.duplicate_counts = seen_ids
    return loaded


def stable_position_assignment(report_id: str, seed: int) -> dict[str, str]:
    digest = hashlib.sha256(f"{seed}:{report_id}".encode("utf-8")).hexdigest()
    position_rng = random.Random(int(digest[:16], 16))
    before_is_model_x = position_rng.choice([True, False])
    if before_is_model_x:
        return {"model_x": "before", "model_y": "after"}
    return {"model_x": "after", "model_y": "before"}


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def build_alignment(
    before: LoadedTexts,
    after: LoadedTexts,
    original: LoadedTexts,
    sample_size: int,
    seed: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    before_ids = set(before.texts)
    after_ids = set(after.texts)
    original_ids = set(original.texts)
    union_ids = before_ids | after_ids | original_ids
    matched_present_ids = before_ids & after_ids & original_ids

    empty_before_matched = {report_id for report_id in matched_present_ids if not before.texts[report_id]}
    empty_after_matched = {report_id for report_id in matched_present_ids if not after.texts[report_id]}
    empty_original_matched = {report_id for report_id in matched_present_ids if not original.texts[report_id]}
    usable_ids = sorted(
        report_id
        for report_id in matched_present_ids
        if before.texts[report_id] and after.texts[report_id] and original.texts[report_id]
    )

    sample_rng = random.Random(seed)
    if len(usable_ids) <= sample_size:
        sampled_ids = usable_ids
    else:
        sampled_ids = sample_rng.sample(usable_ids, sample_size)

    aligned_rows = [
        {
            "report_id": report_id,
            "original_ocr_text": original.texts[report_id],
            "before_text": before.texts[report_id],
            "after_text": after.texts[report_id],
        }
        for report_id in sampled_ids
    ]

    diagnostics = {
        "union_ids": len(union_ids),
        "matched_present_ids": len(matched_present_ids),
        "usable_matched_ids": len(usable_ids),
        "sampled_ids": len(sampled_ids),
        "sample_size_requested": sample_size,
        "missing_before": sorted(union_ids - before_ids),
        "missing_after": sorted(union_ids - after_ids),
        "missing_original": sorted(union_ids - original_ids),
        "before_after_missing_original": sorted((before_ids & after_ids) - original_ids),
        "before_original_missing_after": sorted((before_ids & original_ids) - after_ids),
        "after_original_missing_before": sorted((after_ids & original_ids) - before_ids),
        "empty_before_matched": sorted(empty_before_matched),
        "empty_after_matched": sorted(empty_after_matched),
        "empty_original_matched": sorted(empty_original_matched),
    }
    return aligned_rows, diagnostics


def find_keyword_windows(text: str, max_chars: int) -> list[str]:
    lower_text = text.lower()
    windows: list[tuple[int, int]] = []
    window_radius = 900
    for keyword in ORIGINAL_KEYWORDS:
        search_start = 0
        while True:
            keyword_index = lower_text.find(keyword, search_start)
            if keyword_index < 0:
                break
            window_start = max(0, keyword_index - window_radius)
            window_end = min(len(text), keyword_index + len(keyword) + window_radius)
            if all(window_end < existing_start or window_start > existing_end for existing_start, existing_end in windows):
                windows.append((window_start, window_end))
            search_start = keyword_index + len(keyword)
            if len(windows) >= 8:
                break
        if len(windows) >= 8:
            break

    snippets: list[str] = []
    used_chars = 0
    for window_start, window_end in sorted(windows):
        snippet = text[window_start:window_end].strip()
        if not snippet:
            continue
        if used_chars + len(snippet) > max_chars:
            remaining_chars = max_chars - used_chars
            if remaining_chars > 200:
                snippets.append(snippet[:remaining_chars].strip())
            break
        snippets.append(snippet)
        used_chars += len(snippet)
    return snippets


def smart_truncate_original(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    if max_chars < 1000:
        return text[:max_chars]

    head_chars = int(max_chars * 0.42)
    tail_chars = int(max_chars * 0.20)
    remaining_chars = max_chars - head_chars - tail_chars - 300
    head_text = text[:head_chars].strip()
    tail_text = text[-tail_chars:].strip()
    keyword_snippets = find_keyword_windows(text[head_chars:-tail_chars], max(0, remaining_chars))

    parts = [head_text]
    if keyword_snippets:
        parts.append("\n\n[...middle sections selected around diagnosis/synoptic/staging keywords...]\n\n")
        parts.extend(keyword_snippets)
    else:
        parts.append("\n\n[...middle content truncated...]\n\n")
    parts.append("\n\n[...tail preserved...]\n\n")
    parts.append(tail_text)
    truncated = "".join(parts)
    if len(truncated) > max_chars:
        return truncated[: max_chars - 80] + "\n\n[...truncated to prompt budget...]"
    return truncated


def middle_truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    if max_chars < 500:
        return text[:max_chars]
    head_chars = int(max_chars * 0.62)
    tail_chars = max_chars - head_chars - 120
    return (
        text[:head_chars].strip()
        + "\n\n[...middle content truncated for judge prompt...]\n\n"
        + text[-tail_chars:].strip()
    )


def parse_sections(text: str) -> dict[str, Any]:
    stripped_text = text.strip()
    reasoning_match = re.search(r"<reasoning>(.*?)</reasoning>", stripped_text, flags=re.IGNORECASE | re.DOTALL)
    conclusion_match = re.search(
        r"<final_conclusion>(.*?)</final_conclusion>|<conclusion>(.*?)</conclusion>",
        stripped_text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if reasoning_match or conclusion_match:
        conclusion_text = ""
        if conclusion_match:
            conclusion_text = next(group for group in conclusion_match.groups() if group is not None).strip()
        return {
            "method": "xml_tags",
            "reasoning_found": reasoning_match is not None,
            "conclusion_found": conclusion_match is not None,
            "reasoning_text": reasoning_match.group(1).strip() if reasoning_match else stripped_text,
            "conclusion_text": conclusion_text if conclusion_text else stripped_text,
        }

    reasoning_match = re.search(
        r"\breasoning\s*:\s*(.*?)(?=\b(?:final\s+)?conclusion\s*:|$)",
        stripped_text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    conclusion_match = re.search(
        r"\b(?:final\s+)?conclusion\s*:\s*(.*)$",
        stripped_text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if reasoning_match or conclusion_match:
        return {
            "method": "plain_labels",
            "reasoning_found": reasoning_match is not None,
            "conclusion_found": conclusion_match is not None,
            "reasoning_text": reasoning_match.group(1).strip() if reasoning_match else stripped_text,
            "conclusion_text": conclusion_match.group(1).strip() if conclusion_match else stripped_text,
        }

    return {
        "method": "whole_text_fallback",
        "reasoning_found": False,
        "conclusion_found": False,
        "reasoning_text": stripped_text,
        "conclusion_text": stripped_text,
    }


def build_judge_prompt(
    aligned_row: dict[str, Any],
    position_map: dict[str, str],
    max_original_chars: int,
    max_output_chars: int,
) -> tuple[str, dict[str, Any]]:
    before_sections = parse_sections(aligned_row["before_text"])
    after_sections = parse_sections(aligned_row["after_text"])
    section_map = {"before": before_sections, "after": after_sections}

    model_x_label = position_map["model_x"]
    model_y_label = position_map["model_y"]
    model_x_output = aligned_row[f"{model_x_label}_text"]
    model_y_output = aligned_row[f"{model_y_label}_text"]

    original_for_prompt = smart_truncate_original(aligned_row["original_ocr_text"], max_original_chars)
    model_x_for_prompt = middle_truncate(model_x_output, max_output_chars)
    model_y_for_prompt = middle_truncate(model_y_output, max_output_chars)

    model_x_sections = section_map[model_x_label]
    model_y_sections = section_map[model_y_label]

    prompt = f"""You are evaluating two LLM-generated pathology report summaries against the original OCR pathology report.

You must decide which model better captures the diagnostic essence of the original report and which model reasons better.

Original OCR report:
<<<ORIGINAL_REPORT>>>
{original_for_prompt}
<<<END_ORIGINAL_REPORT>>>

Model X output:
<<<MODEL_X_OUTPUT>>>
{model_x_for_prompt}
<<<END_MODEL_X_OUTPUT>>>

Model Y output:
<<<MODEL_Y_OUTPUT>>>
{model_y_for_prompt}
<<<END_MODEL_Y_OUTPUT>>>

Detected section parsing metadata:
- Model X explicit reasoning found: {model_x_sections["reasoning_found"]}; explicit conclusion found: {model_x_sections["conclusion_found"]}; method: {model_x_sections["method"]}.
- Model Y explicit reasoning found: {model_y_sections["reasoning_found"]}; explicit conclusion found: {model_y_sections["conclusion_found"]}; method: {model_y_sections["method"]}.
- If explicit sections are not available, treat the whole text as both the available reasoning context and conclusion context.

Important:
- Judge only using the original report as ground truth.
- Do not reward unsupported clinical speculation.
- Penalize hallucinated biomarkers, treatments, stages, clinical history, patient age, or findings not present in the report.
- Reward correct capture of diagnosis, tumor site, histology, grade, invasion, lymphovascular invasion, margins, lymph nodes, metastases/positive sites, cytology, pTNM stage, and important incidental findings.
- If the original OCR is noisy, focus on clearly supported pathology facts.
- If one model is more complete but has a small OCR artifact, penalize it mildly.
- If one model is concise but misses major staging/prognostic facts, penalize it for incompleteness.

Return strict JSON only with this schema:

{{
  "model_x_scores": {{
    "diagnostic_essence": 0,
    "faithfulness": 0,
    "prognostic_staging_capture": 0,
    "reasoning_quality": 0,
    "conclusion_quality": 0,
    "overall_usefulness": 0,
    "reasoning_prognostic_feature_score": 0,
    "conclusion_prognostic_feature_score": 0,
    "reasoning_faithfulness_score": 0,
    "conclusion_faithfulness_score": 0
  }},
  "model_y_scores": {{
    "diagnostic_essence": 0,
    "faithfulness": 0,
    "prognostic_staging_capture": 0,
    "reasoning_quality": 0,
    "conclusion_quality": 0,
    "overall_usefulness": 0,
    "reasoning_prognostic_feature_score": 0,
    "conclusion_prognostic_feature_score": 0,
    "reasoning_faithfulness_score": 0,
    "conclusion_faithfulness_score": 0
  }},
  "winner": "model_x/model_y/tie",
  "confidence": 1,
  "key_original_facts": [],
  "model_x_major_omissions": [],
  "model_y_major_omissions": [],
  "model_x_hallucinations": [],
  "model_y_hallucinations": [],
  "short_reason": ""
}}
"""
    section_status = {
        "before": {
            "method": before_sections["method"],
            "reasoning_found": before_sections["reasoning_found"],
            "conclusion_found": before_sections["conclusion_found"],
        },
        "after": {
            "method": after_sections["method"],
            "reasoning_found": after_sections["reasoning_found"],
            "conclusion_found": after_sections["conclusion_found"],
        },
    }
    return prompt, section_status


def call_openai_chat(prompt: str, judge_model: str) -> str:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")

    base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    payload = {
        "model": judge_model,
        "messages": [
            {
                "role": "system",
                "content": "You are a meticulous pathology report evaluator. Return strict JSON only.",
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0,
        "response_format": {"type": "json_object"},
    }
    request = urllib.request.Request(
        f"{base_url}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=180) as response:
        response_payload = json.loads(response.read().decode("utf-8"))
    return response_payload["choices"][0]["message"]["content"]


def extract_json_object(response_text: str) -> dict[str, Any]:
    cleaned = response_text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        object_match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
        if not object_match:
            raise
        parsed = json.loads(object_match.group(0))
    if not isinstance(parsed, dict):
        raise ValueError("Judge response JSON was not an object")
    return parsed


def normalize_score(value: Any, key: str) -> float:
    if isinstance(value, str):
        value = value.strip()
        if not value:
            raise ValueError(f"Score {key} was empty")
        value = float(value)
    if not isinstance(value, (int, float)):
        raise ValueError(f"Score {key} was not numeric")
    score = float(value)
    if score < 0 or score > 5:
        raise ValueError(f"Score {key}={score} outside 0-5")
    return score


def normalize_winner(value: Any) -> str:
    normalized = str(value).strip().lower().replace(" ", "_")
    aliases = {
        "x": "model_x",
        "modelx": "model_x",
        "model_x": "model_x",
        "model-x": "model_x",
        "y": "model_y",
        "modely": "model_y",
        "model_y": "model_y",
        "model-y": "model_y",
        "tie": "tie",
        "draw": "tie",
        "equal": "tie",
    }
    if normalized in aliases:
        return aliases[normalized]
    raise ValueError(f"Invalid winner {value!r}")


def normalize_string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [stringify_text(item) for item in value if stringify_text(item)]
    if isinstance(value, str):
        if not value.strip():
            return []
        return [value.strip()]
    return [stringify_text(value)]


def validate_judge_result(result: dict[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for score_group in ["model_x_scores", "model_y_scores"]:
        scores = result.get(score_group)
        if not isinstance(scores, dict):
            raise ValueError(f"Missing {score_group}")
        normalized_scores: dict[str, float] = {}
        for score_key in SCORE_KEYS:
            if score_key not in scores:
                raise ValueError(f"Missing score {score_group}.{score_key}")
            normalized_scores[score_key] = normalize_score(scores[score_key], f"{score_group}.{score_key}")
        normalized[score_group] = normalized_scores

    normalized["winner"] = normalize_winner(result.get("winner"))
    confidence = normalize_score(result.get("confidence"), "confidence")
    if confidence < 1 or confidence > 5:
        raise ValueError("Confidence outside 1-5")
    normalized["confidence"] = int(round(confidence))
    normalized["key_original_facts"] = normalize_string_list(result.get("key_original_facts"))
    normalized["model_x_major_omissions"] = normalize_string_list(result.get("model_x_major_omissions"))
    normalized["model_y_major_omissions"] = normalize_string_list(result.get("model_y_major_omissions"))
    normalized["model_x_hallucinations"] = normalize_string_list(result.get("model_x_hallucinations"))
    normalized["model_y_hallucinations"] = normalize_string_list(result.get("model_y_hallucinations"))
    normalized["short_reason"] = stringify_text(result.get("short_reason"))
    return normalized


def judge_one_report(
    aligned_row: dict[str, Any],
    seed: int,
    judge_model: str,
    max_original_chars: int,
    max_output_chars: int,
) -> dict[str, Any]:
    position_map = stable_position_assignment(aligned_row["report_id"], seed)
    prompt, section_status = build_judge_prompt(
        aligned_row,
        position_map,
        max_original_chars=max_original_chars,
        max_output_chars=max_output_chars,
    )

    last_error: Exception | None = None
    for attempt_number in range(1, 4):
        attempt_prompt = prompt
        if attempt_number > 1:
            attempt_prompt = (
                "Your previous response was invalid. Return one valid JSON object only, "
                "with all numeric scores in 0-5 and winner exactly model_x, model_y, or tie.\n\n"
                + prompt
            )
        try:
            response_text = call_openai_chat(attempt_prompt, judge_model)
            parsed = extract_json_object(response_text)
            normalized = validate_judge_result(parsed)
            model_x_label = position_map["model_x"]
            model_y_label = position_map["model_y"]

            before_scores = (
                normalized["model_x_scores"] if model_x_label == "before" else normalized["model_y_scores"]
            )
            after_scores = (
                normalized["model_x_scores"] if model_x_label == "after" else normalized["model_y_scores"]
            )
            if normalized["winner"] == "tie":
                winner = "tie"
            elif normalized["winner"] == "model_x":
                winner = model_x_label
            else:
                winner = model_y_label

            before_model_key = "model_x" if model_x_label == "before" else "model_y"
            after_model_key = "model_x" if model_x_label == "after" else "model_y"
            return {
                "report_id": aligned_row["report_id"],
                "judge_model": judge_model,
                "position_map": position_map,
                "section_parsing": section_status,
                "before_scores": before_scores,
                "after_scores": after_scores,
                "winner": winner,
                "confidence": normalized["confidence"],
                "reason": normalized["short_reason"],
                "before_major_omissions": normalized[f"{before_model_key}_major_omissions"],
                "after_major_omissions": normalized[f"{after_model_key}_major_omissions"],
                "before_hallucinations": normalized[f"{before_model_key}_hallucinations"],
                "after_hallucinations": normalized[f"{after_model_key}_hallucinations"],
                "key_original_facts": normalized["key_original_facts"],
            }
        except (ValueError, json.JSONDecodeError, urllib.error.URLError, RuntimeError) as error:
            last_error = error
            if attempt_number < 3:
                time.sleep(1.5 * attempt_number)
                continue
            raise RuntimeError(f"Judge failed after 3 attempts: {last_error}") from last_error

    raise RuntimeError("Judge failed unexpectedly")


def load_existing_judgments(path: Path) -> tuple[set[str], list[dict[str, Any]]]:
    judged_ids: set[str] = set()
    judgments: list[dict[str, Any]] = []
    if not path.exists():
        return judged_ids, judgments
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                judgment = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(judgment, dict) and judgment.get("winner") in {"before", "after", "tie"}:
                report_id = stringify_text(judgment.get("report_id"))
                if report_id:
                    judged_ids.add(report_id)
                    judgments.append(judgment)
    return judged_ids, judgments


def run_judging(
    aligned_rows: list[dict[str, Any]],
    out_dir: Path,
    seed: int,
    judge_model: str,
    max_original_chars: int,
    max_output_chars: int,
) -> tuple[list[dict[str, Any]], str | None]:
    judgments_path = out_dir / "judgments.jsonl"
    judged_ids, existing_judgments = load_existing_judgments(judgments_path)
    api_key_available = bool(os.getenv("OPENAI_API_KEY"))
    if not api_key_available:
        judgments_path.touch(exist_ok=True)
        return existing_judgments, "OPENAI_API_KEY is not set; automatic LLM judging was not run."

    with judgments_path.open("a", encoding="utf-8") as handle:
        for aligned_row in aligned_rows:
            report_id = aligned_row["report_id"]
            if report_id in judged_ids:
                continue
            try:
                judgment = judge_one_report(
                    aligned_row,
                    seed=seed,
                    judge_model=judge_model,
                    max_original_chars=max_original_chars,
                    max_output_chars=max_output_chars,
                )
                handle.write(json.dumps(judgment, ensure_ascii=False) + "\n")
                handle.flush()
                judged_ids.add(report_id)
                existing_judgments.append(judgment)
            except RuntimeError as error:
                failure = {
                    "report_id": report_id,
                    "judge_model": judge_model,
                    "error": str(error),
                    "winner": "judge_failed",
                }
                handle.write(json.dumps(failure, ensure_ascii=False) + "\n")
                handle.flush()
                return existing_judgments, f"Judging stopped at {report_id}: {error}"
    return existing_judgments, None


def numeric_values(judgments: list[dict[str, Any]], model_key: str, score_key: str) -> list[float]:
    values: list[float] = []
    score_group = f"{model_key}_scores"
    for judgment in judgments:
        scores = judgment.get(score_group)
        if isinstance(scores, dict) and score_key in scores:
            values.append(float(scores[score_key]))
    return values


def format_float(value: float | None) -> str:
    if value is None:
        return ""
    return f"{value:.4f}"


def write_aggregate_scores(out_dir: Path, judgments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for score_key in SCORE_KEYS:
        before_values = numeric_values(judgments, "before", score_key)
        after_values = numeric_values(judgments, "after", score_key)
        if before_values and after_values:
            before_mean = statistics.mean(before_values)
            after_mean = statistics.mean(after_values)
            row = {
                "criterion": score_key,
                "before_mean": before_mean,
                "before_median": statistics.median(before_values),
                "after_mean": after_mean,
                "after_median": statistics.median(after_values),
                "mean_diff_after_minus_before": after_mean - before_mean,
                "n_judged": min(len(before_values), len(after_values)),
            }
        else:
            row = {
                "criterion": score_key,
                "before_mean": None,
                "before_median": None,
                "after_mean": None,
                "after_median": None,
                "mean_diff_after_minus_before": None,
                "n_judged": 0,
            }
        rows.append(row)

    aggregate_path = out_dir / "aggregate_scores.csv"
    with aggregate_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "criterion",
                "before_mean",
                "before_median",
                "after_mean",
                "after_median",
                "mean_diff_after_minus_before",
                "n_judged",
            ],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "criterion": row["criterion"],
                    "before_mean": format_float(row["before_mean"]),
                    "before_median": format_float(row["before_median"]),
                    "after_mean": format_float(row["after_mean"]),
                    "after_median": format_float(row["after_median"]),
                    "mean_diff_after_minus_before": format_float(row["mean_diff_after_minus_before"]),
                    "n_judged": row["n_judged"],
                }
            )
    return rows


def write_win_rates(out_dir: Path, judgments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    winner_counts = Counter(judgment.get("winner") for judgment in judgments)
    total_judgments = sum(winner_counts[winner] for winner in ["before", "after", "tie"])
    rows: list[dict[str, Any]] = []
    for winner in ["before", "after", "tie"]:
        count = winner_counts[winner]
        percentage = (count / total_judgments * 100) if total_judgments else 0.0
        rows.append({"winner": winner, "count": count, "percentage": percentage})

    win_rates_path = out_dir / "win_rates.csv"
    with win_rates_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["winner", "count", "percentage"])
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "winner": row["winner"],
                    "count": row["count"],
                    "percentage": format_float(row["percentage"]),
                }
            )
    return rows


def normalized_counter_items(judgments: list[dict[str, Any]], key: str, limit: int = 10) -> list[tuple[str, int]]:
    counter: Counter[str] = Counter()
    for judgment in judgments:
        values = judgment.get(key, [])
        if not isinstance(values, list):
            continue
        for value in values:
            normalized = re.sub(r"\s+", " ", stringify_text(value).lower()).strip(" .;:")
            if normalized:
                counter[normalized] += 1
    return counter.most_common(limit)


def representative_cases(judgments: list[dict[str, Any]], winner: str, limit: int = 5) -> list[dict[str, Any]]:
    candidates = [judgment for judgment in judgments if judgment.get("winner") == winner]
    return sorted(candidates, key=lambda item: item.get("confidence", 0), reverse=True)[:limit]


def close_cases(judgments: list[dict[str, Any]], limit: int = 5) -> list[dict[str, Any]]:
    ties = [judgment for judgment in judgments if judgment.get("winner") == "tie"]
    if len(ties) >= limit:
        return sorted(ties, key=lambda item: item.get("confidence", 0), reverse=True)[:limit]

    scored_cases: list[tuple[float, dict[str, Any]]] = []
    for judgment in judgments:
        before_scores = judgment.get("before_scores", {})
        after_scores = judgment.get("after_scores", {})
        if not isinstance(before_scores, dict) or not isinstance(after_scores, dict):
            continue
        before_total = sum(float(before_scores.get(score_key, 0)) for score_key in SCORE_KEYS)
        after_total = sum(float(after_scores.get(score_key, 0)) for score_key in SCORE_KEYS)
        scored_cases.append((abs(after_total - before_total), judgment))

    close_sorted = [judgment for _, judgment in sorted(scored_cases, key=lambda item: item[0])]
    return (ties + [judgment for judgment in close_sorted if judgment not in ties])[:limit]


def markdown_list(items: list[tuple[str, int]]) -> str:
    if not items:
        return "- Not available.\n"
    return "".join(f"- {item} ({count})\n" for item, count in items)


def markdown_cases(cases: list[dict[str, Any]]) -> str:
    if not cases:
        return "- Not available.\n"
    lines: list[str] = []
    for case in cases:
        lines.append(
            f"- `{case.get('report_id')}` (confidence {case.get('confidence')}): "
            f"{case.get('reason', '')}\n"
        )
    return "".join(lines)


def best_model_for_score(aggregate_rows: list[dict[str, Any]], score_key: str) -> str:
    row = next((candidate for candidate in aggregate_rows if candidate["criterion"] == score_key), None)
    if not row or row["before_mean"] is None or row["after_mean"] is None:
        return "Not available"
    if row["after_mean"] > row["before_mean"]:
        return "after"
    if row["before_mean"] > row["after_mean"]:
        return "before"
    return "tie"


def write_summary_report(
    out_dir: Path,
    before: LoadedTexts,
    after: LoadedTexts,
    original: LoadedTexts,
    alignment_diagnostics: dict[str, Any],
    aggregate_rows: list[dict[str, Any]],
    win_rows: list[dict[str, Any]],
    judgments: list[dict[str, Any]],
    judge_status: str | None,
) -> None:
    total_judgments = len(judgments)
    win_text = "\n".join(
        f"- {row['winner']}: {row['count']} ({format_float(row['percentage'])}%)" for row in win_rows
    )
    mean_rows = []
    for row in aggregate_rows:
        mean_rows.append(
            "| {criterion} | {before_mean} | {after_mean} | {diff} |".format(
                criterion=row["criterion"],
                before_mean=format_float(row["before_mean"]),
                after_mean=format_float(row["after_mean"]),
                diff=format_float(row["mean_diff_after_minus_before"]),
            )
        )
    if not mean_rows:
        mean_rows.append("| Not available | | | |")

    if total_judgments:
        final_interpretation = (
            "The automatic judge results above indicate whether the after model improved by criterion. "
            "Use the win-rate and mean-difference tables together: wins capture pairwise preference, "
            "while score differences show which pathology dimensions changed most."
        )
    else:
        final_interpretation = (
            "Automatic judging did not run, so no conclusion can be drawn about whether the after model "
            "genuinely improved over before. The aligned sample is ready for judging once an API key is available."
        )

    summary = f"""# Before vs After Pathology Summary Evaluation

## Run Status
- Before outputs loaded: {before.unique_count} unique IDs from {before.total_records} records.
- After outputs loaded: {after.unique_count} unique IDs from {after.total_records} records.
- Original reports loaded: {original.unique_count} unique IDs from {original.total_records} records.
- Matched IDs present in all sources: {alignment_diagnostics['matched_present_ids']}.
- Usable matched IDs with non-empty before, after, and original text: {alignment_diagnostics['usable_matched_ids']}.
- Number sampled: {alignment_diagnostics['sampled_ids']}.
- Number judged: {total_judgments}.
- Judge status: {judge_status or 'Completed.'}

## Overall Win Rate
{win_text}

## Mean Scores
| Criterion | Before Mean | After Mean | After Minus Before |
| --- | ---: | ---: | ---: |
{chr(10).join(mean_rows)}

## Dimension Winners
- Diagnostic essence: {best_model_for_score(aggregate_rows, 'diagnostic_essence')}
- Faithfulness: {best_model_for_score(aggregate_rows, 'faithfulness')}
- Prognostic/staging features: {best_model_for_score(aggregate_rows, 'prognostic_staging_capture')}
- Reasoning quality: {best_model_for_score(aggregate_rows, 'reasoning_quality')}
- Conclusion quality: {best_model_for_score(aggregate_rows, 'conclusion_quality')}

## Common Omissions For Before
{markdown_list(normalized_counter_items(judgments, 'before_major_omissions'))}
## Common Omissions For After
{markdown_list(normalized_counter_items(judgments, 'after_major_omissions'))}
## Common Hallucinations For Before
{markdown_list(normalized_counter_items(judgments, 'before_hallucinations'))}
## Common Hallucinations For After
{markdown_list(normalized_counter_items(judgments, 'after_hallucinations'))}
## Representative After Wins
{markdown_cases(representative_cases(judgments, 'after'))}
## Representative Before Wins
{markdown_cases(representative_cases(judgments, 'before'))}
## Ties Or Close Cases
{markdown_cases(close_cases(judgments))}
## Final Interpretation
{final_interpretation}
"""
    (out_dir / "summary_report.md").write_text(summary, encoding="utf-8")


def source_diagnostics_markdown(source: LoadedTexts) -> str:
    duplicate_ids = source.duplicate_ids
    duplicate_display = ", ".join(f"`{report_id}`" for report_id in duplicate_ids[:100])
    if len(duplicate_ids) > 100:
        duplicate_display += f", ... ({len(duplicate_ids) - 100} more)"
    if not duplicate_display:
        duplicate_display = "None"
    warnings_display = "\n".join(f"- {warning}" for warning in source.warnings) or "- None"
    files_display = "\n".join(f"- `{file_path}`" for file_path in source.parsed_files) or "- None"
    id_keys = ", ".join(f"`{key}` ({count})" for key, count in source.id_key_counts.items()) or "None"
    text_keys = ", ".join(f"`{key}` ({count})" for key, count in source.text_key_counts.items()) or "None"

    return f"""### {source.source_name}
- Parsed files: {len(source.parsed_files)}
- Total records loaded: {source.total_records}
- Unique IDs retained: {source.unique_count}
- Duplicate IDs: {len(duplicate_ids)}
- Duplicate ID list: {duplicate_display}
- Empty text IDs: {len(source.empty_text_ids)}
- ID keys observed: {id_keys}
- Text keys observed: {text_keys}

Files:
{files_display}

Warnings:
{warnings_display}
"""


def sample_markdown_list(values: list[str], limit: int = 30) -> str:
    if not values:
        return "None"
    display_values = values[:limit]
    rendered = ", ".join(f"`{value}`" for value in display_values)
    if len(values) > limit:
        rendered += f", ... ({len(values) - limit} more)"
    return rendered


def write_loading_diagnostics(
    out_dir: Path,
    requested_generated_dir: Path,
    resolved_generated_dir: Path,
    generated_warnings: list[str],
    original_dir: Path,
    before: LoadedTexts,
    after: LoadedTexts,
    original: LoadedTexts,
    alignment_diagnostics: dict[str, Any],
) -> None:
    generated_warning_text = "\n".join(f"- {warning}" for warning in generated_warnings) or "- None"
    fewer_than_requested = ""
    if alignment_diagnostics["sampled_ids"] < alignment_diagnostics["sample_size_requested"]:
        fewer_than_requested = (
            f"\n- Fewer than requested usable matched IDs were available; "
            f"used all {alignment_diagnostics['sampled_ids']} usable matched IDs."
        )

    diagnostics = f"""# Loading Diagnostics

## Input Directories
- Requested generated dir: `{requested_generated_dir}`
- Resolved generated dir: `{resolved_generated_dir}`
- Original dir: `{original_dir}`

Directory warnings:
{generated_warning_text}

## Source Loading
{source_diagnostics_markdown(before)}
{source_diagnostics_markdown(after)}
{source_diagnostics_markdown(original)}

## Matching
- Union IDs across all sources: {alignment_diagnostics['union_ids']}
- IDs present in before, after, and original: {alignment_diagnostics['matched_present_ids']}
- Usable matched IDs with non-empty before, after, and original text: {alignment_diagnostics['usable_matched_ids']}
- Sample size requested: {alignment_diagnostics['sample_size_requested']}
- Sample size written: {alignment_diagnostics['sampled_ids']}{fewer_than_requested}

## Missing IDs
- Missing before: {len(alignment_diagnostics['missing_before'])}; sample: {sample_markdown_list(alignment_diagnostics['missing_before'])}
- Missing after: {len(alignment_diagnostics['missing_after'])}; sample: {sample_markdown_list(alignment_diagnostics['missing_after'])}
- Missing original: {len(alignment_diagnostics['missing_original'])}; sample: {sample_markdown_list(alignment_diagnostics['missing_original'])}
- Present in before+after but missing original: {len(alignment_diagnostics['before_after_missing_original'])}; sample: {sample_markdown_list(alignment_diagnostics['before_after_missing_original'])}
- Present in before+original but missing after: {len(alignment_diagnostics['before_original_missing_after'])}; sample: {sample_markdown_list(alignment_diagnostics['before_original_missing_after'])}
- Present in after+original but missing before: {len(alignment_diagnostics['after_original_missing_before'])}; sample: {sample_markdown_list(alignment_diagnostics['after_original_missing_before'])}

## Empty Texts Among Matched IDs
- Empty before texts: {len(alignment_diagnostics['empty_before_matched'])}; sample: {sample_markdown_list(alignment_diagnostics['empty_before_matched'])}
- Empty after texts: {len(alignment_diagnostics['empty_after_matched'])}; sample: {sample_markdown_list(alignment_diagnostics['empty_after_matched'])}
- Empty original OCR texts: {len(alignment_diagnostics['empty_original_matched'])}; sample: {sample_markdown_list(alignment_diagnostics['empty_original_matched'])}

## Schema Assumptions
- Generated JSONL records were loaded by detected shared ID keys, primarily `report_id`.
- Generated output text was loaded from detected text keys, primarily `text`.
- Original report JSON files were treated as top-level mappings from report/case ID to an object containing `ocr_text`.
- Duplicate generated or original IDs were deduplicated by retaining the longest non-empty text.
- Sampling used only IDs present in all three sources and with non-empty before, after, and original text.
- Sampling used deterministic `random.Random(seed)` over sorted usable matched IDs.
- Pairwise judging assigns before/after to Model X/Model Y per report using a deterministic SHA-256 seed.
"""
    (out_dir / "loading_diagnostics.md").write_text(diagnostics, encoding="utf-8")


def main() -> int:
    args = parse_args()
    requested_generated_dir = Path(args.generated_dir)
    resolved_generated_dir, generated_warnings = resolve_generated_dir(requested_generated_dir)
    original_dir = Path(args.original_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if not resolved_generated_dir.exists():
        print(f"Generated directory not found: {resolved_generated_dir}", file=sys.stderr)
        return 2
    if not original_dir.exists():
        print(f"Original directory not found: {original_dir}", file=sys.stderr)
        return 2

    before = load_generated_outputs(resolved_generated_dir, "before")
    after = load_generated_outputs(resolved_generated_dir, "after")
    original = load_original_reports(original_dir)

    aligned_rows, alignment_diagnostics = build_alignment(
        before,
        after,
        original,
        sample_size=args.n,
        seed=args.seed,
    )
    write_jsonl(out_dir / "aligned_sample_500.jsonl", aligned_rows)

    judgments, judge_status = run_judging(
        aligned_rows,
        out_dir=out_dir,
        seed=args.seed,
        judge_model=args.judge_model,
        max_original_chars=args.max_original_chars,
        max_output_chars=args.max_output_chars,
    )

    aggregate_rows = write_aggregate_scores(out_dir, judgments)
    win_rows = write_win_rates(out_dir, judgments)
    write_summary_report(
        out_dir,
        before=before,
        after=after,
        original=original,
        alignment_diagnostics=alignment_diagnostics,
        aggregate_rows=aggregate_rows,
        win_rows=win_rows,
        judgments=judgments,
        judge_status=judge_status,
    )
    write_loading_diagnostics(
        out_dir,
        requested_generated_dir=requested_generated_dir,
        resolved_generated_dir=resolved_generated_dir,
        generated_warnings=generated_warnings,
        original_dir=original_dir,
        before=before,
        after=after,
        original=original,
        alignment_diagnostics=alignment_diagnostics,
    )

    print(f"Aligned sample rows: {len(aligned_rows)}")
    print(f"Judged rows: {len(judgments)}")
    if judge_status:
        print(judge_status)
    print(f"Wrote outputs to: {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
