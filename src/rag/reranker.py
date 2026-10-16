"""Optional cross-encoder reranking of retrieved candidates.

The bi-encoder (e5) embeds query and passage separately, which is fast enough to search the
whole index but compares them only through one vector each. A cross-encoder reads the query
and the passage together (full attention between them), which is more precise but must run
once per (query, passage) pair, so it is only applied to the top candidates (two-stage
retrieval). The multilingual model below was trained on mMARCO (MS MARCO translated into
14 languages, French included).
"""

from functools import lru_cache

from src.utils.logging_utils import get_logger

logger = get_logger(__name__)

DEFAULT_RERANKER = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"


class CrossEncoderReranker:
    """Scores (query, passage) pairs with a sequence-classification cross-encoder."""

    def __init__(self, model_name: str = DEFAULT_RERANKER, batch_size: int = 16) -> None:
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        logger.info("Loading reranker %s", model_name)
        self._torch = torch
        self.batch_size = batch_size
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForSequenceClassification.from_pretrained(model_name).to(self.device).eval()

    def score(self, query: str, passages: list[str]) -> list[float]:
        """Relevance logit of each passage for ``query`` (higher is more relevant)."""
        scores: list[float] = []
        for start in range(0, len(passages), self.batch_size):
            batch = self.tokenizer(
                [query] * len(passages[start : start + self.batch_size]),
                passages[start : start + self.batch_size],
                padding=True,
                truncation=True,
                max_length=512,
                return_tensors="pt",
            ).to(self.device)
            with self._torch.inference_mode():
                logits = self.model(**batch).logits
            scores.extend(logits[:, 0].cpu().tolist())
        return scores


@lru_cache
def get_reranker(model_name: str = DEFAULT_RERANKER) -> CrossEncoderReranker:
    """Return a cached reranker."""
    return CrossEncoderReranker(model_name)
