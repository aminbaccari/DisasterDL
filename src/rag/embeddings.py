"""Embedding model and token counting, shared by ingestion and retrieval.

Keeping both here guarantees that documents and queries are embedded the same way
(same model, same e5 prefixes) and that chunk sizes are measured with the tokenizer
of the model that will embed them, so no chunk is silently truncated.
"""

from functools import lru_cache
from typing import Protocol

from src.config import get_settings
from src.utils.logging_utils import get_logger

logger = get_logger(__name__)


class TokenCounter(Protocol):
    """Counts tokens and returns token character offsets for a text."""

    def count(self, text: str) -> int:
        """Return the number of tokens in ``text``."""
        ...

    def offsets(self, text: str) -> list[tuple[int, int]]:
        """Return the (start, end) character span of each token of ``text``."""
        ...


class HFTokenCounter:
    """Token counter backed by the Hugging Face fast tokenizer of the embedding model."""

    def __init__(self, model_name: str) -> None:
        from transformers import AutoTokenizer

        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.tokenizer.model_max_length = 10**9  # we tokenise whole documents; silence length warnings

    def count(self, text: str) -> int:
        """Return the number of tokens in ``text`` (special tokens excluded)."""
        return len(self.tokenizer(text, add_special_tokens=False)["input_ids"])

    def offsets(self, text: str) -> list[tuple[int, int]]:
        """Return the character span of each token of ``text``."""
        encoded = self.tokenizer(text, add_special_tokens=False, return_offsets_mapping=True)
        return [tuple(span) for span in encoded["offset_mapping"]]


@lru_cache
def get_token_counter(model_name: str | None = None) -> HFTokenCounter:
    """Return a cached token counter for ``model_name`` (default: the configured embedding model)."""
    return HFTokenCounter(model_name or get_settings().embedding_model)


class Embedder:
    """Bi-encoder embedder (transformer + mean pooling) applying the e5 ``query:``/``passage:`` prefixes.

    e5 models are trained with these asymmetric prefixes; omitting them degrades retrieval.
    The sentence embedding is the attention-masked mean of the last hidden states, then
    L2-normalised so that cosine similarity equals the dot product. This is exactly what
    sentence-transformers does for e5, without its scikit-learn/SciPy dependencies.
    """

    max_length = 512

    def __init__(self, model_name: str, batch_size: int = 32) -> None:
        import torch
        from transformers import AutoModel, AutoTokenizer

        logger.info("Loading embedding model %s", model_name)
        self._torch = torch
        self.model_name = model_name
        self.batch_size = batch_size
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModel.from_pretrained(model_name).to(self.device).eval()
        self._use_prefixes = "e5" in model_name.lower()

    def _prefix(self, kind: str, texts: list[str]) -> list[str]:
        return [f"{kind}: {t}" for t in texts] if self._use_prefixes else texts

    def _encode(self, texts: list[str]) -> list[list[float]]:
        torch = self._torch
        order = sorted(range(len(texts)), key=lambda i: len(texts[i]))  # similar lengths -> less padding
        texts = [texts[i] for i in order]
        vectors: list[list[float]] = []
        for start in range(0, len(texts), self.batch_size):
            batch = self.tokenizer(
                texts[start : start + self.batch_size],
                padding=True,
                truncation=True,
                max_length=self.max_length,
                return_tensors="pt",
            ).to(self.device)
            with torch.inference_mode():
                hidden = self.model(**batch).last_hidden_state
            mask = batch["attention_mask"].unsqueeze(-1).to(hidden.dtype)
            pooled = (hidden * mask).sum(dim=1) / mask.sum(dim=1).clamp(min=1e-9)
            vectors.extend(torch.nn.functional.normalize(pooled, p=2, dim=1).cpu().tolist())
            done = min(start + self.batch_size, len(texts))
            if len(texts) > self.batch_size and (done // self.batch_size % 10 == 0 or done == len(texts)):
                logger.info("Embedded %d/%d", done, len(texts))
        restored: list[list[float]] = [[] for _ in texts]
        for position, original in enumerate(order):
            restored[original] = vectors[position]
        return restored

    def embed_passages(self, texts: list[str]) -> list[list[float]]:
        """Embed document chunks."""
        return self._encode(self._prefix("passage", texts))

    def embed_query(self, text: str) -> list[float]:
        """Embed a search query."""
        return self._encode(self._prefix("query", [text]))[0]


@lru_cache
def get_embedder(model_name: str | None = None) -> Embedder:
    """Return a cached embedder for ``model_name`` (default: the configured embedding model)."""
    settings = get_settings()
    return Embedder(model_name or settings.embedding_model, settings.embedding_batch_size)
