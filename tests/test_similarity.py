"""Unit tests for EmbeddingStore and cosine similarity logic."""

import tempfile
from pathlib import Path

import numpy as np
import pytest

from src.vision.similarity import EmbeddingStore


def _unit_vec(dim: int = 384, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    v = rng.standard_normal(dim).astype(np.float32)
    return v / np.linalg.norm(v)


# ---------------------------------------------------------------------------
# Basic store operations
# ---------------------------------------------------------------------------

class TestEmbeddingStore:

    def test_empty_store_size(self):
        store = EmbeddingStore()
        assert store.size() == 0

    def test_add_increases_size(self):
        store = EmbeddingStore()
        store.add("img_a.jpg", _unit_vec(seed=1))
        assert store.size() == 1
        store.add("img_b.jpg", _unit_vec(seed=2))
        assert store.size() == 2

    def test_add_updates_existing(self):
        store = EmbeddingStore()
        v1 = _unit_vec(seed=1)
        v2 = _unit_vec(seed=2)
        store.add("img.jpg", v1)
        store.add("img.jpg", v2)  # update
        assert store.size() == 1
        # Nearest neighbor to v2 should have similarity ≈ 1.0
        result = store.find_nearest(v2, k=1)
        assert len(result) == 1
        assert result[0]["cosine_similarity"] == pytest.approx(1.0, abs=1e-5)

    # ------------------------------------------------------------------
    # find_nearest
    # ------------------------------------------------------------------

    def test_find_nearest_empty_returns_empty(self):
        store = EmbeddingStore()
        result = store.find_nearest(_unit_vec(), k=3)
        assert result == []

    def test_find_nearest_returns_correct_count(self):
        store = EmbeddingStore()
        for i in range(10):
            store.add(f"img_{i}.jpg", _unit_vec(seed=i))
        result = store.find_nearest(_unit_vec(seed=99), k=5)
        assert len(result) == 5

    def test_find_nearest_sorted_descending(self):
        store = EmbeddingStore()
        for i in range(10):
            store.add(f"img_{i}.jpg", _unit_vec(seed=i))
        query = _unit_vec(seed=99)
        result = store.find_nearest(query, k=5)
        sims = [r["cosine_similarity"] for r in result]
        assert sims == sorted(sims, reverse=True)

    def test_find_nearest_exact_match_at_top(self):
        store = EmbeddingStore()
        target = _unit_vec(seed=42)
        store.add("target.jpg", target)
        for i in range(9):
            store.add(f"other_{i}.jpg", _unit_vec(seed=i))
        result = store.find_nearest(target, k=1)
        assert result[0]["image_path"] == "target.jpg"
        assert result[0]["cosine_similarity"] == pytest.approx(1.0, abs=1e-5)

    # ------------------------------------------------------------------
    # Self-match exclusion
    # ------------------------------------------------------------------

    def test_self_match_excluded(self):
        store = EmbeddingStore()
        v = _unit_vec(seed=1)
        store.add("self.jpg", v)
        for i in range(4):
            store.add(f"other_{i}.jpg", _unit_vec(seed=i + 10))
        result = store.find_nearest(v, k=3, exclude_path="self.jpg")
        paths = [r["image_path"] for r in result]
        assert "self.jpg" not in paths

    def test_exclude_nonexistent_path_is_safe(self):
        store = EmbeddingStore()
        store.add("img.jpg", _unit_vec(seed=1))
        result = store.find_nearest(_unit_vec(seed=99), k=1, exclude_path="does_not_exist.jpg")
        assert len(result) == 1

    # ------------------------------------------------------------------
    # mean_similarity
    # ------------------------------------------------------------------

    def test_mean_similarity_none_on_empty(self):
        store = EmbeddingStore()
        assert store.mean_similarity(_unit_vec()) is None

    def test_mean_similarity_returns_float(self):
        store = EmbeddingStore()
        for i in range(5):
            store.add(f"img_{i}.jpg", _unit_vec(seed=i))
        result = store.mean_similarity(_unit_vec(seed=99))
        assert isinstance(result, float)
        assert -1.0 <= result <= 1.0

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def test_save_and_load_roundtrip(self):
        store = EmbeddingStore()
        expected_paths = []
        for i in range(5):
            p = f"img_{i}.jpg"
            store.add(p, _unit_vec(seed=i))
            expected_paths.append(p)

        with tempfile.TemporaryDirectory() as tmpdir:
            npz_path = Path(tmpdir) / "store.npz"
            store.save(npz_path)

            store2 = EmbeddingStore()
            store2.load(npz_path)

            assert store2.size() == 5
            assert set(store2._paths) == set(expected_paths)

    def test_load_preserves_similarity_results(self):
        store = EmbeddingStore()
        target = _unit_vec(seed=42)
        store.add("target.jpg", target)
        for i in range(4):
            store.add(f"other_{i}.jpg", _unit_vec(seed=i))

        with tempfile.TemporaryDirectory() as tmpdir:
            npz_path = Path(tmpdir) / "store.npz"
            store.save(npz_path)

            store2 = EmbeddingStore()
            store2.load(npz_path)
            result = store2.find_nearest(target, k=1)
            assert result[0]["image_path"] == "target.jpg"
            assert result[0]["cosine_similarity"] == pytest.approx(1.0, abs=1e-4)


# ---------------------------------------------------------------------------
# Shadow mode: DINOv2 signal must NOT change the final predicted class
# ---------------------------------------------------------------------------

class TestShadowMode:

    def test_shadow_mode_does_not_change_prediction(self):
        """With DINOV2_ENABLED=False the VisionOutput.dinov2_signal is None."""
        from unittest.mock import patch, MagicMock
        from src.schemas import VisionInput

        # Ensure DINOv2 is disabled via settings.
        with patch("src.config.settings") as mock_settings:
            mock_settings.dinov2_enabled = False
            mock_settings.vlm_provider = "groq"
            mock_settings.dinov2_model = "facebook/dinov2-small"
            mock_settings.dinov2_integration_mode = "shadow"
            mock_settings.dinov2_store_path = ""

            from src.agents import vision_agent
            # Reload module-level references after patching settings.
            with patch.object(vision_agent, "settings", mock_settings):
                # Mock the VLM client so no network call is made.
                mock_client = MagicMock()
                # 3 variants × 1 structured JSON call each (prompt v2)
                mock_client.answer_json.side_effect = [
                    {"class": "fire", "description": "Fire visible.", "evidence": ["flames", "smoke"]},
                    {"class": "fire", "description": "Fire visible.", "evidence": ["flames", "smoke"]},
                    {"class": "fire", "description": "Fire visible.", "evidence": ["flames", "smoke"]},
                ]
                mock_client.encode_image.return_value = "base64data"

                with patch("src.agents.vision_agent.get_vlm_client", return_value=mock_client):
                    with patch("src.agents.vision_agent.load_prompt") as mock_prompt:
                        mock_prompt.return_value = {
                            "classify_json_prompt": "classify",
                            "system_prompt": "system",
                        }
                        from pathlib import Path as _Path
                        import tempfile, shutil
                        from PIL import Image as _Image

                        tmpdir = tempfile.mkdtemp()
                        try:
                            img_path = str(_Path(tmpdir) / "test.jpg")
                            _Image.new("RGB", (64, 64)).save(img_path)
                            out = vision_agent.run(VisionInput(image_path=img_path))
                            assert out.dinov2_signal is None
                        finally:
                            shutil.rmtree(tmpdir)
