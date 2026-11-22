from __future__ import annotations

from typing import TypedDict

from app.modules.rag.answer_service import OllamaAnswerService


class KnowledgeState(TypedDict, total=False):
    question: str
    context: str
    answer: str


def _retrieve(state: KnowledgeState) -> KnowledgeState:
    # Retrieval is intentionally supplied by the caller; graph nodes do not
    # access databases or vector stores directly.
    return {"context": state.get("context", "")}


def _answer(state: KnowledgeState) -> KnowledgeState:
    context = state.get("context", "").strip()
    if not context:
        return {"answer": "The supplied knowledge context is empty."}
    sources = [{"source_id": "S1", "document_name": "Authorized context",
                "page_number": None, "section_title": None, "content": context}]
    return {"answer": OllamaAnswerService().answer(state["question"], sources)}


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
