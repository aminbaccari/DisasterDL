"""Entailment check for generated statements (natural language inference).

The RAG has no verifier agent downstream, so each generated statement is checked here: does its
cited passage (or its quote) *entail* the statement? A multilingual NLI cross-encoder reads
(premise, hypothesis) and outputs entailment / neutral / contradiction probabilities; a statement
that is not entailed says more than its evidence and is set aside. The model handles an English
statement against a French passage (trained on multilingual NLI data, including XNLI).
"""

from functools import lru_cache

from src.utils.logging_utils import get_logger

logger = get_logger(__name__)

DEFAULT_NLI_MODEL = "MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7"
ENTAILMENT_THRESHOLD = 0.5  # fixed a priori (most likely label), not tuned on the test set


class NLIChecker:
    """Probability that a premise entails a hypothesis."""

    def __init__(self, model_name: str = DEFAULT_NLI_MODEL, batch_size: int = 8) -> None:
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        logger.info("Loading NLI model %s", model_name)
        self._torch = torch
        self.batch_size = batch_size
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForSequenceClassification.from_pretrained(model_name).to(self.device).eval()
        labels = {v.lower(): int(k) for k, v in self.model.config.id2label.items()}
        self.entailment_index = labels["entailment"]

    def entailment(self, pairs: list[tuple[str, str]]) -> list[float]:
        """Entailment probability for each (premise, hypothesis) pair."""
        probs: list[float] = []
        for start in range(0, len(pairs), self.batch_size):
            batch = pairs[start : start + self.batch_size]
            enc = self.tokenizer(
                [p for p, _ in batch], [h for _, h in batch],
                padding=True, truncation="only_first", max_length=512, return_tensors="pt",
            ).to(self.device)
            with self._torch.inference_mode():
                logits = self.model(**enc).logits
            probs.extend(logits.softmax(dim=-1)[:, self.entailment_index].cpu().tolist())
        return probs


@lru_cache
def get_nli(model_name: str = DEFAULT_NLI_MODEL) -> NLIChecker:
    """Return a cached NLI checker."""
    return NLIChecker(model_name)
