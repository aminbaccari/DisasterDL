# Prompt changelog

One entry per prompt change. Fill it in when it happens. This is the evidence for the before and after examples.

Template:

## <agent> v<old> to v<new> (YYYY-MM-DD)
- Test input that failed:
- What went wrong (paste the actual output):
- Change made to the prompt:
- Result after the change (paste the actual output):
- Technique involved (role, JSON schema, few-shot, constraint, other):

## Entries

(none yet)

## rag_query synthesis v1 to v2 (2026-10-16)
- Test input that failed: not a model input. Contract check `python scripts/check_contracts.py` on an output shaped as `v1_synthesis.md` documents it (same fields, citation without entry id).
- What went wrong (actual validator output): `relevant_guidance/0/citation : 'entry_id' is a required property`. The v1 citation (chunk_id, source, page) cannot be checked by /validate against retrieved entry ids, and page is always 1 for knowledge base files.
- Change made to the prompt: citation now includes entry_id, taken from the passage's entry_ids list (rule 2 and the output schema). File: prompts/rag_query/v2_synthesis.md.
- Result after the change: the documented v2 shape validates (no errors in the same script). NOT yet run on a model, so it is not known whether the model uses valid entry ids. /validate will check that the entry id is in the cited chunk.
- Technique involved: JSON schema.

## risk v1 to v2 (2026-10-16)
- Test input that failed: same contract check, output shaped as `risk_assessment/v1.md` documents it.
- What went wrong (actual validator output): `considerations/0/citation : 'entry_id' is a required property`.
- Change made to the prompt: considerations copy the knowledge citation unchanged including entry_id. File: prompts/risk_assessment/v2.md.
- Result after the change: the documented v2 shape validates. NOT yet run on a model.
- Technique involved: JSON schema.

## report v1/v2 to v3 (2026-10-16)
- Test input that failed: not a model input. Contract check of a Markdown string (what report v1 and v2 return) against backend/schemas/report.schema.json.
- What went wrong (actual validator output): `(root) : '# Preliminary incident assessment ...' is not of type 'object'`. /validate needs structured recommendations with entry ids, a location field and a no-guidance statement.
- Change made to the prompt: v3 returns one JSON object that includes report_markdown. It also folds in the partial-coverage wording drafted in v2 (rule 6) and adds the rules on location, dispatch and entry, injected text and numbers. File: prompts/report/v3.md.
- Result after the change: the documented v3 shape validates. NOT yet run on a model. v2 stays as an untested draft and is not used by the workflow.
- Technique involved: JSON schema, constraint.
