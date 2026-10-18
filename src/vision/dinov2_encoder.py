"""DINOv2 visual encoder — frozen pretrained feature extractor.

Wraps facebook/dinov2-small (or a configurable variant) from HuggingFace
Transformers. Returns L2-normalized CLS-token embeddings as numpy arrays.
The model is loaded once as a singleton, frozen, and never fine-tuned.

Reference:
    Oquab et al. (2023). DINOv2: Learning Robust Visual Features without
    Supervision. TMLR 2024. https://arxiv.org/abs/2304.07193
"""

import logging

import numpy as np
import torch
from PIL import Image
from transformers import AutoImageProcessor, AutoModel

logger = logging.getLogger(__name__)

# Embedding dimensions per official DINOv2 variant.
_DIM_MAP: dict[str, int] = {
    "facebook/dinov2-small": 384,
    "facebook/dinov2-base": 768,
    "facebook/dinov2-large": 1024,
    "facebook/dinov2-giant": 1536,
}


class DINOv2Encoder:
    """Singleton frozen DINOv2 encoder.

    GPU inference with float16 when CUDA is available; CPU float32 fallback.
    Loading is deferred until the first call to DINOv2Encoder.get().
    """

    _instance: "DINOv2Encoder | None" = None

    def __init__(self, model_id: str, device: str | None = None) -> None:
        if device is None:
            device = "cuda" if torch.cuda.is_available() else "cpu"
        self.device = device
        self.model_id = model_id
        self.embedding_dim = _DIM_MAP.get(model_id, 384)

        logger.info("Loading DINOv2 %s on %s", model_id, device)
        self.processor = AutoImageProcessor.from_pretrained(model_id)
        self.model = AutoModel.from_pretrained(model_id)
        self.model.eval()
        # Half-precision on GPU saves ~half the VRAM; dinov2-small: ~44 MB on GPU.
        if device == "cuda":
            self.model = self.model.half()
        self.model.to(device)
        logger.info("DINOv2 ready — dim=%d  device=%s", self.embedding_dim, device)

    @torch.no_grad()
    def encode(self, image: Image.Image) -> np.ndarray:
        """Return an L2-normalized float32 embedding of shape (embedding_dim,).

        The CLS token at position 0 of last_hidden_state is used as the
        global image representation, following the DINOv2 paper.
        """
        rgb = image.convert("RGB")
        inputs = self.processor(images=rgb, return_tensors="pt")
        # Move to device; cast float tensors to model dtype.
        dtype = torch.float16 if self.device == "cuda" else torch.float32
        inputs = {
            k: v.to(self.device).to(dtype) if v.is_floating_point() else v.to(self.device)
            for k, v in inputs.items()
        }
        outputs = self.model(**inputs)
        cls_vec = outputs.last_hidden_state[:, 0, :].squeeze(0)
        embedding = cls_vec.float().cpu().numpy()
        norm = np.linalg.norm(embedding)
        if norm > 1e-8:
            embedding = embedding / norm
        return embedding

    @classmethod
    def get(cls) -> "DINOv2Encoder":
        """Return the singleton encoder, creating it on first call."""
        if cls._instance is None:
            from src.config import settings
            cls._instance = cls(model_id=settings.dinov2_model)
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Release the singleton (for testing)."""
        cls._instance = None
