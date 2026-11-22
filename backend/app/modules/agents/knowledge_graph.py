from __future__ import annotations

import re
from typing import TypedDict
from uuid import UUID

from sqlalchemy.orm import Session

from app.api.v1.knowledge import retrieve_authorized, validate_citation_markers
from app.models.user import User
from app.modules.rag.answer_service import OllamaAnswerService
from app.schemas.knowledge import KnowledgeQuery


class KnowledgeState(TypedDict, total=False):
    question: str
    authorized_hits: list[dict]
    answer: str
    citations: list[dict]
    insufficient_evidence: bool


def _retrieve(state: KnowledgeState) -> KnowledgeState:
    """Consume only PostgreSQL-authorized rows supplied by the API boundary."""
    hits = state.get("authorized_hits", [])
    return {"authorized_hits": hits, "insufficient_evidence": not bool(hits)}


def _answer(state: KnowledgeState) -> KnowledgeState:
    hits = state.get("authorized_hits", [])
    if state.get("insufficient_evidence") or not hits:
        return {
            "answer": "The authorized knowledge base does not contain sufficient evidence.",
            "citations": [],
            "insufficient_evidence": True,
        }

    sources = [
        {
            "source_id": f"S{i}",
            "document_name": hit["document_name"],
            "page_number": hit.get("page_number"),
            "section_title": hit.get("section_title"),
            "content": hit["content"],
        }
        for i, hit in enumerate(hits, 1)
    ]
    answer = OllamaAnswerService().answer(state["question"], sources)
    answer, cited_ids = validate_citation_markers(answer, sources)
    citations = [
        {
            "source_id": source["source_id"],
            "document_id": hit["document_id"],
            "document_name": hit["document_name"],
            "page_number": hit.get("page_number"),
            "section_title": hit.get("section_title"),
            "chunk_id": hit["chunk_id"],
        }
        for source, hit in zip(sources, hits)
        if source["source_id"] in cited_ids
    ]
    return {
        "answer": answer,
        "citations": citations,
        "insufficient_evidence": False,
    }


def build_knowledge_graph():
    """Build a fixed, read-only retrieve→answer graph; LangGraph is optional."""
    try:
        from langgraph.graph import END, START, StateGraph
    except ImportError as exc:
        raise RuntimeError("Install langgraph to run the Day 8 agent workflow.") from exc

    graph = StateGraph(KnowledgeState)
    graph.add_node("retrieve", _retrieve)
    graph.add_node("answer", _answer)
    graph.add_edge(START, "retrieve")
    graph.add_edge("retrieve", "answer")
    graph.add_edge("answer", END)
    return graph.compile()


def answer_question(
    db: Session,
    user: User,
    question: str,
    department_id: UUID | None = None,
) -> dict:
    """
    Run the agent only after normal RAG authorization.

    Qdrant contributes candidate IDs only; retrieve_authorized reloads chunk
    text and document ownership from PostgreSQL and applies live memberships.
    """
    authorized_hits = retrieve_authorized(
        KnowledgeQuery(query=question, department_id=department_id),
        db,
        user,
    )
    return build_knowledge_graph().invoke(
        {"question": question, "authorized_hits": authorized_hits}
    )
