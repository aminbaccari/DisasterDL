# DisasterAI

Multi-agent AI assistant for disaster assessment and response. Final project, Advanced Deep Learning (AI Automation), class 5DS1, 2026-2027.

DisasterAI is a decision-support prototype. It does not replace emergency services, dispatch vehicles or make life-critical decisions.

## Status (2026-10-17)

Built and tested offline: the knowledge base (78 entries, English and French), retrieval, agent output schemas, the `/validate` guardrails, the model fallback chain, the n8n workflow generator. Run in a test n8n with MOCK agents (all six incidents, seven failure paths) and with real models for a few runs. **Not yet shown:** a clean batch of the six incidents with images on real models. Free-tier quotas ran out repeatedly, and the Vision step almost never ran. Prompt versions incident v2, report v4, knowledge v2 and risk v2 are drafts with partial evidence. The honest list is in `docs/EVIDENCE_LOG.md`, `docs/SPRINT_STATUS.md` and `docs/BOTTLENECKS.md`.

## Pipeline

Incident (text and optional image) -> n8n webhook -> Incident Understanding Agent -> Vision Agent and RAG Agent (parallel) -> Merge -> Risk Assessment Agent -> Report Agent -> `/validate` (one repair pass) -> final report.

Scope of version 1: forest fires, floods, structural or urban emergencies. Languages: English and French.

```
client --multipart--> n8n webhook
                         |
                  Incident Understanding --(unclear)--> "more information needed"
                         |
            +------------+-------------+
            |                          |
         Vision                  RAG queries -> /search -> Knowledge synthesis
            |                          |
            +-----------Merge----------+
                         |
                  Risk -> Report -> /validate -> (repair once) -> response
```

n8n owns the orchestration (branches, parallel paths, retries, error workflow). Every agent is a pair of nodes: a Set node holding the versioned prompt and an HTTP node calling `POST /llm`. Python stays small: one FastAPI service with `/search` (retrieval), `/validate` (guardrails) and `/llm` (model fallback chain).

## Stack

- Automation: n8n, self-hosted with Docker
- Models: a fallback chain over Gemini, Groq and OpenRouter free tiers (`LLM_CHAIN` in `.env`, `backend/llm_chain.py`). Each response lists the model that answered every step (`models_used`). Image calls can use their own `VISION_CHAIN` (local Ollama, Hugging Face Inference Providers, then cloud models). A local `qwen3-vl:4b-instruct` runs in Docker with the GPU (see `docs/VISION_ARCHITECTURE.md`); the Hugging Face provider is coded and unit-tested but not tried (no token).
- Embeddings: multilingual-e5-small via sentence-transformers (local)
- Vector store: ChromaDB (local), section chunking (chosen after evaluation)
- Service: Python FastAPI on port 8010
- Language: Python, version control with Git

## Repository layout

- `prompts/` one folder per agent, one file per prompt version, `CHANGELOG.md`
- `rag/` retrieval service, corpus (`rag/corpus/en`, `fr`), evaluation queries; `rag/knowledge_base/` is the knowledge base build and QA tools
- `backend/` agent output schemas, `/validate`, the model chain, the MOCK Gemini, tests
- `n8n/workflows/` generated workflow JSON (never edit by hand)
- `eval/incidents/` six fixed test incidents, `eval/results/` raw outputs of every run
- `vision/test_images/` four CC BY test images with attribution
- `ui/` the Streamlit test console (client, rendering, saved runs, samples)
- `scripts/` helper and test scripts
- `docs/` plans, evidence log, status, proposals

## Setup

1. Install Docker and Python 3.10 or newer.
2. Copy `.env.example` to `.env`. Fill in at least one provider key: `GEMINI_API_KEY` (Google AI Studio), `GROQ_API_KEY` (console.groq.com), `OPENROUTER_API_KEY` (openrouter.ai). Create the keys yourself and never commit `.env`. Set `LLM_CHAIN` to models you verified (below).
3. Create a virtual environment and install dependencies:

   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt

4. Start n8n:

   docker compose up -d

   Then open http://localhost:5678 and create the owner account.
5. Run the environment check: `python scripts/check_env.py` (add `--skip-embeddings` to skip the first embedding model download).
6. Check the models of the chain: `python scripts/llm_ping.py --list groq`, then `python scripts/llm_ping.py --json` (one call per model of `LLM_CHAIN`, never prints a key).

Local vision model: run the `ollama/ollama` Docker image with `--gpus all`, pull `qwen3-vl:4b-instruct` (not the thinking tag `qwen3-vl:4b`) and set `VISION_CHAIN=ollama:qwen3-vl:4b-instruct,...`; exact commands in `docs/VISION_ARCHITECTURE.md`. Keep several GB free on C: or Docker fails.

Notes from the development machine (Windows 11): if Python reports certificate errors, `pip install truststore` (the scripts use it when present); if importing sentence-transformers fails with a Keras 3 message, set `USE_TF=0` and `TRANSFORMERS_NO_TF=1`; with no internet set `HF_HUB_OFFLINE=1` after the first model download. Port 8000 was taken by another application, so the service uses 8010.

## Run it

1. Build the index (first run downloads the embedding model): `python -m rag.ingest --strategy both`
2. Start the service for n8n: `uvicorn rag.service:app --host 0.0.0.0 --port 8010`. It serves `/search`, `/validate`, `/llm`, `/llm/status` and `/health`. n8n in Docker reaches it at `http://host.docker.internal:8010`.
3. Generate and import the workflow: `python scripts/build_workflow.py`, then in n8n **Import from file** `n8n/workflows/disasterai.json` and `disasterai_error.json`. The default build uses the draft prompts incident v2 and report v4. For the tested prompts: `--prompt incident=incident_understanding/v1.md --prompt report=report/v3.md`.
4. Send an incident:

   curl -X POST "http://localhost:5678/webhook/incident" -F "incident_text=Smoke is rising from the hills behind the village." -F "output_language=en" -F "image=@vision/test_images/fire_01.jpg;type=image/jpeg"

   The image part needs its own Content-Type (`;type=image/jpeg`), otherwise n8n delivers it as text and the Vision step is skipped (the workflow now says so in `degraded_steps`).

The response is JSON: `status` (ok, needs_more_information, degraded, flagged, rejected), `report`, `report_markdown`, `validation`, `knowledge_coverage`, `degraded_steps`, `models_used`, `prompt_versions`.

### Test console (UI)

A Streamlit screen to send an incident to the n8n webhook and read the result: `streamlit run ui/app.py` (opens on http://localhost:8501). Pick the n8n instance in the sidebar (default `http://localhost:5678/webhook/incident`, the one `docker compose up -d` publishes), check the health lights (n8n, RAG service, model chains, local vision model, disk), choose a fixed incident or write your own, add a photo, press Run. The result shows a plain-language status, the report with the source of each statement and the passage behind each recommendation, the image next to the report, the real pipeline steps (model, seconds, fallbacks, degraded steps, first validation problems) and the raw JSON. Every run is saved in `eval/results/ui_runs/` and can be compared in the History tab. n8n answers only when the whole run ends, so the progress bar is a timer. To try the screen without spending model quota: `python scripts/replay_webhook.py` and pick "Replay of saved answers" (it replays saved real answers and is labelled MOCK; add `?mode=degraded`, `flagged`, `rejected`, `error500`... in a custom URL to see the failure paths). Tests: `backend/tests/test_ui.py` and `test_ui_app.py`.

## Tests

- Unit tests (no network, no model): `python -m unittest discover -s rag/tests -t .` and `python -m unittest discover -s backend/tests -t .` (21 and 84 tests on 2026-10-17)
- Retrieval: `python -m rag.evaluate --queries rag/eval/queries_v2.csv --strategy both` (add `--use-topic-filter`)
- Contracts and workflow: `python scripts/check_contracts.py`, `python scripts/check_workflow.py` (static, does not run n8n)
- Offline replay with MOCK agents: `python scripts/replay_mock.py`; failure paths with a MOCK Gemini: `python scripts/failure_paths_mock.py --url <webhook>`
- Real end-to-end, six incidents: `python scripts/run_incidents.py --url <webhook> --runs 2` then read each report with `python scripts/show_run.py <results folder> <incident id> <run>` and score `manual_checks`
- Baseline, one prompt instead of the pipeline: `python scripts/baseline_single_prompt.py --runs 2`
- Prompt before and after: `python scripts/before_after.py` (pipeline) and `python scripts/report_ab.py` (paired, one pinned model). Both need fresh quotas, see `docs/NEXT_STEPS.md`.

## Known limits

- Free tiers: daily and per-minute quotas stop long runs. A pipeline run is about 7 model calls.
- The Vision step needs a vision-capable model. `VISION_CHAIN` is implemented and the local model works (9 to 14 s per image warm, false observations that echo the report text were seen), see `docs/VISION_ARCHITECTURE.md`.
- Fire guidance is limited (FI-01 says what the knowledge base does not cover). Tunisian guidance is one news report of an ONPC communique.
- French fire entries FI-21 to FI-26 are team translations, not reviewed by an outside reader. Four OCR-only flood pages were not re-verified on the last QA run.
- The severity scale (low, moderate, high, critical, undetermined) is a working scale of this prototype, not an official standard.

## Documents

- `docs/EVIDENCE_LOG.md` what was run, results, failures, limitations (every number comes from here)
- `docs/SPRINT_STATUS.md`, `docs/SPRINT_PLAN.md`, `docs/NEXT_STEPS.md` plan and status
- `docs/BOTTLENECKS.md` bottlenecks and proposed fixes
- `docs/VISION_ARCHITECTURE.md` proposal for a separate vision model
- `docs/N8N_WORKFLOW_PLAN.md`, `docs/CONTRACT_MISMATCHES.md`, `docs/RAG_CORPUS_PLAN.md`
- `prompts/README.md` data contract between agents, `prompts/CHANGELOG.md` prompt iterations
- `vision/test_images/SOURCES.md`, `rag/corpus/SOURCES.md` licences and sources

## Evidence rules

Every number in the report and slides must come from a run we logged. Results from the MOCK Gemini are labelled MOCK and say nothing about model quality. A prompt version is never edited after it has been tested: write the next version and a CHANGELOG entry with the failing input.

## Team

Four members. Roles: architecture and coordination, RAG, multi-agent system, prompt engineering, multimodality, n8n and integration. Everyone must be able to explain every part of the system.
