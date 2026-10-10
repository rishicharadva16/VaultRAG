from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import User
from app.db.session import get_db
from app.security.deps import get_current_user
from app.security.jwt import create_token
from app.security.passwords import (
    PasswordTooLong, PasswordTooShort,
    hash_password, validate_password, verify_password,
)
from app.security.users import get_user_by_email

router = APIRouter(prefix="/auth", tags=["auth"])

# Identical error message for wrong email and wrong password – prevents enumeration.
_LOGIN_FAIL = "Invalid email or password"


class LoginRequest(BaseModel):
    email: str
    password: str


class RegisterRequest(BaseModel):
    name: str
    email: str
    password: str
    # Roles and employee_id are intentionally absent / ignored – never accepted from self-register.


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class MeResponse(BaseModel):
    id: str
    name: str
    email: str
    roles: list[str]
    employee_id: str | None = None
    department: str | None = None
    external_id: str | None = None


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = get_user_by_email(db, body.email)
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=_LOGIN_FAIL)
    if not user.active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=_LOGIN_FAIL)
    return TokenResponse(access_token=create_token(user.id))


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    if not settings.ALLOW_SELF_REGISTER:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Registration is disabled")

    try:
        validate_password(body.password)
    except (PasswordTooShort, PasswordTooLong) as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))

    if get_user_by_email(db, body.email):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
    user = User(
        name=body.name,
        email=body.email,
        password_hash=hash_password(body.password),
        roles=[],           # Self-registered users get no roles
        employee_id=None,   # No employee_id
        department=None,
        external_id=None,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return TokenResponse(access_token=create_token(user.id))


class DemoUserOut(BaseModel):
    id: str
    name: str
    department: str | None = None
    is_admin: bool


@router.get("/demo-users", response_model=list[DemoUserOut])
def get_demo_users(db: Session = Depends(get_db)):
    """Returns only visible, active users for demo login chips (no emails or hashes)."""
    users = (
        db.query(User)
        .filter(User.active == True, User.shown_in_demo == True)
        .order_by(User.name)
        .all()
    )
    return [
        DemoUserOut(
            id=u.id,
            name=u.name,
            department=u.department,
            is_admin="admin" in (u.roles or []),
        )
        for u in users
    ]


@router.get("/me", response_model=MeResponse)
def me(user: User = Depends(get_current_user)):
    return MeResponse(
        id=user.id,
        name=user.name,
        email=user.email,
        roles=user.roles or [],
        employee_id=user.employee_id,
        department=user.department,
        external_id=user.external_id,
    )

