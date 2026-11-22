from uuid import UUID

from pydantic import BaseModel, Field


class KnowledgeQuery(BaseModel):
    query: str = Field(min_length=2, max_length=4000)
    department_id: UUID | None = None
    top_k: int | None = Field(default=None, ge=1, le=20)


class SearchHit(BaseModel):
    chunk_id: UUID
    document_id: UUID
    document_name: str
    department_id: UUID
    page_number: int | None = None
    section_title: str | None = None
    content: str
    score: float


class SearchResponse(BaseModel):
    query: str
    results: list[SearchHit]
    total: int


class Citation(BaseModel):
    source_id: str
    document_id: UUID
    document_name: str
    page_number: int | None = None
    section_title: str | None = None
    chunk_id: UUID


class ChatResponse(BaseModel):
    query: str
    answer: str
    citations: list[Citation]
    insufficient_evidence: bool
