"""Knowledge-base retrieval: dense search in Chroma with metadata filtering and a score threshold.

The retriever is decoupled from generation: it only returns passages with their provenance.
An empty result means nothing relevant enough was found, which the downstream agents must
report instead of falling back on the LLM's general knowledge.

Pipeline (each step optional except the first):
    1. dense candidates per query vector (cosine, ``disaster_type`` filter)
    2. multi-query fusion: several query vectors (e.g. raw report + LLM rewrite) are merged
       with reciprocal rank fusion (RRF)
    3. similarity threshold on the bi-encoder cosine score
    4. cross-encoder reranking of the candidates
    5. per-source cap, so one long document cannot fill the whole top-k
    6. top-k

Usage:
    python -m src.rag.retriever "water is entering houses" --type flood -k 5 [--rerank] [--max-per-source 2]
"""

import argparse
from collections.abc import Sequence
from functools import lru_cache

from src.config import get_settings
from src.rag.embeddings import get_embedder
from src.rag.ingest import collection_name
from src.schemas import IncidentType, RetrievedChunk
from src.utils.logging_utils import get_logger

logger = get_logger(__name__)

FILTERABLE_TYPES = {IncidentType.FIRE, IncidentType.FLOOD, IncidentType.STRUCTURAL}
RRF_K = 60  # standard constant of reciprocal rank fusion
DEFAULT_CANDIDATES = 30  # candidate pool when fusion, reranking or the per-source cap is used


@lru_cache
def _collection(name: str):
    import chromadb

    settings = get_settings()
    client = chromadb.PersistentClient(path=str(settings.resolve(settings.chroma_path)))
    return client.get_collection(name)


def build_filter(disaster_type: str | None) -> dict | None:
    """Chroma ``where`` filter: the incident's type plus cross-hazard ("general") documents.

    No filter is applied when the type is unknown/other, so nothing is excluded by mistake.
    """
    if disaster_type in FILTERABLE_TYPES:
        return {"disaster_type": {"$in": [str(disaster_type), "general"]}}
    return None


def _dense_candidates(vector: list[float], n: int, name: str, where: dict | None) -> list[RetrievedChunk]:
    result = _collection(name).query(query_embeddings=[vector], n_results=n, where=where)
    return [
        RetrievedChunk(
            text=text,
            chunk_id=chunk_id,
            source_id=meta["source_id"],
            title=meta["title"],
            page=meta["page"],
            page_end=meta.get("page_end"),
            heading=meta.get("heading", ""),
            disaster_type=meta["disaster_type"],
            language=meta["language"],
            reliability=meta["reliability"],
            score=round(1.0 - distance, 4),  # Chroma returns cosine distance
        )
        for chunk_id, text, meta, distance in zip(
            result["ids"][0], result["documents"][0], result["metadatas"][0], result["distances"][0]
        )
    ]


def rrf_fuse(ranked_lists: Sequence[list[RetrievedChunk]], k_rrf: int = RRF_K) -> list[RetrievedChunk]:
    """Reciprocal rank fusion: score(c) = sum over lists of 1 / (k_rrf + rank of c).

    Rank-based, so lists whose similarity scores live on different scales can be merged. The
    fused chunk keeps its best cosine score, which the threshold is applied to.
    """
    fused: dict[str, float] = {}
    best: dict[str, RetrievedChunk] = {}
    for ranked in ranked_lists:
        for rank, chunk in enumerate(ranked, 1):
            fused[chunk.chunk_id] = fused.get(chunk.chunk_id, 0.0) + 1.0 / (k_rrf + rank)
            if chunk.chunk_id not in best or chunk.score > best[chunk.chunk_id].score:
                best[chunk.chunk_id] = chunk
    return [best[cid] for cid in sorted(fused, key=fused.get, reverse=True)]


def cap_per_source(chunks: list[RetrievedChunk], max_per_source: int) -> list[RetrievedChunk]:
    """Keep the ranking but at most ``max_per_source`` chunks from each document."""
    counts: dict[str, int] = {}
    kept = []
    for chunk in chunks:
        if counts.get(chunk.source_id, 0) < max_per_source:
            kept.append(chunk)
            counts[chunk.source_id] = counts.get(chunk.source_id, 0) + 1
    return kept


def search(
    vectors: Sequence[list[float]],
    k: int | None = None,
    strategy: str = "structure",
    disaster_type: str | None = None,
    threshold: float | None = None,
    contextual_header: bool = True,
    model: str | None = None,
    max_per_source: int | None = None,
    rerank_query: str | None = None,
    candidates: int = DEFAULT_CANDIDATES,
) -> list[RetrievedChunk]:
    """Core retrieval over one or more already embedded queries (see module docstring).

    Args:
        vectors: Query embeddings; more than one triggers reciprocal rank fusion.
        k: Number of chunks returned (default: ``TOP_K`` from config).
        strategy: Chunking strategy collection to search ("fixed" or "structure").
        disaster_type: Incident type for the metadata filter; None disables filtering.
        threshold: Minimum cosine similarity; chunks below it are dropped.
        contextual_header: Search the collection built with (True) or without contextual headers.
        model: Embedding model of the collection (default: configured model).
        max_per_source: Maximum number of chunks from the same document.
        rerank_query: Query text for cross-encoder reranking; None disables reranking.
        candidates: Candidate pool size when fusion, reranking or the cap is used.
    """
    k = k or get_settings().top_k
    extended = len(vectors) > 1 or rerank_query is not None or max_per_source is not None
    n = max(candidates, k) if extended else k
    name = collection_name(strategy, contextual_header, model)
    where = build_filter(disaster_type)
    lists = [_dense_candidates(vector, n, name, where) for vector in vectors]
    chunks = lists[0] if len(lists) == 1 else rrf_fuse(lists)
    if threshold is not None:
        chunks = [c for c in chunks if c.score >= threshold]
    if rerank_query is not None and chunks:
        from src.rag.reranker import get_reranker

        scores = get_reranker().score(rerank_query, [c.text for c in chunks])
        chunks = [c for _, c in sorted(zip(scores, chunks), key=lambda pair: pair[0], reverse=True)]
    if max_per_source is not None:
        chunks = cap_per_source(chunks, max_per_source)
    return chunks[:k]


def retrieve_by_vector(
    vector: list[float],
    k: int | None = None,
    strategy: str = "structure",
    disaster_type: str | None = None,
    threshold: float | None = None,
    contextual_header: bool = True,
    **options: object,
) -> list[RetrievedChunk]:
    """Top-``k`` chunks for one already embedded query (``options`` are passed to ``search``)."""
    return search([vector], k, strategy, disaster_type, threshold, contextual_header, **options)


def retrieve(
    query: str,
    k: int | None = None,
    strategy: str = "structure",
    disaster_type: str | None = None,
    threshold: float | None = None,
    contextual_header: bool = True,
    extra_queries: Sequence[str] = (),
    rerank: bool = False,
    max_per_source: int | None = None,
    model: str | None = None,
) -> list[RetrievedChunk]:
    """Embed ``query`` (and ``extra_queries``, fused with RRF) and return the top-``k`` chunks."""
    embedder = get_embedder(model)
    vectors = [embedder.embed_query(q) for q in (query, *extra_queries)]
    chunks = search(
        vectors, k, strategy, disaster_type, threshold, contextual_header,
        model=model, max_per_source=max_per_source, rerank_query=query if rerank else None,
    )
    logger.info("Retrieved %d chunks for %r (strategy=%s, type=%s)", len(chunks), query[:60], strategy, disaster_type)
    return chunks


def main() -> None:
    """Command-line entry point for manual retrieval checks."""
    parser = argparse.ArgumentParser(description="Query the DisasterAI knowledge base.")
    parser.add_argument("query")
    parser.add_argument("-k", type=int, default=5)
    parser.add_argument("--strategy", default="structure", choices=["fixed", "structure"])
    parser.add_argument("--type", dest="disaster_type", default=None, choices=[t.value for t in IncidentType])
    parser.add_argument("--threshold", type=float, default=None)
    parser.add_argument("--rerank", action="store_true")
    parser.add_argument("--max-per-source", type=int, default=None)
    args = parser.parse_args()
    chunks = retrieve(
        args.query, args.k, args.strategy, args.disaster_type, args.threshold,
        rerank=args.rerank, max_per_source=args.max_per_source,
    )
    for rank, chunk in enumerate(chunks, 1):
        print(f"\n[{rank}] {chunk.score:.3f}  {chunk.source_id} p.{chunk.page}  {chunk.heading}")
        print(f"    {chunk.text[:300]}")


if __name__ == "__main__":
    main()
