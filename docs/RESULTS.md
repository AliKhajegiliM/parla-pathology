# Results

All numbers below are reproduced from the committed files in `results/` and `data/judgments.jsonl`.

## Internal AutoScientist held-out (challenge criterion)

Adapted PaRLA was preferred over base Llama 70B in **86%** of held-out cases (vs. 14%) in the AutoScientist internal evaluation on the HISTAI-derived in-domain test set. This is the metric the challenge scores on. The raw per-case scores from the AutoScientist platform are not mirrored in this repo.

## External Validation 1: TCGA LLM-as-judge (n = 500)

Judge: GPT-5.5 Extra High, run via Codex. Source: `results/judge/`, `data/judgments.jsonl`.

### Head-to-head win rate

| Outcome | Count | Win rate |
|---|---:|---:|
| PaRLA | 419 | 83.8% |
| Llama 70B | 33 | 6.6% |
| Tie | 48 | 9.6% |

### Robustness of the win (reproduce with `src/analyze_judgments.py`)

- **Significance:** 419 wins / 33 losses / 48 ties. Sign test on decided cases: z = 18.1 (p < 1e-50).
- **Length control:** PaRLA outputs are longer in 83.2% of cases (1.39x mean). On the 84 cases where PaRLA is *not* longer than base, PaRLA still wins 56% (base 11%, tie 33%), so the preference survives length control.
- **Length-independent content signal:** base Llama drops a mean 3.99 major clinical facts per report; PaRLA drops 1.36.
- **Hallucination trade-off (honest):** PaRLA introduces an unsupported detail in 14.0% of cases vs base 12.6% (85 vs 67 total items); net 2.6 fewer omissions per report. By clinical type, PaRLA's 85 unsupported items are ~34 lymph-node counts/denominators, ~15 biomarker/IHC, ~12 stage/grade/margin, ~4 admin/pending, ~20 other. The node-count/denominator error in multi-part specimens is the top failure mode (it affects N-stage), so nodal ratios should be human-verified.

Full numbers: `results/judge/robustness_summary.json` (regenerate with `python src/analyze_judgments.py`; length control uses the committed `results/judge/generation_lengths.csv`).

### Per-criterion mean scores (0–5 scale, n = 500)

| Criterion | Llama 70B | PaRLA | Δ (PaRLA − Llama) |
|---|---:|---:|---:|
| Diagnostic essence | 4.88 | 4.94 | +0.06 |
| Hallucination control | 4.84 | 4.79 | −0.06 |
| Prognostic/staging capture | 4.01 | 4.80 | **+0.79** |
| Reasoning quality | 4.38 | 4.85 | **+0.46** |
| Conclusion quality | 4.04 | 4.73 | **+0.69** |
| Overall usefulness | 4.10 | 4.82 | **+0.72** |
| Reasoning: prognostic features | 4.14 | 4.81 | **+0.68** |
| Conclusion: prognostic features | 3.90 | 4.64 | **+0.74** |
| Reasoning: hallucination control | 4.85 | 4.80 | −0.05 |
| Conclusion: hallucination control | 4.92 | 4.86 | −0.05 |

PaRLA's gains concentrate in the clinically meaningful axes (prognostic/staging, conclusion, overall usefulness, reasoning). Diagnostic essence is a statistical tie; the base model is fractionally ahead on strict hallucination control because PaRLA is more detailed. Full per-criterion 95% CIs are in `results/judge/figure_category_scores.csv`.

### Cohort diversity (n = 500)

| Cases | Cancer cohorts | Centers | TSS codes | Primary sites | Disease types |
|---:|---:|---:|---:|---:|---:|
| 500 | 32 | 92 | 236 | 34 | 19 |

All 500 sampled reports matched GDC case metadata. Full breakdown: `results/cohort/`.

## External Validation 2: downstream survival (test C-index, 0–100)

Both the full report and the PaRLA summary were embedded with the same 4-bit base Llama 70B encoder; 5-fold C-index. Run on **five TCGA cohorts totaling 2,819 patients**. Patient counts are unique `case_id`s and are identical for both arms. Source: `results/survival/`.

| TCGA cohort | Patients (n) | Full report | PaRLA summary (95% CI) | Δ points |
|---|---:|---:|---:|---:|
| Bladder (BLCA) | 378 | 61.2 | 63.1 (±7.6) | +1.8 |
| Breast (BRCA) | 1,034 | 60.8 | 64.5 (±3.7) | +3.7 |
| Kidney (KIRC + KIRP) | 805 | 75.4 | 75.4 (±4.1) | +0.0 |
| Lung adeno (LUAD) | 353 | 63.6 | 68.8 (±4.6) | +5.2 |
| Sarcoma (SARC) | 249 | 57.3 | 62.5 (±6.3) | +5.2 |
| **Total** | **2,819** | | | |

**Significance (honest):** per-cohort 95% CIs overlap and no single cohort reaches significance at 5 folds (best is sarcoma, paired t(4)=2.72, n.s.). The pooled paired test across all 25 fold-pairs is significant: mean +3.2 points, t(24)=2.27, p ≈ 0.02, with 17/25 folds favoring PaRLA. So PaRLA gives a modest, consistent preservation/gain of survival signal, not a large per-cohort effect. Reproduce from `results/survival/survival_fold_results_long.csv`. Per-fold values and per-cancer outputs are in `results/survival/`.
