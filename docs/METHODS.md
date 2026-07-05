# Methods

## Model

- **Base:** `togethercomputer/Meta-Llama-3.3-70B-Instruct-Reference`, loaded in **4-bit NF4** (`bnb_4bit_compute_dtype=bfloat16`).
- **Adaptation:** PEFT/LoRA adapter (PEFT 0.15.1), released on Hugging Face as `AliKhajegiliM/PaRLA`.
- **Training source:** the **HISTAI** pathology dataset, available as digital pathology report text (not OCR). The adapted SFT set — [`AliKhajegiliM/PaRLA-SFT`](https://huggingface.co/datasets/AliKhajegiliM/PaRLA-SFT), 24,370 examples generated via the Adaption Data platform — pairs an `enhanced_prompt` (instruction + case findings) with an `enhanced_completion` (reasoning + conclusion). PaRLA is adapted to transform a report into a `<reasoning>` block and a `<final_conclusion>` block.

Both PaRLA and the base comparator run on the **same 4-bit quantized Llama 70B backbone**, so quantization is held constant across every comparison below.

## Generation prompt (schema)

The model is prompted to return exactly two sections:

```text
<reasoning> integrated pathology reasoning based only on the report </reasoning>
<final_conclusion> final integrated diagnostic, biomarker, and prognosis-relevant conclusion </final_conclusion>
```

It is directed to integrate diagnosis, histology, grade, tumor extent and stage-relevant spread, margins, lymphovascular/perineural invasion, nodal burden and ratios, metastatic sites, treatment effect, biomarkers, immunohistochemistry, and molecular findings; to preserve explicitly negative, equivocal, deferred, or unassessable findings exactly as stated; and to avoid inventing information or resolving uncertainty the report leaves open.

## Validation design

Three distinct evaluations, in increasing order of distribution shift:

1. **Internal AutoScientist held-out** — the direct challenge criterion. In-domain (HISTAI-derived digital text), held out from adaptation. Measures whether the adapter learned the intended behavior without memorizing training examples.
2. **External TCGA, LLM-as-judge** — 500 independent TCGA reports that originated as **scanned PDFs**, OCR'd to text with **Chandra**. Different source and different text modality (OCR vs. digital).
3. **External TCGA, downstream survival** — whether the PaRLA abstraction preserves a quantitative, clinically actionable endpoint.

## External Validation 1 — LLM-as-judge (500 reports)

- **Source text:** Chandra-extracted OCR text from scanned TCGA pathology-report PDFs.
- **Sampling:** the 500 reports were randomly sampled with a fixed seed from all TCGA reports that had all three of: Chandra OCR text, a base Llama 70B generation, and a PaRLA generation. All 500 matched GDC case metadata (no missing cases, no duplicate IDs).
- **Judge:** a **GPT-5.5 Extra High LLM-as-judge, run via Codex** (recorded as `codex_manual_read` in `data/judgments.jsonl`). Each case was judged against the OCR source text on diagnostic essence, faithfulness/hallucination control, prognostic/staging capture, reasoning quality, conclusion quality, and overall usefulness (0–5 each), plus a head-to-head winner (`after` = PaRLA, `before` = base, or `tie`).
- **Cohort characterization:** participant barcodes were mapped through the GDC cases API, the official TCGA Tissue Source Site (TSS) code table, and a cleaned center→TSS mapping to consolidate institution names (`src/summarize_tcga_validation_cohort.py`).

## External Validation 2 — downstream survival

- Two representations of each report were embedded with the **same 4-bit base Llama 70B encoder**: (a) the full report text, and (b) the PaRLA-generated summary. The encoder is held constant, so the only variable is the representation.
- Both representations were **mean-pooled token embeddings** and fed to the **same Cox proportional-hazards survival model**, trained under **5-fold cross-validation** with **identical hyperparameters, configuration, and random seed** for both arms: Cox loss, AdamW, lr 0.001, weight decay 0.01, 100 epochs, batch size 32, hidden dim 128, feature size 8192, seed 1. Only the input representation differs. Metric: **test C-index** (0–100; 50 ≈ random ranking).
- Per-fold and per-cancer outputs for the five cancer datasets are in `results/survival/`.

## Reproducibility notes

- The scripts prefer an installed scientific stack (`requirements.txt`) and only fall back to a vendored `.plot_deps/` if none is installed.
- The cohort summarizer (`summarize_tcga_validation_cohort.py`) contacts the live GDC API and TSS code table; the resolved metadata is cached under `results/cohort/` so the diversity figures reproduce offline.
- See [REPRODUCE.md](REPRODUCE.md) for exact commands.
