"""Pydantic data contracts for all DisasterAI agents."""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Shared enumerations
# ---------------------------------------------------------------------------


class DisasterClass(str, Enum):
    FIRE = "fire"
    FLOOD = "flood"
    NORMAL = "normal"        # disaster-relevant scene, no active incident
    IRRELEVANT = "irrelevant"  # image is not disaster-domain at all (selfie, document, meme...)
    UNCERTAIN = "uncertain"


class ReliabilityStatus(str, Enum):
    RELIABLE = "reliable"
    UNRELIABLE = "unreliable"
    UNCERTAIN = "uncertain"


# ---------------------------------------------------------------------------
# Vision Agent schemas
# ---------------------------------------------------------------------------


class TTAVariantResult(BaseModel):
    """Inference result for a single Test-Time Augmentation variant."""

    variant_name: str
    predicted_class: DisasterClass
    visible_evidence: list[str]
    raw_description: str


class ConsistencyResult(BaseModel):
    """Agreement statistics across TTA variants."""

    agreement_score: float = Field(ge=0.0, le=1.0)
    majority_class: DisasterClass
    all_agree: bool
    variant_results: list[TTAVariantResult]
    disagreements: list[str]


class VisionInput(BaseModel):
    """Input to the Vision Agent."""

    image_path: str
    incident_text: Optional[str] = None  # optional text context for the VLM


# ---------------------------------------------------------------------------
# DINOv2 similarity schemas (shadow-mode by default)
# ---------------------------------------------------------------------------


class SimilarityMatch(BaseModel):
    """One nearest-neighbor result from the DINOv2 embedding store."""

    image_path: str
    cosine_similarity: float = Field(ge=-1.0, le=1.0)


class DINOv2Signal(BaseModel):
    """Visual similarity information produced by the DINOv2 encoder.

    In shadow_mode=True the signal is logged only and does not influence
    the reliability decision.  Low/high similarity does NOT imply the
    prediction is wrong/correct — it is a descriptive signal only.
    """

    embedding_dim: int
    nearest_neighbors: list[SimilarityMatch]
    mean_top5_similarity: Optional[float] = None
    shadow_mode: bool = True
    note: str = ""


# ---------------------------------------------------------------------------
# Vision Agent output
# ---------------------------------------------------------------------------


class VisionOutput(BaseModel):
    """Structured output of the Vision Agent."""

    predicted_class: DisasterClass
    description: str
    visible_evidence: list[str]
    consistency: ConsistencyResult
    reliability_status: ReliabilityStatus
    reliability_notes: list[str]
    dinov2_signal: Optional[DINOv2Signal] = None  # None when DINOV2_ENABLED=False
    error: Optional[str] = None
