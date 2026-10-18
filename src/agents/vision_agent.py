"""Vision Agent — image-based disaster classification with TTA consistency.

Pipeline per call
-----------------
1. Load image from disk.
2. Produce three TTA variants: original, resized (512×512), horizontally flipped.
   Transformations that could destroy disaster evidence (vertical flip, rotation,
   colour jitter) are intentionally excluded.
3. For each variant, encode once and send ONE structured JSON call to the VLM
   (prompt v2) — class + description + evidence come back together from a
   single reasoning pass, which prevents the class/description contradictions
   seen with v1's three independent text questions. VLM backend is selected by
   VLM_PROVIDER: "groq" (cloud, qwen/qwen3.8-27b, default) or "ollama" (local
   llava-phi3 fallback) — see src/llm/factory.py.
4. Visual Consistency Module: compute agreement_score = majority_count / 3.
   Flag disagreements between variants.
5. Reliability Layer: mark prediction unreliable when agreement < 0.67 or when
   the VLM's own language expresses uncertainty. Return DisasterClass.UNCERTAIN
   when the majority class is already uncertain.
6. Optional DINOv2 visual-similarity signal (shadow mode by default).
7. Return a fully validated VisionOutput — the class + description pair is the
   clean contract consumed downstream (e.g. by the n8n workflow).

Note: agreement_score measures stability across augmentations, not probability
of correctness. High agreement does not guarantee the prediction is right.
"""

import logging
from pathlib import Path
from typing import Optional

from PIL import Image, ImageOps

from src.config import settings
from src.llm.factory import get_vlm_client
from src.llm.prompt_loader import load_prompt
from src.schemas import (
    ConsistencyResult,
    DINOv2Signal,
    DisasterClass,
    ReliabilityStatus,
    SimilarityMatch,
    TTAVariantResult,
    VisionInput,
    VisionOutput,
)

logger = logging.getLogger(__name__)

# Minimum fraction of variants that must agree to be considered consistent.
_AGREEMENT_THRESHOLD = 0.67

# Words in VLM evidence/description that suggest the model is uncertain.
_UNCERTAINTY_KEYWORDS = frozenset(
    {"unclear", "cannot", "hard to tell", "unsure", "not sure", "ambiguous", "difficult to"}
)

# Target size for the resized TTA variant.
_RESIZE_TARGET = (512, 512)

# Mapping from raw VLM tokens to DisasterClass.
_CLASS_MAP: dict[str, DisasterClass] = {
    "fire": DisasterClass.FIRE,
    "flood": DisasterClass.FLOOD,
    "flooding": DisasterClass.FLOOD,
    "normal": DisasterClass.NORMAL,
    "none": DisasterClass.NORMAL,
    "no": DisasterClass.NORMAL,
    "irrelevant": DisasterClass.IRRELEVANT,
    "uncertain": DisasterClass.UNCERTAIN,
    "unknown": DisasterClass.UNCERTAIN,
}


# ---------------------------------------------------------------------------
# Image helpers
# ---------------------------------------------------------------------------


def _make_variants(image: Image.Image) -> list[tuple[str, Image.Image]]:
    """Return three TTA variants: original, resized, horizontally flipped."""
    return [
        ("original", image.copy()),
        ("resized", image.resize(_RESIZE_TARGET, Image.LANCZOS)),
        ("flipped", ImageOps.mirror(image)),
    ]


# ---------------------------------------------------------------------------
# VLM inference helpers
# ---------------------------------------------------------------------------


def _parse_class(raw: str) -> DisasterClass:
    """Map the first token of a raw VLM answer to a DisasterClass."""
    token = raw.strip().lower().split()[0] if raw.strip() else ""
    # Strip trailing punctuation
    token = token.rstrip(".,;:")
    return _CLASS_MAP.get(token, DisasterClass.UNCERTAIN)


def _parse_evidence(raw: str) -> list[str]:
    """Split a comma-separated evidence string into a clean list.

    Also handles bullet-point output (- item or * item) by first
    normalising newline-separated bullets into a comma-separated string.
    """
    # Normalise bullet lists to comma-separated
    if "\n" in raw or raw.strip().startswith(("-", "*")):
        lines = [l.strip().lstrip("-*•·0123456789.) ").strip() for l in raw.splitlines()]
        raw = ", ".join(l for l in lines if l)

    items = [e.strip() for e in raw.split(",") if e.strip()]
    # Strip leading numbered prefixes like "1." or "2)" left by some VLM outputs
    import re
    items = [re.sub(r"^\d+[.)]\s*", "", it) for it in items]
    # Remove items that are explanatory sentences (contain VLM reasoning)
    items = [it for it in items if len(it.split()) <= 6]
    return items[:5] if items else [raw.strip()]  # cap at 5 items


def _parse_evidence_list(raw) -> list[str]:
    """Validate and clean a JSON evidence array (prompt v2 — single structured call).

    Returns an empty list for anything that isn't a list of strings, which is
    the correct fallback for normal / irrelevant / uncertain classes anyway.
    """
    if not isinstance(raw, list):
        return []
    items = [str(x).strip() for x in raw if str(x).strip()]
    return items[:5]


def _infer_variant(
    client,
    prompts: dict,
    variant_name: str,
    image: Image.Image,
) -> TTAVariantResult:
    """Run VLM inference for one TTA variant.

    Single structured JSON call per variant (prompt v2): the model returns
    class + description + evidence together from one reasoning pass, which
    is what prevents the class/description contradictions seen with v1's
    three independent text questions.
    """
    logger.debug("Encoding variant: %s", variant_name)
    encoded = client.encode_image(image)

    data = client.answer_json(
        encoded,
        prompts["classify_json_prompt"],
        system_prompt=prompts.get("system_prompt", ""),
    )

    predicted = _parse_class(str(data.get("class", "")))
    evidence = _parse_evidence_list(data.get("evidence", []))
    description = str(data.get("description", "")).strip() or "No description provided."

    logger.debug("  %s → %s (description: %r)", variant_name, predicted.value, description)

    return TTAVariantResult(
        variant_name=variant_name,
        predicted_class=predicted,
        visible_evidence=evidence,
        raw_description=description,
    )


# ---------------------------------------------------------------------------
# Visual Consistency Module
# ---------------------------------------------------------------------------


def _compute_consistency(results: list[TTAVariantResult]) -> ConsistencyResult:
    """Compute per-class counts and agreement score across TTA variants."""
    counts: dict[DisasterClass, int] = {}
    for r in results:
        counts[r.predicted_class] = counts.get(r.predicted_class, 0) + 1

    majority_class = max(counts, key=lambda c: counts[c])
    majority_count = counts[majority_class]
    agreement_score = round(majority_count / len(results), 3)
    all_agree = agreement_score == 1.0

    disagreements = [
        f"{r.variant_name} predicted '{r.predicted_class.value}' "
        f"(majority is '{majority_class.value}')"
        for r in results
        if r.predicted_class != majority_class
    ]

    return ConsistencyResult(
        agreement_score=agreement_score,
        majority_class=majority_class,
        all_agree=all_agree,
        variant_results=results,
        disagreements=disagreements,
    )


# ---------------------------------------------------------------------------
# Reliability Layer
# ---------------------------------------------------------------------------


def _assess_reliability(
    consistency: ConsistencyResult,
    variant_results: list[TTAVariantResult],
) -> tuple[ReliabilityStatus, list[str]]:
    """Combine consistency score and VLM language to assign reliability status.

    Returns (ReliabilityStatus, list_of_explanatory_notes).
    High agreement_score indicates stability, not correctness.
    """
    notes: list[str] = []

    # Check for uncertainty language in evidence/descriptions
    all_text = " ".join(
        " ".join(r.visible_evidence) + " " + r.raw_description
        for r in variant_results
    ).lower()
    has_uncertainty_language = any(kw in all_text for kw in _UNCERTAINTY_KEYWORDS)

    if consistency.agreement_score < _AGREEMENT_THRESHOLD:
        notes.append(
            f"TTA agreement is {consistency.agreement_score:.0%} "
            f"(threshold {_AGREEMENT_THRESHOLD:.0%}); prediction is unstable."
        )

    if has_uncertainty_language:
        notes.append("VLM output contains uncertainty language.")

    if consistency.majority_class == DisasterClass.UNCERTAIN:
        notes.append("Majority class is 'uncertain'; evidence is ambiguous.")
        return ReliabilityStatus.UNCERTAIN, notes

    # Unreliable: low agreement OR two or more soft signals
    if consistency.agreement_score < _AGREEMENT_THRESHOLD or len(notes) >= 2:
        return ReliabilityStatus.UNRELIABLE, notes

    return ReliabilityStatus.RELIABLE, notes


# ---------------------------------------------------------------------------
# DINOv2 integration (shadow / active mode)
# ---------------------------------------------------------------------------

# Threshold for active mode: mean top-5 similarity below this adds a note.
# Not a hard cutoff — just a signal worth logging.
_DINO_LOW_SIMILARITY_THRESHOLD = 0.30


def _run_dinov2(image: Image.Image, image_path: str) -> Optional[DINOv2Signal]:
    """Extract a DINOv2 embedding and optionally run nearest-neighbor search.

    Returns None on any error so the main pipeline is never blocked.
    Shadow mode: signal is attached to output but does NOT change reliability.
    Active mode: additionally appends a note when mean similarity is very low.
    (The caller decides whether to append the note — this function just builds
    the signal object.)
    """
    try:
        from src.vision.dinov2_encoder import DINOv2Encoder
        from src.vision.similarity import EmbeddingStore

        encoder = DINOv2Encoder.get()
        embedding = encoder.encode(image)

        neighbors: list[SimilarityMatch] = []
        mean_sim: Optional[float] = None

        if settings.dinov2_store_path:
            store_path = Path(settings.dinov2_store_path)
            if store_path.exists():
                store = EmbeddingStore()
                store.load(store_path)
                raw = store.find_nearest(embedding, k=5, exclude_path=image_path)
                neighbors = [SimilarityMatch(**n) for n in raw]
                if neighbors:
                    mean_sim = float(
                        sum(n.cosine_similarity for n in neighbors) / len(neighbors)
                    )
            else:
                logger.warning("DINOv2 store not found: %s", store_path)

        return DINOv2Signal(
            embedding_dim=encoder.embedding_dim,
            nearest_neighbors=neighbors,
            mean_top5_similarity=mean_sim,
            shadow_mode=(settings.dinov2_integration_mode == "shadow"),
            note="",
        )
    except Exception as exc:
        logger.warning("DINOv2 signal failed (non-fatal): %s", exc)
        return None


# ---------------------------------------------------------------------------
# Agent entry point
# ---------------------------------------------------------------------------


def run(input: VisionInput) -> VisionOutput:
    """Run the Vision Agent: TTA → consistency → reliability → VisionOutput."""
    logger.info("Vision agent started | image=%s", input.image_path)

    # -- Load image ----------------------------------------------------------
    try:
        image = Image.open(input.image_path).convert("RGB")
    except Exception as exc:
        logger.error("Failed to open image %s: %s", input.image_path, exc)
        empty_consistency = ConsistencyResult(
            agreement_score=0.0,
            majority_class=DisasterClass.UNCERTAIN,
            all_agree=False,
            variant_results=[],
            disagreements=["Image load failure."],
        )
        return VisionOutput(
            predicted_class=DisasterClass.UNCERTAIN,
            description="Image could not be loaded.",
            visible_evidence=[],
            consistency=empty_consistency,
            reliability_status=ReliabilityStatus.UNRELIABLE,
            reliability_notes=["Image load failure."],
            error=str(exc),
        )

    # -- TTA inference -------------------------------------------------------
    prompts = load_prompt("vision_description", version=2)
    client = get_vlm_client()
    variants = _make_variants(image)

    variant_results: list[TTAVariantResult] = []
    for name, variant_image in variants:
        try:
            result = _infer_variant(client, prompts, name, variant_image)
        except Exception as exc:
            # A transient cloud failure on one variant should not crash the
            # whole request — treat it as an uncertain vote and keep going.
            logger.warning("Variant %s inference failed: %s", name, exc)
            result = TTAVariantResult(
                variant_name=name,
                predicted_class=DisasterClass.UNCERTAIN,
                visible_evidence=[],
                raw_description=f"Inference failed: {exc}",
            )
        variant_results.append(result)

    # -- Consistency ---------------------------------------------------------
    consistency = _compute_consistency(variant_results)

    # -- Reliability ---------------------------------------------------------
    reliability_status, reliability_notes = _assess_reliability(
        consistency, variant_results
    )

    # -- Final class ---------------------------------------------------------
    # When the prediction is unreliable or majority is already uncertain,
    # return UNCERTAIN rather than propagating a potentially wrong class.
    if reliability_status == ReliabilityStatus.UNRELIABLE:
        final_class = DisasterClass.UNCERTAIN
    elif consistency.majority_class == DisasterClass.UNCERTAIN:
        final_class = DisasterClass.UNCERTAIN
    else:
        final_class = consistency.majority_class

    # -- Merge evidence (deduplicated, original variant first) ---------------
    seen: set[str] = set()
    merged_evidence: list[str] = []
    for r in variant_results:
        for item in r.visible_evidence:
            key = item.lower()
            if key not in seen:
                seen.add(key)
                merged_evidence.append(item)

    # Use original variant description as the canonical description.
    main_description = variant_results[0].raw_description

    if final_class == DisasterClass.IRRELEVANT:
        reliability_notes.append("Image appears unrelated to disaster assessment domain.")

    # -- DINOv2 visual similarity (optional, shadow mode by default) ---------
    dinov2_signal: Optional[DINOv2Signal] = None
    if settings.dinov2_enabled:
        dinov2_signal = _run_dinov2(image, input.image_path)
        if (
            dinov2_signal is not None
            and not dinov2_signal.shadow_mode
            and dinov2_signal.mean_top5_similarity is not None
            and dinov2_signal.mean_top5_similarity < _DINO_LOW_SIMILARITY_THRESHOLD
        ):
            note = (
                f"DINOv2 mean top-5 similarity is low "
                f"({dinov2_signal.mean_top5_similarity:.2f} < "
                f"{_DINO_LOW_SIMILARITY_THRESHOLD:.2f}); "
                "image may be visually dissimilar from reference set."
            )
            reliability_notes.append(note)
            dinov2_signal = dinov2_signal.model_copy(update={"note": note})
            # Re-evaluate reliability with the extra note.
            if reliability_status == ReliabilityStatus.RELIABLE and len(reliability_notes) >= 2:
                reliability_status = ReliabilityStatus.UNRELIABLE
                final_class = DisasterClass.UNCERTAIN

    logger.info(
        "Vision agent done | class=%s reliability=%s agreement=%.2f dino=%s",
        final_class.value,
        reliability_status.value,
        consistency.agreement_score,
        "enabled" if settings.dinov2_enabled else "off",
    )

    return VisionOutput(
        predicted_class=final_class,
        description=main_description,
        visible_evidence=merged_evidence,
        consistency=consistency,
        reliability_status=reliability_status,
        reliability_notes=reliability_notes,
        dinov2_signal=dinov2_signal,
    )
