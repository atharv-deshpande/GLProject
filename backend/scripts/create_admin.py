import getpass
import sys

from sqlalchemy import func, select

from app.core.database import SessionLocal
from app.models.user import Role, User
from app.modules.auth.password import hash_password


def create_admin():
    db = SessionLocal()

    try:
        existing_admin = db.scalar(
            select(User).where(User.role == Role.ADMIN)
        )

        if existing_admin:
            print("An administrator already exists. Bootstrap stopped.")
            return

        email = input("Admin email: ").strip().lower()

        if not email or "@" not in email:
            print("Invalid email address.")
            sys.exit(1)

        existing_user = db.scalar(
            select(User).where(
                func.lower(User.email) == email
            )
        )

        if existing_user:
            print("This email is already registered.")
            sys.exit(1)

        password = getpass.getpass("Admin password: ")
        confirm_password = getpass.getpass("Confirm password: ")

        if password != confirm_password:
            print("Passwords do not match.")
            sys.exit(1)

        if len(password) < 12 or len(password) > 128:
            print("Password must contain 12–128 characters.")
            sys.exit(1)

        admin = User(
            email=email,
            password_hash=hash_password(password),
            role=Role.ADMIN,
            is_active=True,
        )

        db.add(admin)
        db.commit()

        print(f"Administrator created successfully: {email}")

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


if __name__ == "__main__":
    create_admin()