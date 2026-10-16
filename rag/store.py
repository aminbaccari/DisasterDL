"""ChromaDB storage. One collection per chunking strategy, cosine distance."""
import os
from pathlib import Path

import chromadb

from rag.metrics import entry_ids

DB_PATH = Path(os.getenv("CHROMA_PATH", str(Path(__file__).resolve().parent / "chroma_db")))


def _client():
    return chromadb.PersistentClient(path=str(DB_PATH))


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
