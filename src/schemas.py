"""Pydantic v2 data contracts shared by all DisasterAI agents.

Each agent takes and returns one of these models. Reported facts, image
observations, retrieved guidance and AI inference live in separate models
and fields so that the origin of every statement stays traceable. Unknown
values are represented with ``None`` or empty lists, never invented.
"""

from enum import StrEnum

from pydantic import BaseModel, Field


class IncidentType(StrEnum):
    """Kind of emergency described in an incident report."""

    FIRE = "fire"
    FLOOD = "flood"
    STRUCTURAL = "structural"
    OTHER = "other"
    UNKNOWN = "unknown"


class EvidenceSource(StrEnum):
    """Where the evidence behind a risk comes from."""

    REPORT = "report"
    IMAGE = "image"
    DOCUMENTS = "documents"


class IncidentInput(BaseModel):
    """Raw incident submitted to the pipeline."""

    text: str = Field(
        min_length=1,
        description="Free-text incident report exactly as submitted by the reporter.",
    )
    image_path: str | None = Field(
        default=None,
        description="Path to an optional image of the scene; None when no image was provided.",
    )


class IncidentInfo(BaseModel):
    """Structured facts extracted from the incident text (reported facts only)."""

    incident_type: IncidentType = Field(
        description="Category of the incident; 'unknown' when the report does not make it clear.",
    )
    location: str | None = Field(
        default=None,
        description="Location as stated in the report; None when not mentioned.",
    )
    language: str = Field(
        description="Language code of the report text, e.g. 'fr', 'ar' or 'en'.",
    )
    reported_observations: list[str] = Field(
        default_factory=list,
        description="Facts explicitly stated by the reporter, without interpretation.",
    )
    missing_information: list[str] = Field(
        default_factory=list,
        description="Important details the report does not provide (e.g. number of people involved).",
    )


class ImageObservations(BaseModel):
    """What is visible in the incident image (image observations only)."""

    observations: list[str] = Field(
        default_factory=list,
        description="Visual elements directly observable in the image.",
    )
    uncertainties: list[str] = Field(
        default_factory=list,
        description="Things that cannot be determined reliably from the image.",
    )
    image_quality_note: str | None = Field(
        default=None,
        description="Comment on image quality issues (blur, darkness, low resolution); None if fine.",
    )


class RetrievedChunk(BaseModel):
    """One passage retrieved from the knowledge base (retrieved guidance)."""

    text: str = Field(description="Text content of the retrieved passage.")
    chunk_id: str = Field(default="", description="Identifier of the chunk in the vector store.")
    source_id: str = Field(description="Identifier of the source document, matching data/sources.csv.")
    title: str = Field(description="Title of the source document.")
    page: int | None = Field(
        default=None,
        description="Page number in the source document; None when not applicable.",
    )
    page_end: int | None = Field(
        default=None,
        description="Last page covered by the passage when it spans several pages.",
    )
    heading: str = Field(
        default="",
        description="Section path of the passage in its document (e.g. 'Before a flood > Evacuation').",
    )
    disaster_type: str = Field(description="Disaster type the source document covers.")
    language: str = Field(description="Language code of the source document.")
    reliability: str = Field(description="Reliability rating of the source, as listed in data/sources.csv.")
    score: float = Field(description="Retrieval relevance score assigned by the retriever.")


class GuidanceItem(BaseModel):
    """One statement of documented guidance, grounded in the retrieved passages."""

    statement: str = Field(description="Guidance relevant to the incident, as stated by the documents.")
    citations: list[str] = Field(
        default_factory=list,
        description="Passages supporting the statement, as 'SOURCE-ID p.N' (e.g. 'FLOOD-01 p.2').",
    )
    quote: str = Field(default="", description="Sentence copied verbatim from a cited passage.")
    quote_verified: bool = Field(
        default=False, description="True when the quote was found verbatim in a cited passage."
    )
    entailment: float | None = Field(
        default=None,
        description="Highest probability (NLI model) that the quote or a cited passage entails the statement; "
        "None when the check was not run.",
    )


class GroundedAnswer(BaseModel):
    """Generated summary of what the retrieved documents say about the incident (retrieved guidance only)."""

    answer: str = Field(description="Short summary of the documented guidance relevant to the incident.")
    guidance: list[GuidanceItem] = Field(
        default_factory=list,
        description="Grounded guidance statements whose quote was verified in a cited passage; "
        "empty when the documents do not cover the incident.",
    )
    unverified_guidance: list[GuidanceItem] = Field(
        default_factory=list,
        description="Statements that failed a check (quote not found in the cited passages, or statement "
        "not entailed by its evidence): kept for transparency, not passed on as evidence.",
    )
    in_scope: bool = Field(
        default=True, description="False when the request is outside the scope of the knowledge base."
    )
    abstained_by_gate: bool = Field(
        default=False,
        description="True when the scope gate stopped generation (untyped incident, no passage above the stricter threshold).",
    )
    retried: bool = Field(
        default=False, description="True when generation was retried because strong passages produced no guidance."
    )
    not_covered: list[str] = Field(
        default_factory=list,
        description="Aspects of the incident the retrieved documents do not address.",
    )
    invalid_citations: int = Field(
        default=0, description="Citations to passages that were not provided (removed from the output)."
    )


class KnowledgeResult(BaseModel):
    """Output of the knowledge (RAG) agent."""

    query_used: str = Field(description="Search query actually sent to the retriever, after any rewriting.")
    chunks: list[RetrievedChunk] = Field(
        default_factory=list,
        description="Retrieved passages; an empty list means nothing relevant was found.",
    )
    answer: GroundedAnswer | None = Field(
        default=None,
        description="Grounded answer generated from the passages; None when generation was not requested.",
    )


class RiskItem(BaseModel):
    """A single potential risk inferred by the risk agent (AI inference)."""

    description: str = Field(description="Description of the potential risk.")
    supporting_evidence: list[str] = Field(
        default_factory=list,
        description="Statements from the report, image or documents that support this risk.",
    )
    evidence_source: EvidenceSource = Field(
        description="Origin of the supporting evidence: report, image or documents.",
    )


class RiskAssessment(BaseModel):
    """Preliminary risk assessment (AI inference, to be checked by a human)."""

    potential_risks: list[RiskItem] = Field(
        default_factory=list,
        description="Potential risks, each tied to its supporting evidence.",
    )
    uncertainties: list[str] = Field(
        default_factory=list,
        description="Gaps or doubts that limit the confidence of the assessment.",
    )
    requires_human_review: bool = Field(
        default=True,
        description="Whether a human must review the assessment; True by default as a safety measure.",
    )


class VerificationResult(BaseModel):
    """Output of the verifier agent, which checks claims against evidence."""

    passed: bool = Field(description="True when every claim is supported by the available evidence.")
    unsupported_claims: list[str] = Field(
        default_factory=list,
        description="Claims that are not backed by the report, image or retrieved documents.",
    )
    feedback: str = Field(description="Explanation of the verification outcome and suggested corrections.")


class FinalReport(BaseModel):
    """Final assessment report produced by the report agent."""

    markdown: str = Field(description="Human-readable report in Markdown.")
    data: dict = Field(
        default_factory=dict,
        description="Machine-readable version of the report content.",
    )


class AgentError(BaseModel):
    """Structured error returned when an agent fails."""

    agent: str = Field(description="Name of the agent that failed.")
    message: str = Field(description="Description of what went wrong.")
    retryable: bool = Field(description="Whether retrying the agent might succeed.")


class PipelineResult(BaseModel):
    """Aggregated output of a full pipeline run.

    Stage outputs after the incident step are optional so that a partial
    result can still be returned when an agent fails; the failure is then
    recorded in ``errors``.
    """

    incident: IncidentInfo = Field(description="Facts extracted from the incident report.")
    image: ImageObservations | None = Field(
        default=None,
        description="Image observations; None when no image was provided or analysis failed.",
    )
    knowledge: KnowledgeResult | None = Field(default=None, description="Retrieved guidance.")
    risk: RiskAssessment | None = Field(default=None, description="Inferred risk assessment.")
    verification: VerificationResult | None = Field(default=None, description="Verifier outcome.")
    report: FinalReport | None = Field(default=None, description="Final generated report.")
    errors: list[AgentError] = Field(
        default_factory=list,
        description="Errors raised by agents during the run; empty when everything succeeded.",
    )
    latency_ms: dict[str, float] = Field(
        default_factory=dict,
        description="Execution time of each agent in milliseconds, keyed by agent name.",
    )
