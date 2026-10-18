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


def balance_by_language(candidates, k):
    """Pick k results from candidates (sorted by score, best first) so that each language present keeps at least k // 2 slots.

    D12 (2026-10-17): after French translations were added, a French query ranked French entries first even when the answer
    existed only in an English entry, and pushed it out of the top 5. The reserved slots keep the best entries of the other
    language in the list; the result is still sorted by score, and for k = 1 nothing changes."""
    if k < 2:
        return candidates[:k]
    reserve = k // 2
    chosen = []
    for lang in sorted({c["language"] for c in candidates}):
        chosen += [c for c in candidates if c["language"] == lang][:reserve]
    for c in candidates:
        if len(chosen) >= k:
            break
        if c not in chosen:
            chosen.append(c)
    return sorted(chosen, key=lambda c: -c["score"])[:k]


def search(query_embedding, strategy, k=5, topic=None, balance_languages=False):
    collection = get_collection(strategy)
    where = {"topic": topic} if topic else None
    n = k
    if balance_languages:
        try:
            n = min(k * 4, collection.count())
        except Exception:
            n = k * 4
    res = collection.query(query_embeddings=[query_embedding], n_results=max(n, 1), where=where)
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
    if balance_languages:
        results = balance_by_language(results, k)
    return results
