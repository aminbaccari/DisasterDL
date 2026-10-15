"""Local multilingual embeddings.

multilingual-e5 models expect the prefixes "query: " and "passage: ". They are
added automatically when the model name contains "e5". If you switch to another
model family, check its documentation for the right prefixes.
"""
import os
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()


def model_name():
    return os.getenv("EMBEDDING_MODEL", "intfloat/multilingual-e5-small")


@lru_cache(maxsize=1)
def _model():
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(model_name())


def _encode(texts, prefix):
    if "e5" in model_name().lower():
        texts = [f"{prefix}{t}" for t in texts]
    return _model().encode(texts, normalize_embeddings=True, show_progress_bar=False).tolist()


def embed_passages(texts):
    return _encode(texts, "passage: ")


def embed_queries(texts):
    return _encode(texts, "query: ")
