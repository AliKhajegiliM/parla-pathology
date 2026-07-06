# Reproduce

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

The committed `results/` and `data/judgments.jsonl` are the authoritative outputs; the steps below regenerate the figures and tables from them. Steps that need the large raw inputs (raw TCGA OCR text, full generations, model checkpoints) are marked; those inputs are not committed (see [../data/README.md](../data/README.md)).

## Figures from committed data (no large inputs needed)

**Judge win-rate + category-score figures**: read `data/judgments.jsonl`:

```bash
cp data/judgments.jsonl src/            # script reads ./judgments.jsonl
cd src && python make_publication_plots_seaborn.py
```

**TCGA cohort-diversity figures**: read the cached cleaned metadata:

```bash
cd src
python make_tcga_validation_diversity_plots.py \
  --metadata-csv ../results/cohort/tcga_external_validation_metadata_cleaned_centers.csv \
  --out-dir ../figures
```

The script uses the `cleaned_center` column already present in that CSV; `--center-map-json` is optional.

**Survival C-index figure**: reads the committed per-cancer fold CSVs:

```bash
# point the script at the committed per-cancer results (all_tokens/ + generated_tokens/)
cd results/survival/per_cancer
python /path/to/repo/src/survival/make_survival_comparison_plot.py
```

Per-cancer CSVs for the five datasets are committed, so the C-index tables and figure regenerate without the `*.pt` checkpoints.

## Full pipeline (needs raw inputs, hosted externally)

1. **OCR** the TCGA scanned-PDF reports with Chandra → `original_reports/*.json`.
2. **Generate** base and PaRLA outputs for each report → `gen_chandra_{before,after}_*.jsonl`.
3. **Align + sample 500 and judge:**

   ```bash
   python src/compare_before_after.py \
     --generated-dir generated_token_original_prompt \
     --original-dir original_reports \
     --out-dir model_comparison_500 \
     --n 500 --seed 42
   ```

   Note: the released `judgments.jsonl` was produced by a **GPT-5.5 Extra High judge run via Codex** (recorded as `codex_manual_read`). `compare_before_after.py` can also drive an API judge (`--judge-model`, `JUDGE_MODEL`, `OPENAI_API_KEY`); the released numbers come from the committed `judgments.jsonl`.

4. **Cohort metadata** (contacts the live GDC API + TSS code table):

   ```bash
   python src/summarize_tcga_validation_cohort.py   # writes the results/cohort/ CSVs
   ```

## Seeds

- Alignment / 500-report sampling: `seed=42`, `n=500`.
- Survival: `seed256` is the run/output directory label; the per-fold `runs_log.csv` records the actual model training seed (`seed=1`) and the Cox hyperparameters (lr 0.001, weight decay 0.01, 100 epochs, batch 32, hidden dim 128).
