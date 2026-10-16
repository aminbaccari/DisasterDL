"""Knowledge-base ingestion: sources.csv -> extract -> chunk -> embed -> ChromaDB.

Each chunking strategy is stored in its own Chroma collection (``kb_fixed``,
``kb_structure``, ...) so the strategies can be compared on the same test queries.
Chunks are also written to ``data/processed/<collection>.jsonl`` for manual inspection,
with summary statistics in ``<collection>_stats.json``.

Usage:
    python -m src.rag.ingest --strategy structure
    python -m src.rag.ingest --strategy all
    python -m src.rag.ingest --strategy fixed --dry-run      # chunk only, no embedding
    python -m src.rag.ingest --strategy structure --no-header  # ablation: no contextual header
    python -m src.rag.ingest --strategy structure --model intfloat/multilingual-e5-small
"""

import argparse
import csv
import re
import json
import statistics
from dataclasses import asdict, dataclass
from pathlib import Path

from src.config import get_settings
from src.rag.chunkers import CHUNKERS, Chunk, ChunkingConfig
from src.rag.embeddings import TokenCounter, get_embedder, get_token_counter
from src.rag.extract import extract_pdf
from src.utils.logging_utils import get_logger

logger = get_logger(__name__)

_CHROMA_BATCH = 1000


@dataclass
class Source:
    """One row of data/sources.csv."""

    source_id: str
    title: str
    publisher: str
    year: str
    language: str
    disaster_type: str
    reliability: str
    url: str
    licence: str
    filename: str


def load_sources(csv_path: Path, raw_dir: Path) -> list[Source]:
    """Read sources.csv, skipping (with a warning) rows whose PDF is missing from ``raw_dir``."""
    with csv_path.open(encoding="utf-8", newline="") as f:
        rows = [Source(**{k: (v or "").strip() for k, v in row.items()}) for row in csv.DictReader(f)]
    available = []
    for source in rows:
        if (raw_dir / source.filename).is_file():
            available.append(source)
        else:
            logger.warning("Skipping %s: %s not found in %s", source.source_id, source.filename, raw_dir)
    return available


def collection_name(strategy: str, contextual_header: bool, model: str | None = None) -> str:
    """Name of the Chroma collection holding one chunking configuration.

    Collections built with an embedding model other than the configured default get the model
    name as a suffix (e.g. ``kb_structure_multilingual-e5-small``) so experiments never overwrite
    each other.
    """
    name = f"kb_{strategy}" + ("" if contextual_header else "_noheader")
    if model and model != get_settings().embedding_model:
        name += "_" + re.sub(r"[^A-Za-z0-9._-]", "-", model.split("/")[-1])
    return name


def build_chunks(
    source: Source, raw_dir: Path, strategy: str, counter: TokenCounter, config: ChunkingConfig
) -> list[Chunk]:
    """Extract one source PDF and chunk it with ``strategy``."""
    doc = extract_pdf(raw_dir / source.filename)
    return CHUNKERS[strategy](doc, source.title, counter, config)


def chunk_records(source: Source, chunks: list[Chunk], strategy: str) -> list[dict]:
    """Turn chunks into flat records (id, texts and Chroma-compatible metadata)."""
    records = []
    for i, chunk in enumerate(chunks):
        records.append(
            {
                "id": f"{source.source_id}:{strategy}:{i:04d}",
                "text": chunk.text,
                "embed_text": chunk.embed_text,
                "metadata": {
                    "source_id": source.source_id,
                    "title": source.title,
                    "publisher": source.publisher,
                    "year": source.year,
                    "language": source.language,
                    "disaster_type": source.disaster_type,
                    "reliability": source.reliability,
                    "page": chunk.page,
                    "page_end": chunk.page_end,
                    "heading": chunk.heading,
                    "chunk_index": i,
                    "n_tokens": chunk.n_tokens,
                    "strategy": strategy,
                },
            }
        )
    return records


def chunk_stats(records: list[dict], config: ChunkingConfig) -> dict:
    """Summary statistics used in the report (size distribution, chunks per source)."""
    tokens = sorted(r["metadata"]["n_tokens"] for r in records)
    per_source: dict[str, int] = {}
    for r in records:
        per_source[r["metadata"]["source_id"]] = per_source.get(r["metadata"]["source_id"], 0) + 1
    return {
        "n_chunks": len(records),
        "tokens_mean": round(statistics.mean(tokens), 1),
        "tokens_median": statistics.median(tokens),
        "tokens_p95": tokens[int(0.95 * (len(tokens) - 1))],
        "tokens_min": tokens[0],
        "tokens_max": tokens[-1],
        "n_over_chunk_size": sum(t > config.chunk_size for t in tokens),
        "n_under_min_tokens": sum(t < config.min_chunk_tokens for t in tokens),
        "chunks_per_source": per_source,
        "config": asdict(config),
    }


def ingest(
    strategy: str, contextual_header: bool = True, dry_run: bool = False, model: str | None = None
) -> dict:
    """Build one collection end to end and return its statistics."""
    settings = get_settings()
    raw_dir = settings.resolve(settings.raw_dir)
    processed_dir = settings.resolve(settings.processed_dir)
    processed_dir.mkdir(parents=True, exist_ok=True)
    config = ChunkingConfig(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
        min_chunk_tokens=settings.min_chunk_tokens,
        contextual_header=contextual_header,
    )
    model = model or settings.embedding_model
    name = collection_name(strategy, contextual_header, model)
    counter = get_token_counter(model)

    records: list[dict] = []
    for source in load_sources(settings.resolve(settings.sources_csv), raw_dir):
        chunks = build_chunks(source, raw_dir, strategy, counter, config)
        records.extend(chunk_records(source, chunks, strategy))
        logger.info("%s: %d chunks", source.source_id, len(chunks))
    if not records:
        raise RuntimeError("No chunks produced: check data/sources.csv and data/raw/")

    with (processed_dir / f"{name}.jsonl").open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    stats = chunk_stats(records, config)
    stats.update(collection=name, embedding_model=model)
    (processed_dir / f"{name}_stats.json").write_text(json.dumps(stats, indent=2), encoding="utf-8")

    if not dry_run:
        _store(name, records, model, strategy)
    logger.info(
        "%s: %d chunks, %s tokens on average (min %s, max %s)%s",
        name, stats["n_chunks"], stats["tokens_mean"], stats["tokens_min"], stats["tokens_max"],
        " [dry run, not embedded]" if dry_run else "",
    )
    return stats


def _store(name: str, records: list[dict], model_name: str, strategy: str) -> None:
    """Embed records and (re)create the Chroma collection ``name``."""
    import chromadb

    settings = get_settings()
    embeddings = get_embedder(model_name).embed_passages([r["embed_text"] for r in records])
    client = chromadb.PersistentClient(path=str(settings.resolve(settings.chroma_path)))
    if name in [c.name for c in client.list_collections()]:
        client.delete_collection(name)
    collection = client.create_collection(
        name, metadata={"hnsw:space": "cosine", "embedding_model": model_name, "strategy": strategy}
    )
    for start in range(0, len(records), _CHROMA_BATCH):
        batch = records[start : start + _CHROMA_BATCH]
        collection.add(
            ids=[r["id"] for r in batch],
            documents=[r["text"] for r in batch],
            metadatas=[r["metadata"] for r in batch],
            embeddings=embeddings[start : start + _CHROMA_BATCH],
        )
    logger.info("Stored %d chunks in Chroma collection %s", collection.count(), name)


def main() -> None:
    """Command-line entry point."""
    parser = argparse.ArgumentParser(description="Build the DisasterAI knowledge base.")
    parser.add_argument("--strategy", choices=[*CHUNKERS, "all"], default="structure")
    parser.add_argument("--no-header", action="store_true", help="disable the contextual header")
    parser.add_argument("--dry-run", action="store_true", help="chunk and write JSONL only, skip embedding")
    parser.add_argument("--model", default=None, help="embedding model (default: EMBEDDING_MODEL from config)")
    args = parser.parse_args()
    strategies = list(CHUNKERS) if args.strategy == "all" else [args.strategy]
    for strategy in strategies:
        ingest(strategy, contextual_header=not args.no_header, dry_run=args.dry_run, model=args.model)


if __name__ == "__main__":
    main()
