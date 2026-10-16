"""RAG HTTP service called by n8n.

Run from the project root:
    uvicorn rag.service:app --port 8010

From the n8n container, the service is reachable at http://host.docker.internal:8010
(see docker-compose.yml).
"""
import os

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from backend.validate import router as validate_router
from rag import chunking, embedder, store

# Set DEFAULT_STRATEGY in .env after the chunking evaluation decides which is better.
DEFAULT_STRATEGY = os.getenv("DEFAULT_STRATEGY", "fixed")

app = FastAPI(title="DisasterAI RAG service")
# One process and one port for n8n: /search (retrieval) and /validate (guardrails on the report).
app.include_router(validate_router)


class SearchRequest(BaseModel):
    query: str
    k: int = 4
    topic: str | None = None  # fire, flood, structural, general. Optional filter.
    strategy: str | None = None


@app.get("/health")
def health():
    return {"status": "ok", "default_strategy": DEFAULT_STRATEGY, "embedding_model": embedder.model_name()}


@app.post("/search")
def search(req: SearchRequest):
    query = req.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="query is empty")
    if not 1 <= req.k <= 20:
        raise HTTPException(status_code=400, detail="k must be between 1 and 20")
    strategy = req.strategy or DEFAULT_STRATEGY
    if strategy not in ("fixed", "section"):
        raise HTTPException(status_code=400, detail="strategy must be fixed or section")

    topic = req.topic if req.topic in chunking.TOPICS else None
    try:
        results = store.search(embedder.embed_queries([query])[0], strategy, k=req.k, topic=topic)
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"index not available for strategy {strategy}. Run: python -m rag.ingest ({exc})",
        )
    return {
        "query": query,
        "strategy": strategy,
        "topic_filter_applied": topic,
        "n_results": len(results),
        "results": results,
    }
