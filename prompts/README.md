# Prompt library

Status of all v1 prompts: drafts, not yet run. No failure or result is recorded here until we have a real output to paste.

## Prompts and files

| Agent | File | Output |
|-------|------|--------|
| Incident Understanding | incident_understanding/v1.md | JSON |
| Vision | vision/v1.md | JSON |
| RAG query writer | rag_query/v1.md | JSON |
| RAG knowledge synthesis | rag_query/v1_synthesis.md | JSON |
| Risk Assessment | risk_assessment/v1.md | JSON |
| Report | report/v1.md | Markdown |
| Report (partial-coverage wording) | report/v2.md, untested draft | Markdown |

The RAG agent has two prompts: one writes bilingual search queries, one selects and restates the retrieved passages with citations. The synthesis step is optional. A simple variant passes the raw chunks straight to the Risk agent. Comparing the two on the same test incidents is a good piece of evidence for the multi-agent section.

## Conventions

- Each prompt version is a new file (v1.md, v2.md). Never edit an old version after it has been tested, so before and after comparisons stay reproducible.
- The text inside the system prompt code block is what gets pasted into the n8n node. Record the prompt version used in every test row of docs/EVIDENCE_LOG.md.
- Incident text, image content and retrieved passages are untrusted data. Every prompt tells the model to ignore instructions found inside them.
- JSON keys and enum values are always English. The language of free text follows the incident language, and the report follows output_language.
- Sources are tagged everywhere: report, image, knowledge_base, model_inference. This is what lets the final report separate what was reported, observed, retrieved and assessed.

## Data contract between agents

1. n8n receives: incident_text, image (optional), output_language (en or fr), generated_at.
2. Incident Understanding: incident_text in, incident JSON out.
3. In parallel:
   - Vision: image + incident_text in, vision JSON out. If there is no image, n8n sets vision to null and skips the call.
   - RAG: incident JSON in, queries out, then /search for each query using rag_topic, then the synthesis prompt, knowledge JSON out. If retrieval returns nothing, n8n sets knowledge to {"relevant_guidance": [], "coverage": "none"} without calling the LLM.
4. Risk Assessment: incident JSON, vision JSON or null, knowledge JSON in, risk JSON out.
5. Report: all four plus output_language and generated_at in, markdown out.

## Model settings

Ask for JSON output mode on the JSON agents (response_mime_type set to application/json in generationConfig, as shown in the Gemini generateContent reference on 2026-10-15). Do not rely on a schema alone, validate the values in the workflow too.

Temperature: the Gemini docs say Gemini 3.6 and newer models ignore a custom temperature. If you use gemini-3.8-flash, do not send temperature, and expect some run to run variation. Run each fixed test incident at least twice and record whether the output changed. If you pick an older model that accepts temperature, use a low value (0 to 0.2) for the JSON agents.

Record the real model name and settings in docs/EVIDENCE_LOG.md.

## Severity scale

The scale used in the Incident Understanding and Risk prompts (low, moderate, high, critical) is our own working scale for this prototype. It is not an official standard. Say this in the report and the presentation.

## Iteration protocol (this is the evidence for section 3 of the presentation)

1. Run each prompt on the fixed incidents in eval/incidents/.
2. Save the raw output. Mark each as correct, partly wrong or wrong, and say why.
3. When a prompt fails, add an entry to CHANGELOG.md with the failing input, the actual bad output, the change, and the actual output after the change.
4. Create the next version file. Keep at least one before and after example per key prompt.

Each prompt file ends with hypotheses to test. They are things that might go wrong, not observed failures. Move one to CHANGELOG.md only after you see it happen.
