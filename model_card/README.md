<!-- Mirror of the Hugging Face model card. Canonical, rendered version: https://huggingface.co/AliKhajegiliM/PaRLA -->

---
base_model: togethercomputer/Meta-Llama-3.3-70B-Instruct-Reference
library_name: peft
pipeline_tag: text-generation
datasets:
- AliKhajegiliM/PaRLA-SFT
tags:
- pathology
- oncology
- surgical-pathology
- prognostic-summary
- biomarker-extraction
- clinical-information-extraction
- molecular-pathology
- survival-analysis
- peft
- lora
- llama
- healthcare
---

# PaRLA: a LoRA Llama-70B that beats base Llama on pathology report abstraction

![PaRLA demo banner](assets/parla_social_banner.svg)

**PaRLA** is a LoRA adapter for `Llama-3.3-70B` that turns long, noisy pathology reports into structured, evidence-grounded clinical reasoning and a final integrated conclusion. It was adapted for the [Adaption Labs AutoScientist Challenge](https://adaptionlabs.ai/blog/autoscientist-challenge) (Healthcare) and **beats the base model on the challenge's held-out test set, then generalizes to independent TCGA data** on both an LLM-as-judge comparison and a downstream survival benchmark.

| Evaluation | Setting | Result |
|---|---|---|
| **External, reproducible:** TCGA reports, GPT-5.5 Extra High (Codex) LLM-as-judge | PaRLA vs. base Llama 70B on 500 independent OCR'd reports | **PaRLA 83.8%** / base 6.6% / Tie 9.6% (sign test *p* < 1e-50) |
| **External, reproducible:** TCGA downstream survival | 5-fold test C-index, 5 TCGA cohorts (2,819 patients) | improves 4 of 5; pooled **+3.2** C-index pts (*p* ≈ 0.03) |
| **Challenge criterion** (platform-reported): AutoScientist internal held-out | adapted vs. base Llama 70B, in-domain | **86%** win rate vs. 14% |

*Both external results reproduce exactly from the released [`judgments.jsonl`](https://github.com/AliKhajegiliM/parla-pathology/blob/main/data/judgments.jsonl) and result CSVs (rerun [`analyze_judgments.py`](https://github.com/AliKhajegiliM/parla-pathology/blob/main/src/analyze_judgments.py)). The internal 86% is the metric the challenge scores on; it is reported by the AutoScientist platform and is not independently reproducible from this repo (raw per-case scores are held on the platform).*

This repo is a **PEFT/LoRA adapter** (not a standalone model); load it on the 4-bit base (see [How to use](#how-to-use)). It was fine-tuned on **[AliKhajegiliM/PaRLA-SFT](https://huggingface.co/datasets/AliKhajegiliM/PaRLA-SFT)**, 24,370 pathology-reasoning examples derived from the [HISTAI](https://huggingface.co/datasets/histai/HISTAI-metadata) dataset via the Adaption Data platform. Full methods, the 500 judge records, all result tables, and reproduction code live in the companion repository: **[github.com/AliKhajegiliM/parla-pathology](https://github.com/AliKhajegiliM/parla-pathology)**.

## Results

**The Cancer Genome Atlas (TCGA)** is a widely used, standard public cancer dataset in oncology and pathology: an NCI/NHGRI program that characterized ~20,000 tumors across 33 cancer types. Validating on TCGA tests PaRLA on data independent of the HISTAI training source.

The internal AutoScientist held-out test is the **direct challenge criterion** (in-domain, HISTAI-derived digital report text). The two TCGA studies are **independent generalization tests**: TCGA is a different source from the HISTAI training data, and its reports are scanned-PDF pathology reports converted to text by OCR, a different distribution from the digital training text.

### Challenge criterion: internal held-out win rate

In the AutoScientist internal held-out evaluation, the adapted PaRLA model was preferred over the base Llama 70B model in **86% of cases (vs. 14%)**. This is the metric the challenge scores on, and confirms the LoRA adaptation shifted the model toward the intended clinical-pathology extraction behavior on the in-domain test set. (Reported from the AutoScientist internal evaluation; the raw per-case scores are not mirrored in this repo.)

![Internal held-out win rate](assets/internal_autoscientist_win_rate.svg)

### Generalization 1: TCGA reports, LLM-as-judge (500 reports)

On **500 independent TCGA pathology reports** (scanned PDFs OCR'd to text with Chandra), a **GPT-5.5 Extra High LLM-as-judge (run via Codex)** compared PaRLA against the base model on diagnostic essence, prognostic/staging preservation, report-grounded reasoning, hallucination control, and conclusion quality. PaRLA won **83.8%** of head-to-head comparisons against the base Llama 70B model (base Llama 70B 6.6%, tie 9.6%).

![Pairwise win rate](assets/manual_pairwise_win_rate.svg)

The largest per-criterion gains (0–5 scale, 95% CI over 500 reports) are in clinically meaningful criteria: **prognostic/staging capture (+0.79)**, **conclusion quality (+0.69)**, **overall usefulness (+0.72)**, and **reasoning quality (+0.46)**. The base model stays fractionally ahead on strict hallucination control (PaRLA is more detailed, so it has more opportunities to add unsupported detail), and diagnostic essence is a statistical tie. The gains are in preservation and integration of structured pathology evidence.

![Category ratings](assets/manual_category_scores.svg)

The 500-report cohort was randomly sampled with a fixed seed; all 500 matched GDC case metadata and span **32 TCGA cancer cohorts, 92 contributing centers, 34 primary sites, and 19 disease types**. Full cohort tables are in the [companion repo](https://github.com/AliKhajegiliM/parla-pathology).

![TCGA validation cohort breadth](assets/tcga_validation_diversity_summary.svg)

### Generalization 2: downstream survival prediction

As a quantitative test of whether the abstraction preserves clinically actionable signal, both the **full report** and the **PaRLA summary** were encoded as **mean-pooled token embeddings** from the *same* 4-bit base Llama 70B, then fed to the **same Cox proportional-hazards survival model** trained under **5-fold cross-validation** with **identical hyperparameters, configuration, and random seed** for both arms. Only the input representation differs, so any change in C-index is attributable to the representation alone. Metric is test C-index (0–100; 50 ≈ random). The task was run on **five TCGA cohorts totaling 2,819 patients**: bladder (BLCA), breast (BRCA), kidney (KIRC + KIRP), lung adenocarcinoma (LUAD), and sarcoma (SARC):

![Survival C-index by cancer](assets/survival_test_cindex_by_cancer.svg)

| TCGA cohort | Patients (n) | Full report | PaRLA summary (95% CI) | Δ points |
|---|---:|---:|---:|---:|
| Bladder (BLCA) | 378 | 61.2 | 63.1 (±7.6) | +1.8 |
| Breast (BRCA) | 1,034 | 60.8 | 64.5 (±3.7) | +3.7 |
| Kidney (KIRC + KIRP) | 805 | 75.4 | 75.4 (±4.1) | +0.0 |
| Lung adenocarcinoma (LUAD) | 353 | 63.6 | 68.8 (±4.6) | +5.2 |
| Sarcoma (SARC) | 249 | 57.3 | 62.5 (±6.3) | +5.2 |
| **Total** | **2,819** | | | |

PaRLA summaries improve C-index in 4 of the 5 cohorts and leave kidney flat; none regress. The **pooled effect across all 25 fold-pairs is significant** (mean +3.2 points, paired *t*(24) = 2.27, *p* ≈ 0.03; 17 of 25 folds favor PaRLA). This is a modest, consistent preservation/gain of survival signal. Per-fold values are in the [companion repo](https://github.com/AliKhajegiliM/parla-pathology).

### Example cases (base vs. PaRLA)

Two real cases from the 500-report set, both judged a PaRLA win with no hallucinations. The **PaRLA** row shows the clinically critical facts it recovers on top of the base model.

**Breast, `TCGA-V7-A7HQ`**

| Model | Conclusion captures |
|---|---|
| ⬜ **Base Llama 70B** | Invasive ductal carcinoma, grade 2; metastatic carcinoma in sentinel nodes; pT1c pN2a; ER/PR positive; HER2 not amplified. |
| 🟦 **PaRLA** *(adds)* | Exact nodal burden **5 of 18 nodes**; **ER 65% / PR 80% / HER2 not amplified by FISH**; **venous/lymphatic invasion**; **inferior mastectomy margin involved** with a separately re-excised negative margin. |

**Bladder, `TCGA-DK-A1AC`**

| Model | Conclusion captures |
|---|---|
| ⬜ **Base Llama 70B** | High-grade invasive urothelial carcinoma, perivesical invasion (pT3b); prostate adenocarcinoma Gleason 3+3=6. |
| 🟦 **PaRLA** *(adds)* | **Bilateral pelvic node counts (0/11 and 0/11)**; **prostate stage pT2b** (organ-confined, seminal vesicles free); **prostatic intraepithelial neoplasia**; benign ureter and vas-deferens segments. |

Every added fact is present in the source report. Across all 500 reports, base Llama drops a mean of **3.99 major clinical facts per report; PaRLA drops 1.36**.

### Live demo

The two cases above are static; the **[live demo](https://huggingface.co/spaces/AliKhajegiliM/PaRLA)** lets you click through 16 cases across 13 cancer types, each with the base and PaRLA outputs and the judge's verdict. Source: [`demo/index.html`](https://github.com/AliKhajegiliM/parla-pathology/blob/main/demo/index.html).

### Robustness checks

- **Significance.** PaRLA wins 419, loses 33, ties 48 of 500. A sign test on the decided cases gives *p* < 1e-50.
- **Not just length.** PaRLA outputs are longer in 83.2% of cases (1.39× on average), a known confound for LLM judges. But even on the **84 cases where PaRLA is no longer than base**, PaRLA still wins **56%** (base 11%, tie 33%), so the preference survives length control. The omission metric above (3.99 vs 1.36) is length-independent.
- **Hallucination.** More detail carries more risk: PaRLA adds an unsupported detail in **14.0%** of cases vs base **12.6%** (85 vs 67 total items), and base stays fractionally ahead on strict hallucination-control scoring. The most common error type is **lymph-node counts/denominators in multi-part specimens (34 of 85 items)**, which drive N-stage, so nodal ratios are the field most needing human re-verification. The net trade is favorable (2.6 fewer omissions per report).

## What it is and why?

Pathology reports are long, heterogeneous, and institution-specific; the clinically important variables (biomarker status, immunophenotype, molecular alterations, margins, nodal ratios, invasion, metastasis, treatment response, uncertainty) are scattered across final diagnosis, synoptic sections, gross descriptions, addenda, IHC, and molecular blocks, and OCR adds noise. Generic LLM summaries capture the headline diagnosis but drop this structured evidence. PaRLA is prompted and adapted to reason like a surgical pathologist building a tumor-board synthesis and to compress the report into a **clinically enriched representation** useful for biomarker extraction, cohort phenotyping, and downstream modeling.

## Generation style

PaRLA returns two explicit sections:

```text
<reasoning>
Integrated pathology reasoning based only on the report.
</reasoning>
<final_conclusion>
Final integrated diagnostic, biomarker, and prognosis-relevant conclusion.
</final_conclusion>
```

The prompt directs the model to integrate diagnosis, histology, grade, tumor extent and stage-relevant spread, margins, lymphovascular/perineural invasion, nodal burden, metastatic sites, treatment effect, biomarkers, and molecular findings; and to preserve explicitly negative, equivocal, or unassessable findings exactly as stated, without inventing or resolving anything the report leaves open. The full prompt is in the [companion repo](https://github.com/AliKhajegiliM/parla-pathology).

All experiments above used **4-bit (NF4) quantized Llama 70B** for both PaRLA and the base comparator.

## How to use

```python
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
from peft import PeftModel

base_model_id = "togethercomputer/Meta-Llama-3.3-70B-Instruct-Reference"
adapter_id = "AliKhajegiliM/PaRLA"

quantization_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_compute_dtype="bfloat16",
)

tokenizer = AutoTokenizer.from_pretrained(base_model_id)
base_model = AutoModelForCausalLM.from_pretrained(
    base_model_id,
    quantization_config=quantization_config,
    device_map="auto",
)
model = PeftModel.from_pretrained(base_model, adapter_id)
```

## Intended use and limitations

**Intended for research use** in pathology report abstraction, clinical biomarker/molecular extraction, cohort phenotyping, prognosis-oriented summarization, and downstream modeling from pathology text (including OCR-derived reports).

**Not a clinical device.** PaRLA is not a substitute for a pathologist, oncologist, or validated decision-support system, and must not drive patient care without expert review. It can omit facts or state unsupported details, especially on ambiguous, fragmented, or OCR-degraded reports. The survival benchmark measures signal preservation, not deployment readiness. The adapter inherits the limitations and biases of the base Llama 70B model and its training corpus.

**Reliability by field.** Grounded in the hallucination analysis above, PaRLA is most reliable on diagnosis, histologic grade, receptor/HER2 status, and margin status; it most often errs on **lymph-node counts and denominators in multi-part specimens**, so nodal ratios and multi-part specimen numbering should be human-verified before use.

**Evaluation caveat.** The external LLM-as-judge result is a single high-effort GPT-5.5 (Codex) pass, not a multi-judge or human-pathologist adjudication, and the length control addresses verbosity but not formatting-preference bias. It is a strong structured comparison, not a regulatory validation.

**Research use only; respect the source licenses.** This model and its associated data are released for research purposes only. The work is derived from the **HISTAI** (training) and **TCGA** (external validation) pathology datasets and is intended to comply with their original data-use licenses. Anyone using this model or the associated data must likewise comply with the original TCGA (NCI GDC) and HISTAI license terms, in addition to the Meta Llama 3.3 Community License that governs the adapter.

## Links and citation

- **Weights (Kaggle mirror):** [alikhajegilimirabadi/parla](https://www.kaggle.com/models/alikhajegilimirabadi/parla) (the LoRA adapter, mirrored on Kaggle; the adapter also lives in this Hugging Face repo)
- **Training dataset (Hugging Face):** [AliKhajegiliM/PaRLA-SFT](https://huggingface.co/datasets/AliKhajegiliM/PaRLA-SFT) (adapted SFT data, 24,370 HISTAI-derived examples)
- **Training dataset (Kaggle mirror):** [alikhajegilimirabadi/adaption-combined-adapted-histai-no-skin](https://www.kaggle.com/datasets/alikhajegilimirabadi/adaption-combined-adapted-histai-no-skin) (the same adapted SFT dataset, mirrored on Kaggle)
- **Training data source (HISTAI):** [histai/HISTAI-metadata](https://huggingface.co/datasets/histai/HISTAI-metadata)
- **Live demo (HF Space):** [huggingface.co/spaces/AliKhajegiliM/PaRLA](https://huggingface.co/spaces/AliKhajegiliM/PaRLA)
- **Companion code + full experiments:** [github.com/AliKhajegiliM/parla-pathology](https://github.com/AliKhajegiliM/parla-pathology)
- **Challenge:** [Adaption Labs AutoScientist Challenge](https://adaptionlabs.ai/blog/autoscientist-challenge)
- **TCGA cohort metadata sources:** [GDC API](https://docs.gdc.cancer.gov/API/Users_Guide/Search_and_Retrieval/) · [TCGA barcode](https://docs.gdc.cancer.gov/Encyclopedia/pages/TCGA_Barcode/) · [TSS code table](https://gdc.cancer.gov/resources-tcga-users/tcga-code-tables/tissue-source-site-codes)

```bibtex
@misc{khajegili2026parla,
  title        = {PaRLA: A LoRA Llama 3.3 70B for Summarizing Pathology Reports},
  author       = {Khajegili Mirabadi, Ali},
  year         = {2026},
  howpublished = {\url{https://huggingface.co/AliKhajegiliM/PaRLA}},
  note         = {Developed as part of the Adaption Labs AutoScientist Challenge}
}
```

Built with PEFT 0.15.1. For questions or collaboration, use the Hugging Face repository discussion page.
