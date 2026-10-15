"""Build the vector index from the corpus.

Run from the project root:
    python -m rag.ingest --strategy both
    python -m rag.ingest --strategy fixed --size 300 --overlap 40
"""
import argparse
from pathlib import Path

from rag import chunking, embedder, store

DEFAULT_CORPUS = Path(__file__).resolve().parent / "corpus"


def build(strategy, corpus_dir, size, overlap, min_words, batch=32):
    docs = chunking.load_documents(corpus_dir)
    if not docs:
        raise SystemExit(f"No documents found in {corpus_dir}")

    ids, texts, metas = [], [], []
    print(f"Strategy {strategy}")
    for doc in docs:
        chunks = chunking.chunk_document(doc["pages"], strategy, size, overlap, min_words)
        if not chunks:
            print(f"  WARNING {doc['source']}: no text extracted (scanned PDF?)")
            continue
        avg = sum(len(c.text.split()) for c in chunks) / len(chunks)
        print(f"  {doc['source']}: {len(chunks)} chunks, {avg:.0f} words on average")
        for n, chunk in enumerate(chunks):
            ids.append(f"{doc['source']}::{strategy}::{n}")
            texts.append(chunk.text)
            metas.append(
                {
                    "source": doc["source"],
                    "language": doc["language"],
                    "topic": doc["topic"],
                    "page": chunk.page,
                    "section": chunk.section,
                    "strategy": strategy,
                }
            )

    collection = store.reset_collection(strategy)
    for i in range(0, len(texts), batch):
        collection.add(
            ids=ids[i:i + batch],
            documents=texts[i:i + batch],
            embeddings=embedder.embed_passages(texts[i:i + batch]),
            metadatas=metas[i:i + batch],
        )
    print(f"  stored {len(texts)} chunks in collection {store.collection_name(strategy)}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--strategy", choices=["fixed", "section", "both"], default="both")
    parser.add_argument("--corpus", default=str(DEFAULT_CORPUS))
    parser.add_argument("--size", type=int, default=300, help="max words per chunk")
    parser.add_argument("--overlap", type=int, default=40, help="overlap in words")
    parser.add_argument("--min-words", type=int, default=30, help="section strategy: merge sections shorter than this")
    args = parser.parse_args()

    strategies = ["fixed", "section"] if args.strategy == "both" else [args.strategy]
    for strategy in strategies:
        build(strategy, args.corpus, args.size, args.overlap, args.min_words)


if __name__ == "__main__":
    main()
