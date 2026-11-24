import hashlib
import logging
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.document import (
    Document, DocumentChunk, DocumentStatus, DocumentVersion,
)
from app.models.user import Department, User, UserDepartment
from app.modules.embeddings.indexing_service import (
    DocumentIndexingService, IndexingError,
)
from app.modules.embeddings.ollama_embeddings import EmbeddingServiceError
from app.modules.ingestion.validators import validate_upload
from app.modules.ingestion.parsers.pdf_parser import parse_pdf, PDFParserError
from app.modules.ingestion.parsers.docx_parser import parse_docx, DOCXParserError
from app.modules.ingestion.parsers.html_parser import parse_html, HTMLParserError
from app.modules.ingestion.processing.ingestion_service import process_parsed_document
from app.modules.ingestion.processing.file_storage import (
    FileStorageError, delete_file, store_file,
)
from app.modules.retrieval.qdrant_store import QdrantVectorStore, VectorStoreError
from app.modules.graph.neo4j_store import GraphStoreError, Neo4jGraphStore

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/documents", tags=["Documents"])


class DocumentUploadResponse(BaseModel):
    document_id: UUID
    document_name: str
    file_type: str
    status: str
    file_size: int
    total_chunks: int
    total_tokens: int
    department_id: UUID
    version_number: int
    checksum: str
    metadata: dict


class IndexResponse(BaseModel):
    document_id: UUID
    indexed_chunks: int
    status: str


def authorize_department(db: Session, user: User, department_id: UUID) -> None:
    department = db.scalar(
        select(Department).where(
            Department.id == department_id,
            Department.is_active.is_(True),
        )
    )
    if department is None:
        raise HTTPException(status_code=404, detail="Department not found.")

    role = getattr(user.role, "value", user.role)
    if role == "ADMIN":
        return
    if role != "DEPARTMENT_MANAGER":
        raise HTTPException(
            status_code=403,
            detail="Only administrators and department managers can upload documents.",
        )

    membership = db.scalar(
        select(UserDepartment.id).where(
            UserDepartment.user_id == user.id,
            UserDepartment.department_id == department_id,
        )
    )
    if membership is None:
        raise HTTPException(
            status_code=403,
            detail="You are not authorized to upload to this department.",
        )


@router.post(
    "/upload",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    file: UploadFile = File(...),
    department_id: UUID = Form(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    authorize_department(db, current_user, department_id)
    validated = await validate_upload(file)

    try:
        if validated.extension == ".pdf":
            parsed = parse_pdf(validated.content, validated.filename)
        elif validated.extension == ".docx":
            parsed = parse_docx(validated.content, validated.filename)
        elif validated.extension in {".html", ".htm"}:
            parsed = parse_html(validated.content, validated.filename)
        else:
            raise HTTPException(status_code=415, detail="Unsupported document format.")
        result = process_parsed_document(parsed)
    except (PDFParserError, DOCXParserError, HTMLParserError) as exc:
        raise HTTPException(status_code=422, detail=f"Document parsing failed: {exc}") from exc
    except TypeError as exc:
        raise HTTPException(status_code=422, detail="Document processing failed.") from exc

    checksum = hashlib.sha256(validated.content).hexdigest()
    storage_path: str | None = None
    try:
        storage_path = store_file(
            validated.content,
            validated.extension,
            settings.DOCUMENT_STORAGE_ROOT,
        )
        title = result.metadata.get("title") or Path(validated.filename).stem
        document = Document(
            title=str(title)[:255],
            original_filename=validated.filename[:255],
            file_type=result.file_type,
            department_id=department_id,
            uploaded_by=current_user.id,
            status=DocumentStatus.COMPLETED,
        )
        db.add(document)
        db.flush()

        version = DocumentVersion(
            document_id=document.id,
            version_number=1,
            checksum=checksum,
            storage_path=storage_path,
            file_size=validated.size,
        )
        db.add(version)
        db.flush()

        db.add_all([
            DocumentChunk(
                document_id=document.id,
                version_id=version.id,
                chunk_index=chunk.chunk_index,
                content=chunk.content,
                page_number=chunk.page_number,
                section_title=chunk.section_title,
                token_count=chunk.token_count,
                metadata_json={
                    "source_block_start": chunk.source_block_start,
                    "source_block_end": chunk.source_block_end,
                },
            )
            for chunk in result.chunks
        ])

        db.commit()
        db.refresh(document)
        return DocumentUploadResponse(
            document_id=document.id,
            document_name=document.original_filename,
            file_type=document.file_type,
            status=document.status.value,
            file_size=validated.size,
            total_chunks=result.total_chunks,
            total_tokens=result.total_tokens,
            department_id=document.department_id,
            version_number=version.version_number,
            checksum=checksum,
            metadata=result.metadata,
        )

    except FileStorageError as exc:
        db.rollback()
        logger.exception("Document storage failed for %s", validated.filename)
        raise HTTPException(
            status_code=500,
            detail="Unable to store uploaded document. Check backend logs.",
        ) from exc
    except Exception as exc:
        db.rollback()
        logger.exception("Document persistence failed for %s", validated.filename)
        if storage_path:
            try:
                delete_file(storage_path, settings.DOCUMENT_STORAGE_ROOT)
            except FileStorageError:
                logger.exception("Orphan-file cleanup failed for %s", storage_path)
        raise HTTPException(
            status_code=500,
            detail="Document persistence failed. Check backend logs.",
        ) from exc


@router.post("/{document_id}/index", response_model=IndexResponse)
def index_document(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    document = db.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    authorize_department(db, current_user, document.department_id)

    try:
        count = DocumentIndexingService().index_document(db, document_id)
    except IndexingError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (EmbeddingServiceError, VectorStoreError) as exc:
        logger.exception("Indexing failed for document %s", document_id)
        raise HTTPException(
            status_code=503,
            detail="Document indexing is temporarily unavailable.",
        ) from exc

    return IndexResponse(
        document_id=document_id,
        indexed_chunks=count,
        status="indexed",
    )



@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Delete source and derived document data.

    External stores are cleaned before PostgreSQL is committed. Each cleanup
    operation is idempotent, so a failed request can safely be retried. The
    PostgreSQL record remains available for retry if any derived-store cleanup
    fails.
    """
    document = db.get(Document, document_id)
    if document is None:
        # DELETE is idempotent from the caller's perspective.
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    authorize_department(db, current_user, document.department_id)
    versions = db.scalars(
        select(DocumentVersion).where(DocumentVersion.document_id == document_id)
    ).all()

    try:
        # Filesystem deletion is safe to repeat; paths are validated beneath root.
        for version in versions:
            delete_file(version.storage_path, settings.DOCUMENT_STORAGE_ROOT)

        # Remove vector points even if the collection currently has no points.
        QdrantVectorStore().delete_document(document_id)

        # Neo4j is an optional derived store; enable only when provisioned.
        if settings.NEO4J_ENABLED:
            Neo4jGraphStore().delete_document_graph(str(document_id))

        db.delete(document)
        db.commit()
    except (FileStorageError, VectorStoreError, GraphStoreError) as exc:
        db.rollback()
        logger.exception("Document lifecycle cleanup failed for %s", document_id)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Document cleanup is incomplete. Retry the deletion after the dependent service is available.",
        ) from exc
    except Exception as exc:
        db.rollback()
        logger.exception("Document deletion failed for %s", document_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Document deletion failed. The document record was retained for safe retry.",
        ) from exc

    return Response(status_code=status.HTTP_204_NO_CONTENT)
