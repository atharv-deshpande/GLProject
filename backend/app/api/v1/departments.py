import re
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.user import Department, Role, User, UserDepartment


router = APIRouter(prefix="/departments", tags=["Departments"])


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if getattr(current_user.role, "value", current_user.role) != Role.ADMIN.value:
        raise HTTPException(status_code=403, detail="Administrator access required.")
    return current_user


class DepartmentCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    code: str | None = Field(default=None, max_length=30)


class DepartmentUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=100)
    is_active: bool | None = None


class DepartmentResponse(BaseModel):
    id: UUID
    name: str
    code: str
    is_active: bool


def make_code(name: str) -> str:
    code = re.sub(r"[^A-Z0-9]+", "_", name.upper()).strip("_")
    return code[:30].strip("_")


@router.get("", response_model=list[DepartmentResponse])
def list_departments(
    include_inactive: bool = False,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = select(Department)
    if not include_inactive or getattr(current_user.role, "value", current_user.role) != Role.ADMIN.value:
        query = query.where(Department.is_active.is_(True))
    return [
        DepartmentResponse(id=row.id, name=row.name, code=row.code, is_active=row.is_active)
        for row in db.scalars(query.order_by(Department.name)).all()
    ]


@router.post("", response_model=DepartmentResponse, status_code=status.HTTP_201_CREATED)
def create_department(
    payload: DepartmentCreate,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    name = payload.name.strip()
    code = (payload.code or make_code(name)).upper()
    if not code:
        raise HTTPException(status_code=422, detail="A valid department code is required.")
    if db.scalar(select(Department.id).where(func.lower(Department.name) == name.lower())):
        raise HTTPException(status_code=409, detail="Department name already exists.")
    if db.scalar(select(Department.id).where(Department.code == code)):
        raise HTTPException(status_code=409, detail="Department code already exists.")
    department = Department(name=name, code=code, is_active=True)
    db.add(department)
    db.commit()
    db.refresh(department)
    return DepartmentResponse(id=department.id, name=department.name, code=department.code, is_active=department.is_active)


@router.patch("/{department_id}", response_model=DepartmentResponse)
def update_department(
    department_id: UUID,
    payload: DepartmentUpdate,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    department = db.get(Department, department_id)
    if department is None:
        raise HTTPException(status_code=404, detail="Department not found.")
    if payload.name is not None:
        name = payload.name.strip()
        duplicate = db.scalar(select(Department.id).where(
            func.lower(Department.name) == name.lower(),
            Department.id != department_id,
        ))
        if duplicate:
            raise HTTPException(status_code=409, detail="Department name already exists.")
        department.name = name
    if payload.is_active is not None:
        if payload.is_active is False:
            from app.models.document import Document
            linked_documents = db.scalar(select(func.count(Document.id)).where(Document.department_id == department_id)) or 0
            if linked_documents:
                raise HTTPException(status_code=409, detail="Cannot deactivate a department that still owns documents. Move or remove its documents first.")
        department.is_active = payload.is_active
    db.commit()
    db.refresh(department)
    return DepartmentResponse(id=department.id, name=department.name, code=department.code, is_active=department.is_active)


@router.put("/{department_id}/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def assign_user_to_department(
    department_id: UUID,
    user_id: UUID,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    department = db.get(Department, department_id)
    user = db.get(User, user_id)
    if department is None or not department.is_active:
        raise HTTPException(status_code=404, detail="Active department not found.")
    if user is None:
        raise HTTPException(status_code=404, detail="User not found.")
    existing = db.scalar(select(UserDepartment).where(
        UserDepartment.user_id == user_id,
        UserDepartment.department_id == department_id,
    ))
    if existing is None:
        db.add(UserDepartment(user_id=user_id, department_id=department_id))
        db.commit()
    return None


@router.delete("/{department_id}/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_user_from_department(
    department_id: UUID,
    user_id: UUID,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    membership = db.scalar(select(UserDepartment).where(
        UserDepartment.user_id == user_id,
        UserDepartment.department_id == department_id,
    ))
    if membership is not None:
        db.delete(membership)
        db.commit()
    return None
