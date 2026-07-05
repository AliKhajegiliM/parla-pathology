#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import urllib.error
import urllib.request
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path


GDC_CASES_ENDPOINT = "https://api.gdc.cancer.gov/cases"
GDC_TSS_CODE_TABLE_URL = "https://gdc.cancer.gov/resources-tcga-users/tcga-code-tables/tissue-source-site-codes"


class TableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.tables: list[list[list[str]]] = []
        self._in_table = False
        self._in_row = False
        self._in_cell = False
        self._current_table: list[list[str]] = []
        self._current_row: list[str] = []
        self._current_cell_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "table":
            self._in_table = True
            self._current_table = []
        elif self._in_table and tag == "tr":
            self._in_row = True
            self._current_row = []
        elif self._in_row and tag in {"td", "th"}:
            self._in_cell = True
            self._current_cell_parts = []

    def handle_data(self, data: str) -> None:
        if self._in_cell:
            self._current_cell_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag in {"td", "th"} and self._in_cell:
            cell = " ".join(" ".join(self._current_cell_parts).split())
            self._current_row.append(cell)
            self._in_cell = False
        elif tag == "tr" and self._in_row:
            if self._current_row:
                self._current_table.append(self._current_row)
            self._in_row = False
        elif tag == "table" and self._in_table:
            if self._current_table:
                self.tables.append(self._current_table)
            self._in_table = False


def read_report_ids(path: Path) -> list[str]:
    ids: list[str] = []
    with path.open() as handle:
        for line in handle:
            if not line.strip():
                continue
            record = json.loads(line)
            report_id = str(record["report_id"]).strip()
            if report_id:
                ids.append(report_id)
    return ids


def tss_code(report_id: str) -> str:
    parts = report_id.split("-")
    if len(parts) < 3 or parts[0] != "TCGA":
        return ""
    return parts[1]


def post_gdc_cases(report_ids: list[str], fields: list[str]) -> list[dict]:
    payload = {
        "filters": {
            "op": "in",
            "content": {
                "field": "submitter_id",
                "value": report_ids,
            },
        },
        "format": "JSON",
        "fields": ",".join(fields),
        "size": str(len(report_ids)),
    }
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        GDC_CASES_ENDPOINT,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        message = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GDC request failed with HTTP {error.code}: {message}") from error
    return body["data"]["hits"]


def fetch_tss_code_table() -> dict[str, dict[str, str]]:
    with urllib.request.urlopen(GDC_TSS_CODE_TABLE_URL, timeout=60) as response:
        html = response.read().decode("utf-8")
    parser = TableParser()
    parser.feed(html)
    for table in parser.tables:
        if not table:
            continue
        header = [cell.lower() for cell in table[0]]
        if header[:4] == ["tss code", "source site", "study name", "bcr"]:
            mapping: dict[str, dict[str, str]] = {}
            for row in table[1:]:
                if len(row) < 4:
                    continue
                mapping[row[0]] = {
                    "source_site": row[1],
                    "study_name": row[2],
                    "bcr": row[3],
                }
            return mapping
    raise RuntimeError("Could not find the official TSS code table in the GDC HTML page")


def first_value(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        if not value:
            return ""
        return str(value[0])
    return str(value)


def write_counter_csv(path: Path, header: tuple[str, str, str], counter: Counter[str], denominator: int) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        for key, count in counter.most_common():
            writer.writerow([key, count, round(100.0 * count / denominator, 1)])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--aligned-jsonl", type=Path, default=Path("aligned_sample_500.jsonl"))
    parser.add_argument("--out-dir", type=Path, default=Path("."))
    args = parser.parse_args()

    report_ids = read_report_ids(args.aligned_jsonl)
    unique_ids = sorted(set(report_ids))
    duplicate_count = len(report_ids) - len(unique_ids)
    tss_codes = {report_id: tss_code(report_id) for report_id in unique_ids}
    tss_table = fetch_tss_code_table()

    fields = [
        "submitter_id",
        "project.project_id",
        "project.name",
        "primary_site",
        "disease_type",
    ]
    hits = post_gdc_cases(unique_ids, fields)
    by_id = {hit["submitter_id"]: hit for hit in hits}
    missing_gdc_ids = sorted(set(unique_ids) - set(by_id))

    metadata_path = args.out_dir / "tcga_external_validation_metadata.csv"
    with metadata_path.open("w", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "report_id",
                "tss_code",
                "tss_source_site",
                "tss_study_name",
                "tss_bcr",
                "project_id",
                "project_name",
                "primary_site",
                "disease_type",
            ],
        )
        writer.writeheader()
        for report_id in unique_ids:
            hit = by_id.get(report_id, {})
            project = hit.get("project") or {}
            writer.writerow(
                {
                    "report_id": report_id,
                    "tss_code": tss_codes.get(report_id, ""),
                    "tss_source_site": (tss_table.get(tss_codes.get(report_id, "")) or {}).get("source_site", ""),
                    "tss_study_name": (tss_table.get(tss_codes.get(report_id, "")) or {}).get("study_name", ""),
                    "tss_bcr": (tss_table.get(tss_codes.get(report_id, "")) or {}).get("bcr", ""),
                    "project_id": project.get("project_id", ""),
                    "project_name": project.get("name", ""),
                    "primary_site": first_value(hit.get("primary_site")),
                    "disease_type": first_value(hit.get("disease_type")),
                }
            )

    project_counter = Counter()
    project_name_by_id: dict[str, str] = {}
    primary_site_counter = Counter()
    disease_counter = Counter()
    tss_counter = Counter()
    tss_source_counter = Counter()
    tss_missing_codes = set()
    for report_id in unique_ids:
        code = tss_codes.get(report_id, "")
        tss_counter[code] += 1
        tss_info = tss_table.get(code)
        if tss_info:
            tss_source_counter[tss_info["source_site"]] += 1
        else:
            tss_source_counter["UNKNOWN"] += 1
            tss_missing_codes.add(code)
        hit = by_id.get(report_id, {})
        project = hit.get("project") or {}
        project_id = project.get("project_id", "UNKNOWN") or "UNKNOWN"
        project_counter[project_id] += 1
        project_name_by_id[project_id] = project.get("name", "")
        primary_site_counter[first_value(hit.get("primary_site")) or "UNKNOWN"] += 1
        disease_counter[first_value(hit.get("disease_type")) or "UNKNOWN"] += 1

    write_counter_csv(
        args.out_dir / "tcga_external_validation_tss_counts.csv",
        ("tss_code", "n_reports", "percent"),
        tss_counter,
        len(unique_ids),
    )
    write_counter_csv(
        args.out_dir / "tcga_external_validation_tss_source_site_counts.csv",
        ("tss_source_site", "n_reports", "percent"),
        tss_source_counter,
        len(unique_ids),
    )
    with (args.out_dir / "tcga_external_validation_project_counts.csv").open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["project_id", "project_name", "n_reports", "percent"])
        for project_id, count in project_counter.most_common():
            writer.writerow(
                [project_id, project_name_by_id.get(project_id, ""), count, round(100.0 * count / len(unique_ids), 1)]
            )
    write_counter_csv(
        args.out_dir / "tcga_external_validation_primary_site_counts.csv",
        ("primary_site", "n_reports", "percent"),
        primary_site_counter,
        len(unique_ids),
    )
    write_counter_csv(
        args.out_dir / "tcga_external_validation_disease_type_counts.csv",
        ("disease_type", "n_reports", "percent"),
        disease_counter,
        len(unique_ids),
    )

    top_projects = project_counter.most_common(10)
    top_tss = tss_counter.most_common(10)
    top_tss_sources = tss_source_counter.most_common(10)
    top_sites = primary_site_counter.most_common(10)

    summary = [
        "# TCGA External Validation Cohort Diversity",
        "",
        f"- Sampled report IDs: {len(report_ids)}",
        f"- Unique report IDs: {len(unique_ids)}",
        f"- Duplicate sampled IDs: {duplicate_count}",
        f"- GDC-matched cases: {len(by_id)}",
        f"- GDC-missing cases: {len(missing_gdc_ids)}",
        f"- Distinct TCGA projects/cancer cohorts: {len(project_counter)}",
        f"- Distinct TCGA TSS codes: {len(tss_counter)}",
        f"- Distinct TCGA tissue source sites: {len(tss_source_counter)}",
        f"- TSS codes not found in GDC TSS table: {len(tss_missing_codes)}",
        f"- Distinct GDC primary sites: {len(primary_site_counter)}",
        f"- Distinct GDC disease types: {len(disease_counter)}",
        "",
        "## Top TCGA Projects",
        "",
        "| Project | Project name | Reports | Percent |",
        "|---|---|---:|---:|",
    ]
    for project_id, count in top_projects:
        summary.append(
            f"| {project_id} | {project_name_by_id.get(project_id, '')} | {count} | {100.0 * count / len(unique_ids):.1f}% |"
        )

    summary.extend(["", "## Top TSS Codes", "", "| TSS code | Reports | Percent |", "|---|---:|---:|"])
    for code, count in top_tss:
        summary.append(f"| {code} | {count} | {100.0 * count / len(unique_ids):.1f}% |")

    summary.extend(["", "## Top Tissue Source Sites", "", "| Source site | Reports | Percent |", "|---|---:|---:|"])
    for site, count in top_tss_sources:
        summary.append(f"| {site} | {count} | {100.0 * count / len(unique_ids):.1f}% |")

    summary.extend(["", "## Top Primary Sites", "", "| Primary site | Reports | Percent |", "|---|---:|---:|"])
    for site, count in top_sites:
        summary.append(f"| {site} | {count} | {100.0 * count / len(unique_ids):.1f}% |")

    if missing_gdc_ids:
        summary.extend(["", "## GDC-Missing IDs", "", ", ".join(missing_gdc_ids)])

    (args.out_dir / "tcga_external_validation_diversity_summary.md").write_text("\n".join(summary) + "\n")


if __name__ == "__main__":
    main()
