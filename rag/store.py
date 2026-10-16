"""ChromaDB storage. One collection per chunking strategy, cosine distance."""
import os
import threading
from pathlib import Path

import chromadb

from rag.metrics import entry_ids

DB_PATH = Path(os.getenv("CHROMA_PATH", str(Path(__file__).resolve().parent / "chroma_db")))


_CLIENT = None
_LOCK = threading.Lock()


def _client():
    """One shared client. Opening a new PersistentClient per call failed under parallel requests from n8n
    ("Could not connect to tenant default_tenant", seen 2026-10-16 with three simultaneous /search calls)."""
    global _CLIENT
    with _LOCK:
        if _CLIENT is None:
            _CLIENT = chromadb.PersistentClient(path=str(DB_PATH))
        return _CLIENT


def collection_name(strategy):
    return f"disasterai_{strategy}"


def reset_collection(strategy):
    client = _client()
    try:
        client.delete_collection(collection_name(strategy))
    except Exception:
        pass
    return client.create_collection(collection_name(strategy), metadata={"hnsw:space": "cosine"})


def get_collection(strategy):
    return _client().get_collection(collection_name(strategy))


def search(query_embedding, strategy, k=5, topic=None):
    collection = get_collection(strategy)
    where = {"topic": topic} if topic else None
    res = collection.query(query_embeddings=[query_embedding], n_results=k, where=where)
    results = []
    for i, chunk_id in enumerate(res["ids"][0]):
        meta = res["metadatas"][0][i]
        results.append(
            {
                "chunk_id": chunk_id,
                "text": res["documents"][0][i],
                "source": meta["source"],
                "page": meta["page"],
                "section": meta["section"],
                "topic": meta["topic"],
                "language": meta["language"],
                "score": round(1 - res["distances"][0][i], 4),
            }
        )
        results[-1]["entry_ids"] = entry_ids(results[-1])
    return results
