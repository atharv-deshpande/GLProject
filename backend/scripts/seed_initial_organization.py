"""Seed EKIP departments and initial users.

Passwords are read from environment variables and are never stored in this script.
Set USER_<EMAIL_LOCAL_PART>_PASSWORD for each user, for example:
USER_MUKESH_JHA_PASSWORD. Existing users are not overwritten.
"""
import os
import re
import sys

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.user import Department, Role, User, UserDepartment
from app.modules.auth.password import hash_password


DEPARTMENTS = [
    ("Ethics and Compliance", "ETHICS_COMPLIANCE"),
    ("Human resource", "HUMAN_RESOURCE"),
    ("Finance and auditing", "FINANCE_AUDITING"),
    ("Facility and safety", "FACILITY_SAFETY"),
    ("Legal and risk", "LEGAL_RISK"),
    ("Information technology and security", "IT_SECURITY"),
    ("Marketing, Investor relations and Communications", "MARKETING_IR_COMMUNICATIONS"),
    ("AI usage", "AI_USAGE"),
]

# Seed records use the roles shown in the supplied roster.
# HR employees are assigned to Human resource. Other employees start with no
# department membership until an administrator assigns their actual department.
USERS = [
    ("Mukesh.jha@abcerp.com", "USER", []),
    ("Chetan.sinha@abcerp.com", "DEPARTMENT_MANAGER", ["HUMAN_RESOURCE"]),
    ("Rahul.shinde@abcerp.com", "USER", []),
    ("Mukta.doshi@abcerp.com", "USER", []),
    ("Ramesh.seth@abcerp.com", "ADMIN", []),
    ("Rupali.rao@abcerp.com", "DEPARTMENT_MANAGER", ["HUMAN_RESOURCE"]),
    ("Mayank.iyer@abcerp.com", "USER", []),
]


def password_env_name(email: str) -> str:
    local = email.split("@", 1)[0].upper()
    return "USER_" + re.sub(r"[^A-Z0-9]+", "_", local) + "_PASSWORD"


def seed() -> None:
    missing = [password_env_name(email) for email, _, _ in USERS if not os.getenv(password_env_name(email))]
    if missing:
        print("Missing environment variables for user passwords:")
        for name in missing:
            print(f"  {name}")
        print("Set each variable in the current PowerShell session and rerun.")
        sys.exit(2)

    db = SessionLocal()
    created_departments = 0
    created_users = 0
    created_memberships = 0

    try:
        department_by_code = {}
        for name, code in DEPARTMENTS:
            department = db.scalar(select(Department).where(Department.code == code))
            if department is None:
                department = Department(name=name, code=code, is_active=True)
                db.add(department)
                db.flush()
                created_departments += 1
            else:
                # Preserve existing names/status; this script is safe to re-run.
                if not department.is_active:
                    department.is_active = True
            department_by_code[code] = department

        db.flush()
        for email, role_name, department_codes in USERS:
            user = db.scalar(select(User).where(User.email.ilike(email)))
            if user is None:
                user = User(
                    email=email.lower(),
                    password_hash=hash_password(os.environ[password_env_name(email)]),
                    role=Role[role_name],
                    is_active=True,
                )
                db.add(user)
                db.flush()
                created_users += 1
            else:
                # Do not reset passwords or overwrite roles on existing accounts.
                if not user.is_active:
                    user.is_active = True

            for code in department_codes:
                department = department_by_code[code]
                membership = db.scalar(select(UserDepartment).where(
                    UserDepartment.user_id == user.id,
                    UserDepartment.department_id == department.id,
                ))
                if membership is None:
                    db.add(UserDepartment(user_id=user.id, department_id=department.id))
                    created_memberships += 1

        db.commit()
        print(f"Departments created: {created_departments}")
        print(f"Users created: {created_users}")
        print(f"Department memberships created: {created_memberships}")
        print("Seed completed. Existing passwords and roles were not overwritten.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
