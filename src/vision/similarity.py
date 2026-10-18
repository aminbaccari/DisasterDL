"""Visual similarity module — cosine nearest-neighbour search over DINOv2 embeddings.

EmbeddingStore holds path → L2-normalized embedding mappings. Similarity is
computed as the dot product between normalized vectors (equivalent to cosine
similarity). The store can be persisted to / loaded from a compressed .npz
file so embeddings do not need to be recomputed between runs.

IMPORTANT design constraints (from the project spec):
  - Low similarity does NOT mean a prediction is wrong.
  - High similarity does NOT mean a prediction is correct.
  - Nearest-neighbor paths are identifiers only — do not auto-assign classes.
  - The store operates in shadow mode by default; it never overwrites reliability.
"""

import logging
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)


class EmbeddingStore:
    """In-memory store of (image_path, L2-normalized embedding) pairs.

    Thread-safety: single-threaded use only (matches the rest of the pipeline).
    """

    def __init__(self) -> None:
        self._paths: list[str] = []
        self._embeddings: list[np.ndarray] = []

    # ------------------------------------------------------------------
    # Mutations
    # ------------------------------------------------------------------

    def add(self, image_path: str, embedding: np.ndarray) -> None:
        """Insert or update an embedding for image_path."""
        if image_path in self._paths:
            idx = self._paths.index(image_path)
            self._embeddings[idx] = embedding.astype(np.float32)
        else:
            self._paths.append(image_path)
            self._embeddings.append(embedding.astype(np.float32))

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def size(self) -> int:
        return len(self._paths)

    def _matrix(self) -> np.ndarray:
        """Stack all embeddings into a (N, D) float32 matrix."""
        return np.stack(self._embeddings, axis=0)

    def find_nearest(
        self,
        query: np.ndarray,
        k: int = 5,
        exclude_path: str | None = None,
    ) -> list[dict]:
        """Return the k most similar images as a list of dicts.

        Each dict has keys: ``image_path`` (str) and ``cosine_similarity`` (float).
        Excludes exclude_path to prevent self-matches when the query image is
        already in the store.

        Returns an empty list when the store is empty.
        """
        if not self._embeddings:
            return []

        matrix = self._matrix()  # [N, D]
        q = query.astype(np.float32)

        # Cosine similarity = dot product for L2-normalized vectors.
        sims: np.ndarray = matrix @ q  # [N]

        # Mask out self-match.
        if exclude_path is not None and exclude_path in self._paths:
            exc_idx = self._paths.index(exclude_path)
            sims[exc_idx] = -2.0  # below any valid cosine value [-1, 1]

        effective_k = min(k, len(self._paths))
        top_indices = np.argpartition(sims, -effective_k)[-effective_k:]
        top_indices = top_indices[np.argsort(sims[top_indices])[::-1]]

        return [
            {"image_path": self._paths[i], "cosine_similarity": float(sims[i])}
            for i in top_indices
            if sims[i] > -1.5  # exclude the masked self-match slot
        ]

    def mean_similarity(self, query: np.ndarray, exclude_path: str | None = None) -> float | None:
        """Mean cosine similarity of the top-5 nearest neighbors.

        Returns None when the store is empty.
        """
        neighbors = self.find_nearest(query, k=5, exclude_path=exclude_path)
        if not neighbors:
            return None
        return float(np.mean([n["cosine_similarity"] for n in neighbors]))

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self, path: str | Path) -> None:
        """Persist the store to a compressed .npz file."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        matrix = (
            np.stack(self._embeddings, axis=0)
            if self._embeddings
            else np.empty((0, 0), dtype=np.float32)
        )
        np.savez_compressed(
            str(path),
            paths=np.array(self._paths, dtype=object),
            embeddings=matrix,
        )
        logger.info("Saved %d embeddings → %s", len(self._paths), path)

    def load(self, path: str | Path) -> None:
        """Load an .npz file produced by save().  Overwrites current contents."""
        path = Path(path)
        data = np.load(str(path), allow_pickle=True)
        self._paths = list(data["paths"])
        embs = data["embeddings"]
        self._embeddings = [embs[i] for i in range(len(embs))]
        logger.info("Loaded %d embeddings ← %s", len(self._paths), path)
