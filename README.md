# DisasterAI

Multi-agent AI assistant for disaster assessment and response. Final project, Advanced Deep Learning (AI Automation), class 5DS1, 2026-2027.

DisasterAI is a decision-support prototype. It does not replace emergency services, dispatch vehicles or make life-critical decisions.

## Pipeline

Incident (text + optional image) -> n8n webhook -> Incident Understanding Agent -> Vision Agent and RAG Agent (parallel) -> Risk Assessment Agent -> Report Agent -> final report.

Scope of version 1: forest fires, floods, structural or urban emergencies.

## Stack

- Automation: n8n (self-hosted with Docker)
- LLM and vision: Gemini Flash, free tier (exact model set in .env)
- Embeddings: multilingual-e5 via sentence-transformers (local)
- Vector store: ChromaDB (local)
- RAG service: Python FastAPI, called by n8n through an HTTP Request node
- Language: Python, version control with Git

## Repository layout

- prompts/ one folder per agent, one file per prompt version, plus CHANGELOG.md
- rag/corpus/ source documents (en, fr) and rag/eval/ test queries and results
- vision/test_images/ test images per disaster type
- n8n/ exported workflow JSON
- eval/incidents/ fixed end-to-end test incidents, eval/results/ logged outputs
- docs/ diagrams, screenshots, evidence log, report drafts
- scripts/ helper scripts, including check_env.py

## Setup

1. Install Docker and Python 3.10 or newer.
2. Copy .env.example to .env and fill in GEMINI_API_KEY (free key from Google AI Studio).
3. Create a virtual environment and install dependencies:

   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt

4. Start n8n:

   docker compose up -d

   Then open http://localhost:5678 and create the owner account.
5. Run the environment check:

   python scripts/check_env.py

   Add --skip-embeddings to skip the first-time embedding model download.

## RAG commands

Run from the project root, after adding documents to rag/corpus/en and rag/corpus/fr and listing them in rag/corpus/SOURCES.md.

- Build the index with both chunking strategies: python -m rag.ingest --strategy both
- Evaluate retrieval: copy rag/eval/queries_template.csv to rag/eval/queries.csv, fill in 15 to 20 queries, then run python -m rag.evaluate --strategy both
- Start the service for n8n: uvicorn rag.service:app --port 8000, then POST to /search with {"query": "...", "k": 4, "topic": "flood"}. n8n in Docker reaches it at http://host.docker.internal:8000
- Run the unit tests: python -m unittest discover -s rag/tests -t .

The first ingest downloads the embedding model, so it needs internet access.

## End-to-end tests

Once the n8n workflow exists, run the six fixed incidents in eval/incidents/ (see its README for the images you need to collect first):

python scripts/run_incidents.py --url <n8n webhook url> --runs 2

Raw outputs and a summary.csv are saved in eval/results/<timestamp>/.

## Evidence rules

Every number in the report and slides must come from a run we logged. Use docs/EVIDENCE_LOG.md for prompt iterations, failures and test results as we build, not at the end.

## Team

Four members. Roles: architecture and coordination, RAG, multi-agent system, prompt engineering, multimodality, n8n and integration. Everyone must be able to explain every part of the system.
