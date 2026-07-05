# PaRLA — pathology report abstraction with a LoRA Llama-70B

Companion code and full experiments for **[PaRLA](https://huggingface.co/AliKhajegiliM/PaRLA)**, a LoRA adapter for `Llama-3.3-70B` that turns long, noisy pathology reports into structured clinical reasoning and a final integrated conclusion. Built for the [Adaption Labs AutoScientist Challenge](https://adaptionlabs.ai/blog/autoscientist-challenge) (Healthcare).

- **Model + weights (Hugging Face):** https://huggingface.co/AliKhajegiliM/PaRLA
- **This repo:** methods, the 500 LLM-as-judge records, all result tables, cohort metadata, and plotting code.

## Headline results

| Evaluation | Setting | Result |
|---|---|---|
| **Challenge criterion** — AutoScientist internal held-out | adapted vs. base Llama 70B, in-domain | **86%** win rate vs. 14% |
| **External** — TCGA reports, GPT-5.5 Extra High (Codex) LLM-as-judge | 500 independent OCR'd reports | **PaRLA 83.8%** / Llama 6.6% / Tie 9.6% |
| **External** — TCGA downstream survival | 5-fold test C-index, 5 cancer datasets | **+1.8 to +5.2** C-index points vs. full report |

The internal held-out test is the direct challenge criterion. The two TCGA studies are independent generalization tests on a different source (scanned-PDF reports OCR'd to text), covering 32 cancer cohorts and 92 centers.

## Repository layout

```
.
├── src/
│   ├── compare_before_after.py                 # LLM-as-judge alignment + comparison harness
│   ├── make_publication_plots_seaborn.py       # win-rate + category-score figures
│   ├── make_tcga_validation_diversity_plots.py # TCGA cohort-diversity figures
│   ├── summarize_tcga_validation_cohort.py     # GDC barcode → TSS/center/site metadata
│   └── survival/make_survival_comparison_plot.py
├── data/
│   └── judgments.jsonl          # 500 GPT-5.5 (Codex) judge records — the evidence file
├── results/
│   ├── judge/                   # win rates + per-criterion category deltas (n=500)
│   ├── cohort/                  # TCGA cohort diversity (cleaned CSVs + summary)
│   └── survival/                # C-index tables + per-cancer fold CSVs (5 datasets)
├── figures/                     # all 9 vector figures used on the model card
├── docs/                        # METHODS, RESULTS, REPRODUCE
├── model_card/                  # mirror of the Hugging Face card
└── examples/load_and_infer.py   # minimal load + single-report inference
```

See [docs/METHODS.md](docs/METHODS.md), [docs/RESULTS.md](docs/RESULTS.md), and [docs/REPRODUCE.md](docs/REPRODUCE.md).

## Quickstart

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

Load the model (4-bit base + adapter): see [examples/load_and_infer.py](examples/load_and_infer.py).

## Data availability

`data/judgments.jsonl` (the 500 judge records that back every external number) is included. The raw TCGA report OCR text, the full base/PaRLA generations, and the survival model checkpoints (`*.pt`) are **not** committed — TCGA/GDC reports are open-access and downloadable from the [GDC Data Portal](https://portal.gdc.cancer.gov/); see [data/README.md](data/README.md) for how each artifact is regenerated. Per-cancer survival result CSVs are committed so the C-index tables and figure reproduce without the checkpoints.

## Citation

See [CITATION.cff](CITATION.cff). Code is released under the MIT License ([LICENSE](LICENSE)); the LoRA adapter follows the Meta Llama 3.3 Community License, and TCGA data follows GDC data-use terms.
