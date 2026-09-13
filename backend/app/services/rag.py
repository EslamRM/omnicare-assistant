"""
RAG service — sits between the agent and the retriever.

Responsible for:
1. Applying the "not confident enough" fallback (Section 13: no relevant
   result -> say so, never hallucinate).
2. Formatting retrieved chunks into citations the agent/LLM can quote
   verbatim rather than inventing (Section 12: citations must come from
   retrieved content, never fabricated).
"""
from dataclasses import dataclass

from app.core.config import get_settings
from app.rag.retriever import PolicyRetriever

NOT_FOUND_MESSAGE = (
    "I couldn't find enough information in the policy documents to answer "
    "that confidently. Please contact support for details on this specific case."
)


@dataclass
class RagResult:
    grounded: bool
    context_chunks: list[str]
    sources: list[dict[str, str]]


class RagService:
    def __init__(self):
        settings = get_settings()
        self._settings = settings
        self._retriever = PolicyRetriever(
            policy_path=settings.policy_doc_path,
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
        )

    def query(self, question: str) -> RagResult:
        settings = self._settings
        hits = self._retriever.retrieve(question, top_k=settings.rag_top_k)

        relevant = [h for h in hits if h.score >= settings.rag_min_relevance]

        if not relevant:
            return RagResult(grounded=False, context_chunks=[], sources=[])

        return RagResult(
            grounded=True,
            context_chunks=[h.text for h in relevant],
            sources=[{"section": h.section, "document": "sample_policy.md"} for h in relevant],
        )
