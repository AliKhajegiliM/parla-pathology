# Data

## Committed here

- **`judgments.jsonl`** — 500 records from the GPT-5.5 Extra High (Codex) LLM-as-judge external validation. Each record has the report ID, per-criterion 0–5 scores for the base (`before`) and PaRLA (`after`) outputs, the head-to-head winner, judge confidence, a free-text reason, and lists of major omissions, hallucinations, and key original facts. This is the evidence file behind every number in [../docs/RESULTS.md](../docs/RESULTS.md). It contains short extracted facts, not full report text.

## Not committed (hosted externally / regenerable)

| Artifact | What it is | Where to get it |
|---|---|---|
| `original_reports/*.json` | Raw TCGA pathology-report OCR text (Chandra) | TCGA reports are open-access at the [GDC Data Portal](https://portal.gdc.cancer.gov/); OCR with Chandra |
| `gen_chandra_{before,after}_*.jsonl` | Full base and PaRLA generations per report | Regenerate: run base Llama 70B and `AliKhajegiliM/PaRLA` on the OCR text |
| `aligned_sample_500.jsonl` | The 500 aligned (report text + both generations) | Rebuild with `src/compare_before_after.py` from the two directories above |
| `*.pt` checkpoints | Per-fold survival models | Regenerate from `src/survival/`; only needed to re-derive from scratch |

TCGA/GDC pathology reports are open-access but governed by [GDC data-use policies](https://gdc.cancer.gov/about-data/data-analysis-policies). The per-cancer survival result CSVs (`../results/survival/per_cancer/`) are committed so the C-index tables and figure reproduce without the checkpoints.
