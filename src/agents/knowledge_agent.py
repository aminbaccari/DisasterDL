"""Knowledge (RAG) agent: retrieves documented guidance for an incident and summarises it, grounded.

Tools: the retriever (dense search in Chroma filtered on the incident type, cross-encoder
reranking); the LLM for the grounded answer (prompt ``rag_answer``, every statement cites its
passages, quotes are verified); and, for reports in a language the corpus does not contain, the
LLM query rewrite (prompt ``rag_query_rewrite``) fused with the raw report. It returns the
retrieved passages with their provenance plus the grounded answer; when nothing relevant was
found, both are empty and the answer says so (no LLM call).

Defaults come from the final retrieval evaluation of 2026-10-17 (36 EN/FR queries, labels from the
LLM judging panel; evaluation/results/retrieval_20261017_2028_lenient.md and _2039_strict.md):
    - reranking: best of the pooled configurations under both label sets
      (MRR@10 strict 0.868 vs 0.781 without, lenient 1.000 vs 0.906)
    - threshold 0.785: best balanced threshold with lenient labels (keeps 83% of relevant hits,
      rejects 5/6 out-of-scope queries); 0.830 with strict labels rejects all 6 but keeps 71%
    - rewrite + fusion only for languages absent from the corpus (Arabic, not evaluated in the
      final set). On the 8 French queries fusion did slightly better than reranking with strict
      labels (MRR@10 0.938 vs 0.893), but combining both lowered French (0.750), and 8 queries
      are too few to justify a per-language rule (see FAILURES.md PROMPT-01..03)
"""

from pydantic import BaseModel, Field

from src.llm import client
from src.llm.prompt_loader import build_messages, load_prompt
from src.rag.generate import generate_answer
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
    generate: bool = True,
) -> KnowledgeResult:
    """Retrieve response guidance for an incident.

    Args:
        incident: Output of the incident agent; its reported observations form the query.
        threshold: Minimum cosine similarity of a retrieved passage.
        rewrite: Add an LLM-rewritten English query fused with the raw one. None (default)
            enables it only when the report language is not in ``CORPUS_LANGUAGES``.
        rerank: Rerank candidates with the cross-encoder.
        generate: Add the grounded answer generated from the passages (RAG generation step).
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
    answer = None
    if generate:
        try:
            answer = generate_answer(report, chunks, incident.incident_type)
        except (client.LLMError, client.LLMOutputError) as exc:
            logger.warning("Grounded answer generation failed (%s); returning passages only", exc)
    return KnowledgeResult(query_used=query_used, chunks=chunks, answer=answer)
