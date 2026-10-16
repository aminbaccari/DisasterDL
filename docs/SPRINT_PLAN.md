# Sprint plan (2026-10-16)

## Goal
Take DisasterAI from "corpus indexed" to "pipeline built, guarded and tested", with honest evidence. n8n owns orchestration (one node per agent, parallel Vision and RAG branches, merge, retries, error workflow). Python stays small: `/search` (exists) and `/validate` (new). No agent graph, no `/assess`, no new framework.

## Tasks, in order

| Sprint | Task | Output | Done when |
|--------|------|--------|-----------|
| 1 | Blind retrieval queries | `rag/eval/queries_v2.csv` (16 to 20 queries with expected entry ids), committed before any run | file committed, written from entry needs and fixed incidents |
| 1 | Entry-id matching | `rag/metrics.py`, `rag/evaluate.py`, tests | tests pass |
| 1 | Retrieval evaluation | fixed vs section, k=1,3,5, hit rate, MRR, logged in `docs/EVIDENCE_LOG.md` | numbers come from a logged run, misses analysed |
| 2 | Agent contracts | `backend/schemas/*.schema.json`, examples, mismatch list | schemas validate the examples |
| 2 | Guardrails | `backend/validate.py`, `POST /validate`, tests | one pass and one fail test per check |
| 2 | Mock harness | `backend/mock_gemini.py`, `scripts/replay_mock.py` | six incidents replayed, every result labelled MOCK |
| 3 | Workflow generator | `scripts/build_workflow.py` -> `n8n/workflows/disasterai.json` | JSON parses, nodes and connections consistent |
| 3 | Run in n8n | throwaway container on port 5679 | one real webhook run, or "not run in n8n" stated |
| 4 | Tests and evaluation | unit test counts, six incidents x 2 runs, baseline single prompt | raw outputs in `eval/results/`, manual checks scored |
| 5 | Next steps | `docs/NEXT_STEPS.md` | backlog, owners, presentation mapping |

## Acceptance criteria
- Every number in the docs traces to a raw file or a command output from a run done here.
- Mock results carry the word MOCK. Text-only runs (no test images exist) are marked as such.
- Prompts change only through a new version file plus a `prompts/CHANGELOG.md` entry that names the failing input.
- All unit tests pass before each commit.

## Not doing
Python orchestration, an `/assess` endpoint, a second LLM, embedding model or vector store, Arabic, a UI, deployment, prompt edits to make tests pass, hand edits of `rag/corpus/*_kb.md` (change `rag/knowledge_base/tools/` and rebuild), pushing to the remote.

## Decisions taken by default (team can override)
- Report agent returns JSON with the Markdown inside (new prompt v3), because `/validate` must check structured citations.
- `/validate` is a router mounted in the same FastAPI app as `/search` (one process, one port 8010).
- `/search` results gain `entry_ids` (parsed from entry headings) so citations name an entry, not a page.
- n8n is tested in a separate container on 5679. The team's n8n on 5678 is not touched.
- The KB tools live in `rag/knowledge_base/tools/` (the brief says `kb_build/`). Not moved.

## Risks
- Gemini free-tier limits or the model name in `.env` may block real runs. If so, the run stops and the log says what completed.
- No test images exist, so Vision cannot be tested on images.
- n8n multipart and binary handling is unconfirmed in the plan and may need fixes on first run.
- The first query file `rag/eval/queries.csv` was written with the entries in view, so it is not blind. It is kept and labelled as such.

## Needs the team
Approval of the report JSON format, test images with licences (`vision/test_images/`), someone to read the French text, a decision on whether the demo runs on the team's n8n instance.
