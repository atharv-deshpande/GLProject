from uuid import UUID
from fastapi import APIRouter,Depends
from pydantic import BaseModel
from sqlalchemy import func,select
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.document import Document,DocumentChunk,DocumentStatus
from app.models.user import Department,User
from app.modules.retrieval.authorization import authorized_department_ids
router=APIRouter(prefix="/dashboard",tags=["Dashboard"])
class DepartmentSummary(BaseModel):
    id:UUID
    name:str
    document_count:int
class DashboardSummary(BaseModel):
    total_documents:int
    completed_documents:int
    total_chunks:int
    department_count:int
    departments:list[DepartmentSummary]
@router.get("/summary",response_model=DashboardSummary)
def summary(current_user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    ids=authorized_department_ids(db,current_user)
    if not ids:return DashboardSummary(total_documents=0,completed_documents=0,total_chunks=0,department_count=0,departments=[])
    total=db.scalar(select(func.count(Document.id)).where(Document.department_id.in_(ids))) or 0
    completed=db.scalar(select(func.count(Document.id)).where(Document.department_id.in_(ids),Document.status==DocumentStatus.COMPLETED)) or 0
    chunks=db.scalar(select(func.count(DocumentChunk.id)).join(Document,Document.id==DocumentChunk.document_id).where(Document.department_id.in_(ids))) or 0
    rows=db.execute(select(Department.id,Department.name,func.count(Document.id)).outerjoin(Document,Document.department_id==Department.id)
        .where(Department.id.in_(ids)).group_by(Department.id,Department.name).order_by(Department.name)).all()
    return DashboardSummary(total_documents=total,completed_documents=completed,total_chunks=chunks,department_count=len(rows),
        departments=[DepartmentSummary(id=r[0],name=r[1],document_count=r[2]) for r in rows])
