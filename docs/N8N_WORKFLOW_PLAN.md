# n8n workflow plan (draft v1, 2026-10-15)

Nothing in this plan has been built or run yet. Items I could not confirm from the documentation are listed at the end and marked "confirm" in the text.

## Design choices

- One workflow, triggered by a webhook, that runs from incident to final report with no manual step.
- All LLM and vision calls go through the HTTP Request node to the Gemini generateContent endpoint. Reason: the n8n Google Gemini node page does not say whether it supports a system prompt or JSON output mode, while the Gemini API reference documents both. One request template then serves all five agents. If the team prefers the n8n Gemini node, check its parameters in the editor first.
- The RAG service (FastAPI) runs on the host and is called at http://host.docker.internal:8010, which docker-compose.yml already enables.
- Every agent output is parsed and checked in a small Code node, with a safe fallback, so one bad LLM answer does not crash the run.
- The API key lives in an n8n credential (Header Auth with header name x-goog-api-key), not inside nodes, so exported workflow JSON does not leak it.

## Input contract

POST to the webhook as multipart form data:
- incident_text (required)
- output_language (en or fr, default en)
- image (optional file; formats supported by Gemini: png, jpeg, webp, heic, heif)

Test call (copy the real URL from the Webhook node, the test URL contains webhook-test and the production URL contains webhook):

curl -X POST "http://localhost:5678/webhook-test/incident" -F "incident_text=A forest fire has been reported near a residential area." -F "output_language=en" -F "image=@vision/test_images/fire_01.jpg"

The webhook accepts payloads up to 16 MB by default. Test URL runs show data in the editor. Production runs appear in the Executions tab after the workflow is published.

## Gemini request template (HTTP Request node)

Method POST, URL https://generativelanguage.googleapis.com/v1beta/models/<GEMINI_MODEL>:generateContent, authentication by the Header Auth credential, Send Body on, content type JSON, "Using JSON". Set a Timeout in milliseconds on the node.

Body expression for a text agent (JSON.stringify avoids quote and newline escaping problems):

={{ JSON.stringify({ system_instruction: { parts: { text: $('Prompt incident v1').item.json.system } }, contents: [{ role: "user", parts: [{ text: "<incident_report>\n" + $json.incident_text + "\n</incident_report>" }] }], generationConfig: { response_mime_type: "application/json" } }) }}

For the Vision agent add an image part next to the text part:

{ inline_data: { mime_type: <image mime type>, data: <base64 string> } }

The answer text is at candidates[0].content.parts[0].text. For the Report agent, leave out response_mime_type so the model returns Markdown.

Keep each system prompt in a Set node named "Prompt <agent> v1" so the prompt version is visible on the canvas and in screenshots.

## Nodes, in order

1. Webhook (Incident received). POST, Binary Property = image, respond with a Respond to Webhook node.
2. Edit Fields (Normalise). incident_text trimmed, output_language defaulting to en, has_image true or false, generated_at from the current time.
3. IF (Valid input). False path: Respond to Webhook with status 400 and a short message. True when incident_text is not empty.
4. Prompt incident v1 (Set), HTTP Request (Gemini: incident), Code (Parse incident). Parse the answer, check enum values and required keys against prompts/incident_understanding/v1.md, and on failure return the fallback {incident_type: "unclear", type_confidence: "low", initial_severity: "unknown", rag_topic: "general", parse_error: true, reported_facts: [incident_text]}.
5. Two parallel branches start here.

Branch A, vision:
   - IF (Has valid image). True when has_image and the mime type is supported.
   - True: Code (Prepare image) reads the binary as base64, HTTP Request (Gemini: vision), Code (Parse vision).
   - False: Edit Fields sets vision to null and records why (no image, or unsupported type).

Branch B, knowledge:
   - HTTP Request (Gemini: RAG queries), Code (Parse queries and split into one item per query).
   - HTTP Request (RAG search) once per query: POST http://host.docker.internal:8010/search with {"query": ..., "k": 4, "topic": <rag_topic>}.
   - Code (Merge and dedupe by chunk_id, keep the best score).
   - IF (Any passages). False: set knowledge to {"relevant_guidance": [], "ignored_chunks": [], "coverage": "none", "gaps": ["No passages retrieved"]} with no LLM call. True: HTTP Request (Gemini: synthesis), Code (Parse knowledge).

6. Merge (Combine, by position). Each branch outputs exactly one item, and the node waits for both inputs. Then Code (Assemble) builds one object with incident, vision, knowledge, output_language and generated_at, reading the incident from the "Parse incident" node by name.
7. Prompt risk v1 (Set), HTTP Request (Gemini: risk), Code (Parse risk).
8. Prompt report v1 (Set), HTTP Request (Gemini: report, Markdown).
9. Respond to Webhook. Return JSON with exactly these keys, which scripts/run_incidents.py reads: incident_type (from the Incident Understanding agent), severity (from the Risk agent), report_markdown, degraded_steps (list of steps that ran in fallback mode), prompt_versions (for example {"incident": "v1", "risk": "v1"}).

## Error handling plan

| Failure | How it is detected | Behaviour |
|---------|--------------------|-----------|
| Missing or empty incident_text | IF (Valid input) | 400 response, nothing else runs |
| Unsupported or missing image | IF (Has valid image) | Continue without vision, say so in the report |
| Gemini error or rate limit | HTTP Request node settings: retry on fail with a wait between tries, then on error continue using the error output (confirm exact names in the node Settings tab) | Fallback object for that step, flagged as degraded |
| Gemini returns invalid JSON or wrong values | Parse Code node | Fallback object with parse_error true, one entry in the degraded list |
| RAG service down or slow | HTTP Request timeout and error output | knowledge set to none with the gap "knowledge base unavailable" |
| Empty retrieval | IF (Any passages) | knowledge set to none, no LLM call, no invented guidance |
| Image unusable | Vision agent returns image_usable false | Report states the image could not be used |
| Anything unhandled | Error workflow (set in the workflow Settings, first node is an Error Trigger) | Log execution id and error message |

The degraded list is the evidence for the "error-handling mechanisms" part of section 7. Trigger each failure on purpose once (wrong API key, RAG service stopped, no image, vague text) and screenshot the run.

## Build order (test after every step)

1. Webhook and Respond to Webhook that echoes the input. Run the curl command.
2. Incident Understanding with parse and fallback.
3. RAG branch, using the FastAPI service once the corpus is indexed.
4. Vision branch.
5. Merge, Risk, Report.
6. Error handling and the deliberate failure tests.
7. Download the workflow JSON from n8n into n8n/disasterai_workflow_v1.json (check it contains no API key) and commit it.

## Evidence to capture for the presentation

- Screenshot of the full canvas, with the two parallel branches visible.
- One successful execution per disaster type, with the final report.
- One execution per deliberate failure.
- Time per run, noted from the Executions tab, with the model name used.
- Prompt version numbers per run, in docs/EVIDENCE_LOG.md.

## Not confirmed yet

- How the webhook exposes multipart fields and the uploaded file (expected: text fields in the body, the file as binary under the name image). Check in the first test execution.
- The exact names and options of the node Settings for retries and error output.
- The Code node call used to read the image as base64 (expected: this.helpers.getBinaryDataBuffer). Check in the editor.
- Which Gemini models your free-tier key can call, and the free-tier request limits. The rate limits page points to Google AI Studio for the numbers, and the docs list Tunisia as a supported country.
- Whether temperature is ignored by your chosen model (the docs say 3.6 and newer ignore it). Run each test incident twice to see the variation.
- Gemini also documents a newer Interactions endpoint. This plan uses generateContent, which the API reference still documents as current. Recheck if requests start failing.

## Sources

- n8n Webhook node: https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.webhook/
- n8n Merge node: https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.merge/
- n8n error handling: https://docs.n8n.io/flow-logic/error-handling/
- n8n HTTP Request node: https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.httprequest/
- n8n Google Gemini node: https://docs.n8n.io/integrations/builtin/app-nodes/n8n-nodes-langchain.googlegemini/
- Gemini generateContent reference: https://ai.google.dev/api/generate-content
- Gemini image understanding: https://ai.google.dev/gemini-api/docs/image-understanding
- Gemini models: https://ai.google.dev/gemini-api/docs/models
- Gemini rate limits: https://ai.google.dev/gemini-api/docs/rate-limits
- Gemini available regions: https://ai.google.dev/gemini-api/docs/available-regions
