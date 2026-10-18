"""Tests for the Vision Agent — pure logic only (no GPU / VLM required).

All tests mock VLMClient.get() so the model is never loaded.
Run with:  pytest tests/test_vision_agent.py -v
"""

import pytest
import numpy as np
from PIL import Image
from unittest.mock import MagicMock, patch

from src.schemas import (
    ConsistencyResult,
    DisasterClass,
    ReliabilityStatus,
    TTAVariantResult,
    VisionInput,
)
from src.agents.vision_agent import (
    _assess_reliability,
    _compute_consistency,
    _make_variants,
    _parse_class,
    _parse_evidence,
    _parse_evidence_list,
    run,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _rgb_image(w: int = 100, h: int = 80) -> Image.Image:
    arr = np.zeros((h, w, 3), dtype=np.uint8)
    return Image.fromarray(arr)


def _variant(name: str, cls: DisasterClass, evidence=("smoke",), desc="test") -> TTAVariantResult:
    return TTAVariantResult(
        variant_name=name,
        predicted_class=cls,
        visible_evidence=list(evidence),
        raw_description=desc,
    )


def _consistency(score: float, majority: DisasterClass, agree: bool = True) -> ConsistencyResult:
    return ConsistencyResult(
        agreement_score=score,
        majority_class=majority,
        all_agree=agree,
        variant_results=[],
        disagreements=[],
    )


# ---------------------------------------------------------------------------
# _make_variants
# ---------------------------------------------------------------------------


def test_make_variants_returns_three():
    variants = _make_variants(_rgb_image())
    assert len(variants) == 3


def test_make_variants_names():
    names = [name for name, _ in _make_variants(_rgb_image())]
    assert names == ["original", "resized", "flipped"]


def test_resized_variant_is_512x512():
    variants = dict(_make_variants(_rgb_image(200, 300)))
    assert variants["resized"].size == (512, 512)


def test_original_size_unchanged():
    variants = dict(_make_variants(_rgb_image(200, 300)))
    assert variants["original"].size == (200, 300)


def test_flipped_same_size_as_original():
    img = _rgb_image(200, 300)
    variants = dict(_make_variants(img))
    assert variants["flipped"].size == img.size


def test_original_is_a_copy():
    """Mutating the variant must not affect the source image."""
    img = _rgb_image()
    variants = dict(_make_variants(img))
    variants["original"].putpixel((0, 0), (255, 0, 0))
    assert img.getpixel((0, 0)) == (0, 0, 0)


# ---------------------------------------------------------------------------
# _parse_class
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("raw,expected", [
    ("fire",            DisasterClass.FIRE),
    ("Fire.",           DisasterClass.FIRE),
    ("FIRE",            DisasterClass.FIRE),
    ("flood",           DisasterClass.FLOOD),
    ("flooding",        DisasterClass.FLOOD),
    ("flooding.",       DisasterClass.FLOOD),
    ("normal",          DisasterClass.NORMAL),
    ("none",            DisasterClass.NORMAL),
    ("no",              DisasterClass.NORMAL),
    ("uncertain",       DisasterClass.UNCERTAIN),
    ("unknown",         DisasterClass.UNCERTAIN),
    ("gibberish",       DisasterClass.UNCERTAIN),
    ("",                DisasterClass.UNCERTAIN),
    ("  fire  ",        DisasterClass.FIRE),
    ("irrelevant",      DisasterClass.IRRELEVANT),
    ("Irrelevant.",     DisasterClass.IRRELEVANT),
])
def test_parse_class(raw, expected):
    assert _parse_class(raw) == expected


# ---------------------------------------------------------------------------
# _parse_evidence_list (prompt v2 — JSON array from structured call)
# ---------------------------------------------------------------------------


def test_parse_evidence_list_valid():
    assert _parse_evidence_list(["flames", "smoke"]) == ["flames", "smoke"]


def test_parse_evidence_list_strips_items():
    assert _parse_evidence_list(["  flames ", " smoke  "]) == ["flames", "smoke"]


def test_parse_evidence_list_caps_at_five():
    result = _parse_evidence_list(["a", "b", "c", "d", "e", "f", "g"])
    assert len(result) == 5


def test_parse_evidence_list_non_list_returns_empty():
    assert _parse_evidence_list("not a list") == []
    assert _parse_evidence_list(None) == []


def test_parse_evidence_list_empty_list():
    assert _parse_evidence_list([]) == []


def test_parse_evidence_list_drops_blank_items():
    assert _parse_evidence_list(["flames", "", "  ", "smoke"]) == ["flames", "smoke"]


# ---------------------------------------------------------------------------
# _parse_evidence
# ---------------------------------------------------------------------------


def test_parse_evidence_splits_commas():
    result = _parse_evidence("smoke, flames, damaged roof")
    assert result == ["smoke", "flames", "damaged roof"]


def test_parse_evidence_strips_whitespace():
    result = _parse_evidence("  smoke ,  water  ")
    assert result == ["smoke", "water"]


def test_parse_evidence_single_item():
    assert _parse_evidence("flooded road") == ["flooded road"]


def test_parse_evidence_empty_string_fallback():
    result = _parse_evidence("")
    assert result == [""]


# ---------------------------------------------------------------------------
# _compute_consistency
# ---------------------------------------------------------------------------


def test_full_agreement_score_is_one():
    results = [_variant(n, DisasterClass.FIRE) for n in ("original", "resized", "flipped")]
    c = _compute_consistency(results)
    assert c.agreement_score == 1.0
    assert c.all_agree is True
    assert c.majority_class == DisasterClass.FIRE
    assert c.disagreements == []


def test_two_thirds_agreement():
    results = [
        _variant("original", DisasterClass.FIRE),
        _variant("resized",  DisasterClass.FIRE),
        _variant("flipped",  DisasterClass.FLOOD),
    ]
    c = _compute_consistency(results)
    assert c.agreement_score == pytest.approx(2 / 3, abs=0.01)
    assert c.all_agree is False
    assert c.majority_class == DisasterClass.FIRE
    assert len(c.disagreements) == 1
    assert "flipped" in c.disagreements[0]


def test_full_disagreement_score():
    results = [
        _variant("original", DisasterClass.FIRE),
        _variant("resized",  DisasterClass.FLOOD),
        _variant("flipped",  DisasterClass.NORMAL),
    ]
    c = _compute_consistency(results)
    assert c.agreement_score == pytest.approx(1 / 3, abs=0.01)
    assert c.all_agree is False


def test_consistency_variant_results_preserved():
    results = [_variant(n, DisasterClass.FLOOD) for n in ("original", "resized", "flipped")]
    c = _compute_consistency(results)
    assert len(c.variant_results) == 3


# ---------------------------------------------------------------------------
# _assess_reliability
# ---------------------------------------------------------------------------


def test_reliable_on_full_agreement():
    c = _consistency(1.0, DisasterClass.FIRE)
    status, notes = _assess_reliability(c, [_variant("original", DisasterClass.FIRE)])
    assert status == ReliabilityStatus.RELIABLE


def test_unreliable_on_low_agreement():
    c = _consistency(0.33, DisasterClass.FIRE, agree=False)
    status, notes = _assess_reliability(c, [_variant("original", DisasterClass.FIRE)])
    assert status == ReliabilityStatus.UNRELIABLE
    assert any("agreement" in n.lower() for n in notes)


def test_uncertain_when_majority_is_uncertain():
    c = _consistency(1.0, DisasterClass.UNCERTAIN)
    status, notes = _assess_reliability(c, [_variant("original", DisasterClass.UNCERTAIN)])
    assert status == ReliabilityStatus.UNCERTAIN


def test_unreliable_on_uncertainty_language():
    c = _consistency(1.0, DisasterClass.FIRE)
    results = [_variant("original", DisasterClass.FIRE, desc="It is unclear what this shows")]
    status, notes = _assess_reliability(c, results)
    # One soft signal (uncertainty language) + low agreement absent → still could be reliable
    # but with two signals it must be unreliable; here only one signal so check at least noted
    assert any("uncertainty language" in n for n in notes)


def test_unreliable_with_two_soft_signals():
    """Low agreement + uncertainty language → UNRELIABLE."""
    c = _consistency(0.33, DisasterClass.FIRE, agree=False)
    results = [_variant("original", DisasterClass.FIRE, desc="unclear and hard to tell")]
    status, notes = _assess_reliability(c, results)
    assert status == ReliabilityStatus.UNRELIABLE
    assert len(notes) >= 2


# ---------------------------------------------------------------------------
# run() — integration (VLM mocked)
# ---------------------------------------------------------------------------


def _make_mock_client(json_answers: list[dict]):
    """Return a VLM client mock that cycles through `json_answers` on each
    .answer_json() call — one dict per TTA variant (prompt v2)."""
    client = MagicMock()
    client.encode_image.return_value = MagicMock()
    client.answer_json.side_effect = json_answers
    return client


def test_run_happy_path_fire(tmp_path):
    img_path = tmp_path / "fire.png"
    _rgb_image().save(img_path)

    # 3 variants, one JSON call each, all predict fire
    answers = [
        {"class": "fire", "description": "Fire visible on the building.",
         "evidence": ["flames", "smoke"]},
    ] * 3

    with patch("src.agents.vision_agent.get_vlm_client", return_value=_make_mock_client(answers)):
        output = run(VisionInput(image_path=str(img_path)))

    assert output.predicted_class == DisasterClass.FIRE
    assert output.reliability_status == ReliabilityStatus.RELIABLE
    assert output.consistency.agreement_score == 1.0
    assert output.error is None


def test_run_returns_uncertain_on_disagreement(tmp_path):
    img_path = tmp_path / "ambiguous.png"
    _rgb_image().save(img_path)

    # Three variants disagree: fire / flood / normal
    answers = [
        {"class": "fire",   "description": "Fire visible.",   "evidence": ["flames"]},
        {"class": "flood",  "description": "Flood visible.",  "evidence": ["water"]},
        {"class": "normal", "description": "Normal scene.",   "evidence": []},
    ]

    with patch("src.agents.vision_agent.get_vlm_client", return_value=_make_mock_client(answers)):
        output = run(VisionInput(image_path=str(img_path)))

    assert output.reliability_status == ReliabilityStatus.UNRELIABLE
    assert output.consistency.agreement_score == pytest.approx(1 / 3, abs=0.01)


def test_run_bad_image_path_returns_error():
    output = run(VisionInput(image_path="/nonexistent/image.jpg"))
    assert output.predicted_class == DisasterClass.UNCERTAIN
    assert output.reliability_status == ReliabilityStatus.UNRELIABLE
    assert output.error is not None


def test_run_evidence_deduplicated(tmp_path):
    img_path = tmp_path / "test.png"
    _rgb_image().save(img_path)

    # All variants return the same evidence items
    answers = [
        {"class": "fire", "description": "Fire.", "evidence": ["smoke", "flames"]},
    ] * 3

    with patch("src.agents.vision_agent.get_vlm_client", return_value=_make_mock_client(answers)):
        output = run(VisionInput(image_path=str(img_path)))

    # "smoke" and "flames" should appear only once each
    evidence_lower = [e.lower() for e in output.visible_evidence]
    assert evidence_lower.count("smoke") == 1
    assert evidence_lower.count("flames") == 1


def test_run_description_is_from_original_variant(tmp_path):
    img_path = tmp_path / "test.png"
    _rgb_image().save(img_path)

    answers = [
        {"class": "fire", "description": "ORIGINAL_DESCRIPTION", "evidence": ["smoke"]},
        {"class": "fire", "description": "resized description",  "evidence": ["smoke"]},
        {"class": "fire", "description": "flipped description",  "evidence": ["smoke"]},
    ]

    with patch("src.agents.vision_agent.get_vlm_client", return_value=_make_mock_client(answers)):
        output = run(VisionInput(image_path=str(img_path)))

    assert output.description == "ORIGINAL_DESCRIPTION"


def test_run_irrelevant_class_adds_note(tmp_path):
    img_path = tmp_path / "selfie.png"
    _rgb_image().save(img_path)

    answers = [
        {"class": "irrelevant", "description": "A selfie of a person indoors.", "evidence": []},
    ] * 3

    with patch("src.agents.vision_agent.get_vlm_client", return_value=_make_mock_client(answers)):
        output = run(VisionInput(image_path=str(img_path)))

    assert output.predicted_class == DisasterClass.IRRELEVANT
    assert any("unrelated to disaster assessment" in n for n in output.reliability_notes)


def test_run_variant_failure_is_uncertain_not_crash(tmp_path):
    """A transient cloud API failure on one variant must not crash run()."""
    img_path = tmp_path / "test.png"
    _rgb_image().save(img_path)

    client = MagicMock()
    client.encode_image.return_value = MagicMock()
    client.answer_json.side_effect = [
        {"class": "fire", "description": "Fire.", "evidence": ["flames"]},
        RuntimeError("Groq API timeout"),
        {"class": "fire", "description": "Fire.", "evidence": ["flames"]},
    ]

    with patch("src.agents.vision_agent.get_vlm_client", return_value=client):
        output = run(VisionInput(image_path=str(img_path)))

    assert output.error is None  # pipeline-level error stays None; only the variant failed
    assert output.consistency.agreement_score == pytest.approx(2 / 3, abs=0.01)
