from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import Department, Role, User, UserDepartment


def authorized_department_ids(
    db: Session,
    user: User,
    requested_department_id: UUID | None = None,
) -> list[UUID]:
    role = getattr(user.role, "value", user.role)
    if role == Role.ADMIN.value:
        query = select(Department.id).where(Department.is_active.is_(True))
        if requested_department_id:
            query = query.where(Department.id == requested_department_id)
        ids = list(db.scalars(query).all())
    else:
        query = (
            select(UserDepartment.department_id)
            .join(Department, Department.id == UserDepartment.department_id)
            .where(
                UserDepartment.user_id == user.id,
                Department.is_active.is_(True),
            )
        )
        if requested_department_id:
            query = query.where(UserDepartment.department_id == requested_department_id)
        ids = list(db.scalars(query).all())

    if requested_department_id and not ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to access this department.",
        )
    return ids
