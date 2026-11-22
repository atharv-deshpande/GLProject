import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.document import Document, DocumentChunk
from app.models.user import User
from app.schemas.knowledge import (
    ChatResponse,
    Citation,
    KnowledgeQuery,
    SearchHit,
    SearchResponse,
)
from app.modules.embeddings.ollama_embeddings import (
    EmbeddingServiceError,
    OllamaEmbeddingService,
)
from app.modules.rag.answer_service import GenerationError, OllamaAnswerService
from app.modules.retrieval.authorization import authorized_department_ids
from app.modules.retrieval.qdrant_store import QdrantVectorStore, VectorStoreError

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Knowledge"])


def retrieve_authorized(
    payload: KnowledgeQuery,
    db: Session,
    user: User,
) -> list[dict]:
    department_ids = authorized_department_ids(
        db, user, payload.department_id
    )
    if not department_ids:
        return []

    try:
        query_vector = OllamaEmbeddingService().embed_query(payload.query)
        candidates = QdrantVectorStore().search(
            query_vector,
            department_ids,
            payload.top_k if payload.top_k is not None else settings.RAG_TOP_K,
        )
    except (EmbeddingServiceError, VectorStoreError) as exc:
        logger.exception("Knowledge retrieval failed")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Knowledge retrieval is temporarily unavailable.",
        ) from exc

    # Defense in depth: resolve every vector hit against PostgreSQL and current ACL.
    candidate_ids: list[UUID] = []
    for item in candidates:
        try:
            candidate_ids.append(UUID(str(item["chunk_id"])))
        except (ValueError, TypeError, KeyError):
            logger.warning("Ignoring Qdrant point with an invalid chunk ID.")

    rows = db.execute(
        select(DocumentChunk, Document)
        .join(Document, Document.id == DocumentChunk.document_id)
        .where(
            DocumentChunk.id.in_(candidate_ids),
            Document.department_id.in_(department_ids),
        )
    ).all() if candidate_ids else []

    row_map = {chunk.id: (chunk, document) for chunk, document in rows}
    hits = []
    for item in candidates:
        try:
            chunk_id = UUID(str(item["chunk_id"]))
        except (ValueError, TypeError, KeyError):
            continue
        pair = row_map.get(chunk_id)
        if not pair:
            continue
        chunk, document = pair
        score = float(item.get("score", 0.0))
        if score < settings.RAG_MIN_SCORE:
            continue
        hits.append(
            {
                "chunk_id": chunk.id,
                "document_id": document.id,
                "document_name": document.original_filename,
                "department_id": document.department_id,
                "page_number": chunk.page_number,
                "section_title": chunk.section_title,
                "content": chunk.content,
                "score": score,
            }
        )
    return hits


@router.post("/api/v1/search", response_model=SearchResponse)
def search_knowledge(
    payload: KnowledgeQuery,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    hits = retrieve_authorized(payload, db, current_user)
    return SearchResponse(
        query=payload.query,
        results=[SearchHit(**hit) for hit in hits],
        total=len(hits),
    )


@router.post("/api/v1/chat", response_model=ChatResponse)
def chat_knowledge(
    payload: KnowledgeQuery,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    hits = retrieve_authorized(payload, db, current_user)

    if not hits:
        return ChatResponse(
            query=payload.query,
            answer=(
                "I could not find sufficiently relevant information in the "
                "documents you are authorized to access."
            ),
            citations=[],
            insufficient_evidence=True,
        )

    sources = [
        {
            "source_id": f"S{index}",
            "document_name": hit["document_name"],
            "page_number": hit["page_number"],
            "section_title": hit["section_title"],
            "content": hit["content"],
        }
        for index, hit in enumerate(hits, start=1)
    ]

    try:
        answer = OllamaAnswerService().answer(payload.query, sources)
    except GenerationError as exc:
        logger.exception("Answer generation failed")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Answer generation is temporarily unavailable.",
        ) from exc

    citations = [
        Citation(
            source_id=source["source_id"],
            document_id=hit["document_id"],
            document_name=hit["document_name"],
            page_number=hit["page_number"],
            section_title=hit["section_title"],
            chunk_id=hit["chunk_id"],
        )
        for source, hit in zip(sources, hits)
    ]

    return ChatResponse(
        query=payload.query,
        answer=answer,
        citations=citations,
        insufficient_evidence=False,
    )
