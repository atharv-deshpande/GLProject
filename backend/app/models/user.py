import enum
import uuid

from sqlalchemy import (
    String,
    Boolean,
    Enum,
    ForeignKey,
    UniqueConstraint
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Role(str, enum.Enum):
    ADMIN = "ADMIN"
    DEPARTMENT_MANAGER = "DEPARTMENT_MANAGER"
    USER = "USER"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4
    )

    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True
    )

    password_hash: Mapped[str] = mapped_column(
        String(255)
    )

    role: Mapped[Role] = mapped_column(
        Enum(Role),
        default=Role.USER
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True
    )


class Department(Base):
    __tablename__ = "departments"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4
    )

    name: Mapped[str] = mapped_column(
        String(100),
        unique=True
    )

    code: Mapped[str] = mapped_column(
        String(30),
        unique=True
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True
    )


class UserDepartment(Base):
    __tablename__ = "user_departments"

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "department_id"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE")
    )

    department_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("departments.id", ondelete="CASCADE")
    )