"""Tests for the Pydantic data contracts in src/schemas.py."""

import pytest
from pydantic import ValidationError

from src.schemas import (
    AgentError,
    EvidenceSource,
    FinalReport,
    ImageObservations,
    IncidentInfo,
    IncidentInput,
    IncidentType,
    KnowledgeResult,
    PipelineResult,
    RetrievedChunk,
    RiskAssessment,
    RiskItem,
    VerificationResult,
)


def _incident() -> IncidentInfo:
    return IncidentInfo(
        incident_type="fire",
        location="Ain Draham",
        language="fr",
        reported_observations=["Fumée visible près de la forêt"],
        missing_information=["Nombre de personnes sur place"],
    )


def _chunk() -> RetrievedChunk:
    return RetrievedChunk(
        text="Evacuate downwind areas first.",
        source_id="S001",
        title="Wildfire response guide",
        page=12,
        disaster_type="fire",
        language="en",
        reliability="high",
        score=0.82,
    )


def test_incident_input_defaults_to_no_image() -> None:
    incident = IncidentInput(text="Water is rising in the street.")
    assert incident.image_path is None


def test_incident_input_rejects_empty_text() -> None:
    with pytest.raises(ValidationError):
        IncidentInput(text="")


def test_incident_info_coerces_enum() -> None:
    assert _incident().incident_type is IncidentType.FIRE


def test_incident_info_rejects_invalid_type() -> None:
    with pytest.raises(ValidationError):
        IncidentInfo(incident_type="earthquake", language="en")


def test_risk_item_rejects_invalid_evidence_source() -> None:
    with pytest.raises(ValidationError):
        RiskItem(description="Fire spread", evidence_source="guess")


def test_risk_assessment_requires_human_review_by_default() -> None:
    assert RiskAssessment().requires_human_review is True


def test_knowledge_result_empty_chunks_allowed() -> None:
    result = KnowledgeResult(query_used="flood evacuation")
    assert result.chunks == []


def test_full_pipeline_result_construction() -> None:
    result = PipelineResult(
        incident=_incident(),
        image=ImageObservations(observations=["Dense smoke above trees"]),
        knowledge=KnowledgeResult(query_used="forest fire evacuation", chunks=[_chunk()]),
        risk=RiskAssessment(
            potential_risks=[
                RiskItem(
                    description="Fire may spread to nearby houses",
                    supporting_evidence=["Fumée visible près de la forêt"],
                    evidence_source=EvidenceSource.REPORT,
                )
            ],
        ),
        verification=VerificationResult(passed=True, feedback="All claims supported."),
        report=FinalReport(markdown="# Report", data={"incident_type": "fire"}),
        latency_ms={"incident_agent": 120.5},
    )
    assert result.knowledge is not None
    assert result.knowledge.chunks[0].source_id == "S001"
    assert result.errors == []


def test_partial_pipeline_result_with_error() -> None:
    result = PipelineResult(
        incident=_incident(),
        errors=[AgentError(agent="vision_agent", message="Invalid JSON", retryable=False)],
    )
    assert result.image is None
    assert result.report is None
    assert result.errors[0].agent == "vision_agent"
