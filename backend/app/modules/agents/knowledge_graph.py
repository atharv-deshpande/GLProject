from __future__ import annotations

from typing import TypedDict

from app.modules.embeddings.ollama_embeddings import OllamaEmbeddingService
from app.modules.rag.answer_service import OllamaAnswerService
from app.modules.retrieval.authorization import authorized_department_ids
from app.modules.retrieval.qdrant_store import QdrantVectorStore


class KnowledgeState(TypedDict, total=False):
    question: str
    department_ids: list
    hits: list[dict]
    answer: str
    insufficient_evidence: bool


def _retrieve(state: KnowledgeState) -> KnowledgeState:
    if not state.get("department_ids"):
        return {"hits": [], "insufficient_evidence": True}
    vector = OllamaEmbeddingService().embed_query(state["question"])
    hits = QdrantVectorStore().search(vector, state["department_ids"], 5)
    return {"hits": hits, "insufficient_evidence": not bool(hits)}


def _answer(state: KnowledgeState) -> KnowledgeState:
    hits = state.get("hits", [])
    if state.get("insufficient_evidence") or not hits:
        return {
            "answer": "The authorized knowledge base does not contain sufficient evidence.",
            "insufficient_evidence": True,
        }
    # This node accepts only source text supplied in state; it exposes no privileged tools.
    sources = [
        {"source_id": f"S{i}", "document_name": hit.get("document_name", "Unknown"),
         "page_number": hit.get("page_number"), "section_title": hit.get("section_title"),
         "content": hit.get("content", "")}
        for i, hit in enumerate(hits, 1)
    ]
    return {
        "answer": OllamaAnswerService().answer(state["question"], sources),
        "insufficient_evidence": False,
    }


def build_knowledge_graph():
    """Build a fixed retrieve→answer LangGraph; dependency is optional."""
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


def answer_question(db, user, question: str, department_id=None) -> dict:
    """Resolve department access in PostgreSQL before graph execution."""
    allowed = authorized_department_ids(db, user, department_id)
    if not allowed:
        return {
            "answer": "The authorized knowledge base does not contain sufficient evidence.",
            "hits": [],
            "insufficient_evidence": True,
        }
    return build_knowledge_graph().invoke(
        {"question": question, "department_ids": allowed}
    )
