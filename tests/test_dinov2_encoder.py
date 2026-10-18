"""Unit tests for DINOv2Encoder.

All tests mock the HuggingFace model and processor so no weights need to
be downloaded and no GPU is required.
"""

import numpy as np
import pytest
from PIL import Image
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fake_processor(images, return_tensors):
    import torch
    return {"pixel_values": torch.zeros(1, 3, 224, 224)}


def _make_fake_model(embedding_dim: int = 384):
    import torch

    class FakeOutput:
        last_hidden_state = torch.randn(1, 197, embedding_dim)

    model = MagicMock()
    model.return_value = FakeOutput()
    model.eval.return_value = model
    model.half.return_value = model
    model.to.return_value = model
    model.parameters.return_value = iter([torch.zeros(1)])
    return model


def _rgb_image(w: int = 64, h: int = 64) -> Image.Image:
    return Image.new("RGB", (w, h), color=(100, 150, 200))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestDINOv2Encoder:

    def setup_method(self):
        from src.vision.dinov2_encoder import DINOv2Encoder
        DINOv2Encoder.reset()

    def teardown_method(self):
        from src.vision.dinov2_encoder import DINOv2Encoder
        DINOv2Encoder.reset()

    @patch("src.vision.dinov2_encoder.AutoModel.from_pretrained")
    @patch("src.vision.dinov2_encoder.AutoImageProcessor.from_pretrained")
    def test_encode_returns_float32_numpy(self, mock_proc, mock_model):
        mock_proc.return_value = MagicMock(side_effect=_fake_processor)
        mock_model.return_value = _make_fake_model(384)

        from src.vision.dinov2_encoder import DINOv2Encoder
        enc = DINOv2Encoder(model_id="facebook/dinov2-small", device="cpu")
        result = enc.encode(_rgb_image())

        assert isinstance(result, np.ndarray)
        assert result.dtype == np.float32

    @patch("src.vision.dinov2_encoder.AutoModel.from_pretrained")
    @patch("src.vision.dinov2_encoder.AutoImageProcessor.from_pretrained")
    def test_encode_l2_normalized(self, mock_proc, mock_model):
        mock_proc.return_value = MagicMock(side_effect=_fake_processor)
        mock_model.return_value = _make_fake_model(384)

        from src.vision.dinov2_encoder import DINOv2Encoder
        enc = DINOv2Encoder(model_id="facebook/dinov2-small", device="cpu")
        result = enc.encode(_rgb_image())

        norm = float(np.linalg.norm(result))
        assert abs(norm - 1.0) < 1e-5, f"Expected L2 norm ≈ 1.0, got {norm}"

    @patch("src.vision.dinov2_encoder.AutoModel.from_pretrained")
    @patch("src.vision.dinov2_encoder.AutoImageProcessor.from_pretrained")
    def test_encode_correct_dim(self, mock_proc, mock_model):
        mock_proc.return_value = MagicMock(side_effect=_fake_processor)
        mock_model.return_value = _make_fake_model(384)

        from src.vision.dinov2_encoder import DINOv2Encoder
        enc = DINOv2Encoder(model_id="facebook/dinov2-small", device="cpu")
        result = enc.encode(_rgb_image())

        assert result.shape == (384,)

    @patch("src.vision.dinov2_encoder.AutoModel.from_pretrained")
    @patch("src.vision.dinov2_encoder.AutoImageProcessor.from_pretrained")
    def test_rgba_image_converted(self, mock_proc, mock_model):
        """RGBA images must be converted to RGB without error."""
        mock_proc.return_value = MagicMock(side_effect=_fake_processor)
        mock_model.return_value = _make_fake_model(384)

        from src.vision.dinov2_encoder import DINOv2Encoder
        enc = DINOv2Encoder(model_id="facebook/dinov2-small", device="cpu")
        rgba = Image.new("RGBA", (64, 64), color=(100, 150, 200, 128))
        result = enc.encode(rgba)
        assert result.shape == (384,)

    @patch("src.vision.dinov2_encoder.AutoModel.from_pretrained")
    @patch("src.vision.dinov2_encoder.AutoImageProcessor.from_pretrained")
    def test_singleton_returns_same_instance(self, mock_proc, mock_model):
        mock_proc.return_value = MagicMock(side_effect=_fake_processor)
        mock_model.return_value = _make_fake_model(384)

        # Patch settings so singleton uses our mock model.
        with patch("src.vision.dinov2_encoder.DINOv2Encoder.__init__", return_value=None):
            from src.vision.dinov2_encoder import DINOv2Encoder
            # Directly set an instance to verify singleton behavior.
            fake = MagicMock()
            DINOv2Encoder._instance = fake
            assert DINOv2Encoder.get() is fake
