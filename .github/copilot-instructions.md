Project: DisasterAI, a multi-agent system that turns an incident report (text + optional image) into a preliminary disaster assessment (forest fire, flood, structural emergency). University project (Advanced Deep Learning).
Stack: Python 3.11, FastAPI, ChromaDB, Pydantic v2, n8n as orchestrator calling our FastAPI endpoints.
Agents: incident, vision, knowledge (RAG), risk, verifier, report.
Rules:
- Every agent is a pure function with typed Pydantic input/output defined in src/schemas.py.
- Prompts are never hard-coded: load them from prompts/<name>/v<N>.yaml via src/llm/prompt_loader.py.
- LLM and VLM calls go through src/llm/client.py (provider-agnostic, configurable in config.py).
- Never invent facts: keep reported facts, image observations, retrieved guidance, and AI inference in separate fields. Use null/empty lists for unknowns.
- Always validate LLM JSON output with Pydantic; on failure retry once, then return a structured error.
- Add type hints, docstrings, logging, and a pytest test for each module. Keep code simple and readable.