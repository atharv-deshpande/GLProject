from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.document import Document, DocumentChunk, DocumentVersion
from app.modules.embeddings.ollama_embeddings import OllamaEmbeddingService
from app.modules.retrieval.qdrant_store import QdrantVectorStore


class IndexingError(RuntimeError):
    """Raised when a document cannot be indexed."""


class DocumentIndexingService:
    def __init__(
        self,
        embedder: OllamaEmbeddingService | None = None,
        vector_store: QdrantVectorStore | None = None,
        batch_size: int = 32,
    ) -> None:
        self.embedder = embedder or OllamaEmbeddingService()
        self.vector_store = vector_store or QdrantVectorStore()
        self.batch_size = batch_size

    def index_document(self, db: Session, document_id) -> int:
        document = db.get(Document, document_id)
        if document is None:
            raise IndexingError("Document not found.")

        version = db.scalar(
            select(DocumentVersion)
            .where(DocumentVersion.document_id == document.id)
            .order_by(DocumentVersion.version_number.desc())
            .limit(1)
        )
        if version is None:
            raise IndexingError("Document version not found.")

        chunks = db.scalars(
            select(DocumentChunk)
            .where(DocumentChunk.version_id == version.id)
            .order_by(DocumentChunk.chunk_index)
        ).all()

        indexed = 0
        for start in range(0, len(chunks), self.batch_size):
            batch = chunks[start:start + self.batch_size]
            vectors = self.embedder.embed([chunk.content for chunk in batch])
            rows = [
                {
                    "chunk_id": chunk.id,
                    "document_id": document.id,
                    "department_id": document.department_id,
                    "version_id": version.id,
                    "chunk_index": chunk.chunk_index,
                    "page_number": chunk.page_number,
                    "section_title": chunk.section_title,
                    "document_name": document.original_filename,
                }
                for chunk in batch
            ]
            self.vector_store.upsert_chunks(rows, vectors)
            indexed += len(batch)

        return indexed
