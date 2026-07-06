# Prompts

The exact prompts used to generate the model outputs evaluated in this repository.

## Report summarization

The prompt used to abstract a pathology report into reasoning and a final conclusion.

```python
GENERATION_TASK = (
    """
    Your task is to analyze the provided gross (macroscopic) description, microscopic findings, and any accompanying clinical or referral notes for a single pathology case. You must reason from these findings to derive the pathologist's final conclusion, adhering strictly to the content of the report.

    Grounding Rules (Highest Priority)
    Strict Adherence to Source: Use only information explicitly stated in the input. Preserve the report's original wording and terminology. Do not restyle findings to fit a different reporting standard or rephrase them using terms not present in the source.
    No Inference of Absence: Report only features the text explicitly addresses. Do not add, infer, or fill in fields that are expected for this specimen type but are absent from the input.
    If a feature is not mentioned, omit it entirely. Silence is not a negative result.
    Do not state a feature is "absent," "negative," "not identified," "not involved," or "clear" unless the report explicitly states so.
    If the report states a determination cannot be made or was not assessable, carry that statement forward exactly as written.
    No Fabrication: Do not invent measurements, counts, scores, grades, stages, or ancillary/biomarker results. If the report defers a determination (e.g., recommends FISH or further study), preserve that deferral without resolving it.
    Scope Matching: Match the scope of the report's own conclusion. Do not expand a specific bottom line into an exhaustive synoptic listing of every possible field.
    Reasoning Approach
    Observation to Conclusion: Work logically from observation to conclusion, explicitly naming the reported findings that drive each determination.
    Case Specificity: Address only what the case actually involves. Do not impose categories (e.g., tumor grade, stage) if the findings do not support them.
    Integration: When multiple specimens, blocks, or cores are described, integrate them into a single case-level assessment. Consolidate reported invasion, margin, and nodal findings by carrying forward the most significant finding rather than listing each in isolation.
    Output Format
    Respond exactly using the following structure:

    Reasoning: A concise account of the key reported findings and how they lead to the determination. 
    Conclusion: The committed, integrated final conclusion for the case, stated in the report's own terms.
"""
)
```

## Survival external validation

The prompt used to abstract reports for the downstream survival external validation.

```python
INSTRUCTION = (
    "You are an expert surgical pathologist synthesizing this case for tumor-board "
    "prognostication. Reason through the report the way you would to commit to a final "
    "diagnosis and prognosis. Integrate every reported finding across all specimens, "
    "blocks, and cores — not only tumor type, grade, and stage, but margins, lymphovascular "
    "and perineural invasion, nodal burden and ratios, treatment effect or regression, "
    "biomarker and molecular results, and any background, incidental, or benign findings. "
    "Weigh affirmative findings against explicitly negative ones; carry equivocal, deferred, "
    "or unassessable determinations forward exactly as stated rather than resolving them. "
    "Let the totality of this evidence — what is present, what is absent, and what remains "
    "uncertain — determine the patient's likely clinical course."
)

GENERATION_TASK = (
    "Generate the response in the same reasoning-and-final-conclusion style used during training. "
    "Do not merely summarize the report. First reason through the case as a surgical pathologist "
    "integrating all reported evidence, then commit to a final diagnostic and prognostic conclusion.\n\n"

    "In the reasoning, explicitly synthesize:\n"
    "1. the primary diagnosis, tumor type, histology, grade, and differentiation;\n"
    "2. tumor extent, invasion, anatomic spread, stage-relevant findings, and specimen-level distribution;\n"
    "3. margin status, lymphovascular invasion, perineural invasion, nodal involvement, nodal ratios, "
    "and metastatic disease when reported;\n"
    "4. treatment effect, regression, residual viable tumor, necrosis, or response-related findings;\n"
    "5. biomarker, immunohistochemical, cytogenetic, and molecular findings relevant to diagnosis, "
    "classification, prognosis, or therapy;\n"
    "6. explicitly negative, equivocal, deferred, indeterminate, or unassessable findings exactly as stated;\n"
    "7. background, incidental, precursor, benign, or non-neoplastic findings that may affect interpretation.\n\n"

    "Weigh the positive and negative findings together. Do not invent missing information. "
    "Do not resolve uncertainty unless the report resolves it. Preserve ambiguity when the report is "
    "equivocal, deferred, pending, or unassessable.\n\n"

    "Return the output using this exact format:\n"
    "<reasoning>\n"
    "Integrated pathology reasoning based only on the report.\n"
    "</reasoning>\n"
    "<final_conclusion>\n"
    "Final integrated diagnosis and prognosis-relevant conclusion.\n"
    "</final_conclusion>"
)
```
