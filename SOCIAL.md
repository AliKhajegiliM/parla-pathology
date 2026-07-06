# Launch post (ready to publish)

For the AutoScientist Challenge social bonus. Publish from your own account before the winners announcement, tagging Adaption Labs. Attach the banner image (`figures/parla_social_banner.svg`, or a PNG export).

- **X/Twitter tag:** @adaption_ai
- **LinkedIn tag:** adaption-labs

---

## X / Twitter (short)

Meet **PaRLA** 🔬 a LoRA-adapted Llama-3.3-70B that turns messy pathology reports into structured, tumor-board-grade summaries.

On 500 independent TCGA reports, a GPT-5.5 judge preferred PaRLA over base Llama **83.8% to 6.6%** (p < 1e-50), and it preserves downstream survival signal.

Built with @adaption_ai AutoScientist for the Healthcare challenge. Weights + adapted dataset released open.

🤖 https://huggingface.co/AliKhajegiliM/PaRLA
📊 https://github.com/AliKhajegiliM/parla-pathology

---

## LinkedIn (longer)

**PaRLA: a LoRA Llama-3.3-70B that reads pathology reports like a surgical pathologist.**

Pathology reports are long, noisy, and institution-specific, and the details that matter (biomarkers, margins, nodal burden, molecular findings, staging) are scattered across many sections. Generic LLM summaries grab the headline diagnosis but drop the structured evidence researchers actually need.

I adapted Llama-3.3-70B with LoRA on the Adaption Data platform (from the HISTAI pathology dataset) to compress a report into evidence-grounded reasoning plus a final conclusion, and validated it on independent TCGA data:

• **Wins the challenge criterion** on the AutoScientist internal held-out set vs. the base model.
• **Generalizes:** on 500 independent TCGA reports (OCR'd scanned PDFs), a GPT-5.5 (Codex) LLM-as-judge preferred PaRLA 83.8% vs. base 6.6% (tie 9.6%), sign test p < 1e-50. The win survives length control, and PaRLA drops ~1.4 major clinical facts per report vs. ~4.0 for the base model.
• **Preserves survival signal:** using PaRLA summaries instead of full reports as the input to an identical survival model improves test C-index across TCGA cohorts.

Everything is open and reproducible: adapter weights, the adapted SFT dataset, the 500 judge records, all result tables, plotting code, and a no-GPU before/after demo.

🤖 Model: https://huggingface.co/AliKhajegiliM/PaRLA
🧬 Dataset: https://huggingface.co/datasets/AliKhajegiliM/PaRLA-SFT
💻 Code + experiments: https://github.com/AliKhajegiliM/parla-pathology

Built for the adaption-labs AutoScientist Challenge (Healthcare). #AutoScientist #Pathology #LLM #Healthcare #Oncology

---

*Research use only. PaRLA is not a clinical device. Derived from the HISTAI and TCGA datasets under their respective licenses.*
