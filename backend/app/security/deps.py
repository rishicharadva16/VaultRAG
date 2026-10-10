"""FastAPI dependencies for authentication and authorisation."""

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.db.models import User
from app.db.session import get_db
from app.security.jwt import decode_token
from app.security.users import get_user

# auto_error=False so we control the status code (401, not the default 403).
_bearer = HTTPBearer(auto_error=False)

_INVALID = "Invalid token"


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    """
    Verify the JWT, reload the user from the DB, and reject if missing/inactive.
    Roles are ALWAYS read from the DB, never from the token.
    """
    if creds is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=_INVALID)

    try:
        payload = decode_token(creds.credentials)
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=_INVALID)

    user = get_user(db, payload["sub"])
    if user is None or not user.active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=_INVALID)

    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    """Reject with neutral 404 unless the user has the 'admin' role."""
    if "admin" not in (user.roles or []):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return user

