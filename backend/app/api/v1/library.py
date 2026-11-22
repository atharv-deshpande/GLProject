from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.document import Document
from app.models.user import Department, User
from app.modules.retrieval.authorization import authorized_department_ids

router = APIRouter(prefix="/library", tags=["Document Library"])


class LibraryDocument(BaseModel):
    id: UUID
    name: str
    file_type: str
    department_id: UUID
    department_name: str
    status: str
    created_at: datetime


class LibraryResponse(BaseModel):
    items: list[LibraryDocument]
    total: int


@router.get("/documents", response_model=LibraryResponse)
def list_documents(
    department_id: UUID | None = Query(default=None),
    search: str | None = Query(default=None, max_length=200),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    allowed_ids = authorized_department_ids(db, current_user, department_id)
    if not allowed_ids:
        return LibraryResponse(items=[], total=0)

    query = (
        select(Document, Department.name)
        .join(Department, Department.id == Document.department_id)
        .where(Document.department_id.in_(allowed_ids))
    )
    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.where(Document.original_filename.ilike(term))

    count_query = select(func.count(Document.id)).where(Document.department_id.in_(allowed_ids))
    if search and search.strip():
        count_query = count_query.where(Document.original_filename.ilike(f"%{search.strip()}%"))
    total = db.scalar(count_query) or 0

    rows = db.execute(
        query.order_by(Document.created_at.desc()).offset(offset).limit(limit)
    ).all()
    return LibraryResponse(
        total=total,
        items=[
            LibraryDocument(
                id=document.id,
                name=document.original_filename,
                file_type=document.file_type,
                department_id=document.department_id,
                department_name=department_name,
                status=document.status.value,
                created_at=document.created_at,
            )
            for document, department_name in rows
        ],
    )
