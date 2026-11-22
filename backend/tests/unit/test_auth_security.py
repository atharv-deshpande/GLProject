from uuid import uuid4

from app.modules.auth.password import (
    hash_password,
    verify_password,
)
from app.modules.auth.jwt import (
    create_access_token,
    decode_access_token,
)


def test_password_hashing():
    password = "SecurePassword@123"

    password_hash = hash_password(password)

    assert password_hash.startswith("$argon2id$")
    assert verify_password(password, password_hash)


def test_wrong_password_rejected():
    password_hash = hash_password("SecurePassword@123")

    assert not verify_password(
        "WrongPassword@123",
        password_hash,
    )


def test_jwt_creation_and_validation():
    user_id = uuid4()

    token = create_access_token(user_id)

    assert decode_access_token(token) == user_id


def test_invalid_jwt_rejected():
    assert decode_access_token("invalid-token") is None