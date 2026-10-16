"""Knowledge (RAG) agent: turns the incident into search queries and retrieves guidance.

Tools: the retriever (dense search in Chroma filtered on the incident type, cross-encoder
reranking) and, for reports in a language the corpus does not contain, the LLM (query rewrite
into English, prompt ``rag_query_rewrite``) whose query is fused with the raw report. It never
generates guidance itself: it returns the retrieved passages with their provenance, and an empty
list when nothing relevant was found.

Defaults come from the retrieval evaluation of 2026-10-17 (evaluation/results/retrieval_20261017_0003.md,
keyword labels, 34 queries; provisional until the pooled human judgments are in):
    - reranking: best configuration overall (MRR@10 0.726 vs 0.696, Hit@5 0.912 vs 0.824)
    - threshold 0.785: best balanced threshold for that configuration (keeps 87% of relevant
      hits, rejects 5/6 out-of-scope queries)
    - rewrite + fusion only for languages absent from the corpus: it raised Arabic MRR@10
      (0.675 -> 0.875) but lowered French (0.705 -> 0.500), see FAILURES.md PROMPT-01..03
"""

from pydantic import BaseModel, Field

from src.llm import client
from src.llm.prompt_loader import build_messages, load_prompt
from src.rag.retriever import retrieve
from src.schemas import IncidentInfo, KnowledgeResult
from src.utils.logging_utils import get_logger

logger = get_logger(__name__)

DEFAULT_THRESHOLD = 0.785
CORPUS_LANGUAGES = {"en", "fr"}  # languages the knowledge base documents are written in


class RewrittenQuery(BaseModel):
    """Structured output of the query-rewrite prompt."""

    query: str = Field(min_length=3, description="Concise English search query.")


def rewrite_query(report: str, incident_type: str | None = None, version: int | None = None) -> str:
    """Rewrite an incident report into one English search query."""
    prompt = load_prompt("rag_query_rewrite", version)
    messages = build_messages(prompt, report=report, incident_type=incident_type or "unknown")
    return client.chat_json(messages, RewrittenQuery).query.strip()


def run(
    incident: IncidentInfo,
    threshold: float = DEFAULT_THRESHOLD,
    rewrite: bool | None = None,
    rerank: bool = True,
) -> KnowledgeResult:
    """Retrieve response guidance for an incident.

    Args:
        incident: Output of the incident agent; its reported observations form the query.
        threshold: Minimum cosine similarity of a retrieved passage.
        rewrite: Add an LLM-rewritten English query fused with the raw one. None (default)
            enables it only when the report language is not in ``CORPUS_LANGUAGES``.
        rerank: Rerank candidates with the cross-encoder.
    """
    report = "; ".join(incident.reported_observations) or str(incident.incident_type)
    if rewrite is None:
        rewrite = incident.language not in CORPUS_LANGUAGES
    extra: list[str] = []
    if rewrite:
        try:
            extra = [rewrite_query(report, incident.incident_type)]
        except (client.LLMError, client.LLMOutputError) as exc:
            logger.warning("Query rewrite failed (%s); retrieving with the raw report only", exc)
    chunks = retrieve(
        report, disaster_type=incident.incident_type, threshold=threshold, extra_queries=extra, rerank=rerank
    )
    query_used = " || ".join([report, *extra])
    return KnowledgeResult(query_used=query_used, chunks=chunks)
