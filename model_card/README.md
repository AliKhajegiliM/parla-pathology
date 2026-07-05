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

# PaRLA — a LoRA Llama-70B that beats base Llama on pathology report abstraction

**PaRLA** is a LoRA adapter for `Llama-3.3-70B` that turns long, noisy pathology reports into structured, evidence-grounded clinical reasoning and a final integrated conclusion. It was adapted for the [Adaption Labs AutoScientist Challenge](https://adaptionlabs.ai/blog/autoscientist-challenge) (Healthcare) and **beats the base model on the challenge's held-out test set — then generalizes to independent TCGA data** on both an LLM-as-judge comparison and a downstream survival benchmark.

| Evaluation | Setting | Result |
|---|---|---|
| **Challenge criterion** — AutoScientist internal held-out | adapted vs. base Llama 70B, in-domain | **86%** win rate vs. 14% |
| **External** — TCGA reports, GPT-5.5 Extra High (Codex) LLM-as-judge | 500 independent OCR'd reports | **PaRLA 83.8%** / Llama 6.6% / Tie 9.6% |
| **External** — TCGA downstream survival | 5-fold test C-index, 5 cancer datasets | **+1.8 to +5.2** C-index points vs. full report |

This repo is a **PEFT/LoRA adapter** (not a standalone model); load it on the 4-bit base — see [How to use](#how-to-use). It was fine-tuned on **[AliKhajegiliM/PaRLA-SFT](https://huggingface.co/datasets/AliKhajegiliM/PaRLA-SFT)**, 24,370 pathology-reasoning examples derived from the HISTAI dataset via the Adaption Data platform. Full methods, the 500 judge records, all result tables, and reproduction code live in the companion repository: **[github.com/AliKhajegiliM/parla-pathology](https://github.com/AliKhajegiliM/parla-pathology)**.

## Results

The internal AutoScientist held-out test is the **direct challenge criterion** (in-domain, HISTAI-derived digital report text). The two TCGA studies are **independent generalization tests**: TCGA is a different source, and its reports are scanned-PDF pathology reports converted to text by OCR — a genuinely different distribution from the digital training text.

### Challenge criterion — internal held-out win rate

In the AutoScientist internal held-out evaluation, the adapted PaRLA model was preferred over the base Llama 70B model in **86% of cases (vs. 14%)**. This is the metric the challenge scores on, and confirms the LoRA adaptation shifted the model toward the intended clinical-pathology extraction behavior on the in-domain test set. (Reported from the AutoScientist internal evaluation; the raw per-case scores are not mirrored in this repo.)

![Internal held-out win rate](assets/internal_autoscientist_win_rate.svg)

### Generalization 1 — TCGA reports, LLM-as-judge (500 reports)

On **500 independent TCGA pathology reports** (scanned PDFs OCR'd to text with Chandra), a high-effort in-session **GPT-5.5 Extra High LLM-as-judge (run via Codex)** compared PaRLA against the base model on diagnostic essence, prognostic/staging preservation, report-grounded reasoning, hallucination control, and conclusion quality. PaRLA won **83.8%** of head-to-head comparisons (base 6.6%, tie 9.6%).

![Pairwise win rate](assets/manual_pairwise_win_rate.svg)

The largest per-criterion gains (0–5 scale, 95% CI over 500 reports) are exactly the clinically meaningful ones — **prognostic/staging capture (+0.79)**, **conclusion quality (+0.69)**, **overall usefulness (+0.72)**, and **reasoning quality (+0.46)**. The base model stays fractionally ahead on strict hallucination control (PaRLA is more detailed, so it has more opportunities to add unsupported detail), and diagnostic essence is a statistical tie. The win is preservation and integration of structured pathology evidence, not generic fluency.

![Category ratings](assets/manual_category_scores.svg)

The 500-report cohort was randomly sampled with a fixed seed; all 500 matched GDC case metadata and span **32 TCGA cancer cohorts, 92 contributing centers, 34 primary sites, and 19 disease types** — evidence that the win is not specific to one cancer or institution. Full cohort tables are in the [companion repo](https://github.com/AliKhajegiliM/parla-pathology).

![TCGA validation cohort breadth](assets/tcga_validation_diversity_summary.svg)

### Generalization 2 — downstream survival prediction

As a quantitative test of whether the abstraction preserves clinically actionable signal, a survival model was trained on embeddings of either the **full report** or the **PaRLA summary**, both encoded with the *same* 4-bit base Llama 70B (so the only variable is the representation). Metric is 5-fold test C-index (0–100; 50 ≈ random). Five cancer datasets are shown:

![Survival C-index by cancer](assets/survival_test_cindex_by_cancer.svg)

| Cancer dataset | Δ test C-index, PaRLA summary − full report |
|---|---:|
| Bladder | +1.8 |
| Breast | +3.7 |
| Kidney | +0.0 |
| Lung | +5.2 |
| Sarcoma | +5.2 |

On these datasets, the compact PaRLA summary retained or improved survival signal relative to the full report — consistent with a pathology-specialized summarizer removing report noise while keeping survival-relevant variables (staging, biomarkers, molecular findings).

## What it is and why

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

The prompt directs the model to integrate diagnosis, histology, grade, tumor extent and stage-relevant spread, margins, lymphovascular/perineural invasion, nodal burden, metastatic sites, treatment effect, biomarkers, and molecular findings — and to preserve explicitly negative, equivocal, or unassessable findings exactly as stated, without inventing or resolving anything the report leaves open. The full prompt is in the [companion repo](https://github.com/AliKhajegiliM/parla-pathology).

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

**Not a clinical device.** PaRLA is not a substitute for a pathologist, oncologist, or validated decision-support system, and must not drive patient care without expert review. It can omit facts or state unsupported details, especially on ambiguous, fragmented, or OCR-degraded reports. The manual LLM-as-judge scoring is a structured comparative assessment, not a regulatory validation; the survival benchmark measures signal preservation, not deployment readiness. The adapter inherits the limitations and biases of the base Llama 70B model and its training corpus.

**Research use only; respect the source licenses.** This model and its associated data are released for research purposes only. The work is derived from the **HISTAI** (training) and **TCGA** (external validation) pathology datasets and is intended to comply with their original data-use licenses. Anyone using this model or the associated data must likewise comply with the original TCGA (NCI GDC) and HISTAI license terms, in addition to the Meta Llama 3.3 Community License that governs the adapter.

## Links and citation

- **Training dataset (Hugging Face):** [AliKhajegiliM/PaRLA-SFT](https://huggingface.co/datasets/AliKhajegiliM/PaRLA-SFT) — adapted SFT data (24,370 HISTAI-derived examples)
- **Training dataset (Kaggle):** [adaption-combined-adapted-histai-no-skin](https://www.kaggle.com/datasets/alikhajegilimirabadi/adaption-combined-adapted-histai-no-skin) — Kaggle release (skin/dermatopathology cases excluded)
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
