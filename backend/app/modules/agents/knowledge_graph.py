from __future__ import annotations

from typing import TypedDict
from uuid import UUID

from sqlalchemy.orm import Session

from app.dependencies.auth import get_current_user
from app.models.user import User
from app.modules.rag.answer_service import OllamaAnswerService
from app.modules.retrieval.authorization import authorized_department_ids
from app.modules.retrieval.qdrant_store import QdrantVectorStore
from app.modules.embeddings.ollama_embeddings import OllamaEmbeddingService
from app.schemas.knowledge import KnowledgeQuery
from app.api.v1.knowledge import retrieve_authorized


class KnowledgeState(TypedDict, total=False):
    question: str
    # These rows must already have been reloaded and authorized by PostgreSQL.
    authorized_hits: list[dict]
    answer: str
    insufficient_evidence: bool


def _retrieve(state: KnowledgeState) -> KnowledgeState:
    """Pass through only PostgreSQL-authorized rows; never trust Qdrant payload text."""
    hits = state.get("authorized_hits", [])
    return {
        "authorized_hits": hits,
        "insufficient_evidence": not bool(hits),
    }


def _answer(state: KnowledgeState) -> KnowledgeState:
    hits = state.get("authorized_hits", [])
    if state.get("insufficient_evidence") or not hits:
        return {
            "answer": "The authorized knowledge base does not contain sufficient evidence.",
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
    return {
        "answer": OllamaAnswerService().answer(state["question"], sources),
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
    Run the agent only after the normal RAG authorization boundary.

    Qdrant is used only to find candidate chunk IDs. retrieve_authorized then
    reloads chunk text and document ownership from PostgreSQL and applies the
    user's current department memberships before any text reaches the LLM.
    """
    allowed_department_ids = authorized_department_ids(db, user, department_id)
    if not allowed_department_ids:
        return {
            "answer": "The authorized knowledge base does not contain sufficient evidence.",
            "authorized_hits": [],
            "insufficient_evidence": True,
        }

    authorized_hits = retrieve_authorized(
        KnowledgeQuery(query=question, department_id=department_id),
        db,
        user,
    )
    return build_knowledge_graph().invoke(
        {
            "question": question,
            "authorized_hits": authorized_hits,
        }
    )
