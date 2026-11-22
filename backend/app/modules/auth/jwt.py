from datetime import datetime, timedelta, timezone
from uuid import UUID

import jwt
from jwt import InvalidTokenError

from app.core.config import settings

TOKEN_ISSUER = "ekip"
TOKEN_AUDIENCE = "ekip-api"
ACCESS_TOKEN_TYPE = "access"


def create_access_token(user_id: UUID) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        "iss": TOKEN_ISSUER,
        "aud": TOKEN_AUDIENCE,
        "type": ACCESS_TOKEN_TYPE,
    }
    return jwt.encode(
        payload,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


def decode_access_token(token: str) -> UUID | None:
    """Validate signature, algorithm, issuer, audience and required claims."""
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            issuer=TOKEN_ISSUER,
            audience=TOKEN_AUDIENCE,
            options={"require": ["sub", "exp", "iat", "iss", "aud"]},
        )
        if payload.get("type") != ACCESS_TOKEN_TYPE:
            return None
        return UUID(payload["sub"])
    except (InvalidTokenError, ValueError, TypeError, KeyError):
        return None
