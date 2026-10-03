import uuid
from datetime import datetime, timedelta, timezone

import jwt as pyjwt

from app.config import settings


def create_token(user_id: str) -> str:
    """Create a signed JWT. The token carries only identity, never roles."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "iat": now,
        "exp": now + timedelta(minutes=settings.JWT_EXPIRE_MINUTES),
        "jti": str(uuid.uuid4()),
    }
    return pyjwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    """Verify signature and expiry. Raises on any failure."""
    return pyjwt.decode(
        token,
        settings.JWT_SECRET,
        algorithms=[settings.JWT_ALGORITHM],
    )
