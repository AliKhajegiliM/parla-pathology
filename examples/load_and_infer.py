#!/usr/bin/env python3
"""Minimal example: load the 4-bit base Llama 70B + the PaRLA LoRA adapter and
run one pathology report through the reasoning / final_conclusion prompt.

Requires a CUDA GPU with enough memory for 4-bit Llama-3.3-70B, plus:
    pip install transformers peft accelerate bitsandbytes
"""
from __future__ import annotations

from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from peft import PeftModel

BASE_MODEL_ID = "togethercomputer/Meta-Llama-3.3-70B-Instruct-Reference"
ADAPTER_ID = "AliKhajegiliM/PaRLA"

SYSTEM_PROMPT = (
    "You are a surgical pathologist. Read the pathology report and produce a "
    "<reasoning> block with integrated, report-grounded pathology reasoning and a "
    "<final_conclusion> block with the final diagnostic, biomarker, and "
    "prognosis-relevant conclusion. Use only what the report states; preserve "
    "explicitly negative, equivocal, or unassessable findings; do not invent or "
    "resolve uncertainty the report leaves open."
)


def load():
    quantization_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype="bfloat16",
    )
    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL_ID)
    base_model = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL_ID,
        quantization_config=quantization_config,
        device_map="auto",
    )
    model = PeftModel.from_pretrained(base_model, ADAPTER_ID)
    model.eval()
    return tokenizer, model


def summarize(tokenizer, model, report_text: str) -> str:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": report_text},
    ]
    inputs = tokenizer.apply_chat_template(
        messages, add_generation_prompt=True, return_tensors="pt"
    ).to(model.device)
    output = model.generate(inputs, max_new_tokens=1024, do_sample=False)
    return tokenizer.decode(output[0][inputs.shape[-1]:], skip_special_tokens=True)


if __name__ == "__main__":
    example_report = (
        "FINAL DIAGNOSIS: Right upper lobe, lung, excision: Adenocarcinoma, poorly "
        "differentiated. Tumor size 2.5 x 2.0 x 0.5 cm. Visceral pleura involved. "
        "IHC: TTF-1 positive, CK7 positive, CK20 negative, CDX2 negative. Lymph nodes, "
        "lymphovascular invasion, margins, and neoadjuvant treatment: not specified."
    )
    tokenizer, model = load()
    print(summarize(tokenizer, model, example_report))
