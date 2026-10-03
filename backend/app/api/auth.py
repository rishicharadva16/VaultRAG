from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

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
    # Roles and clearance are intentionally absent – never accepted from the client.


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class MeResponse(BaseModel):
    id: str
    name: str
    email: str
    roles: list[str]
    clearance: int


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
        roles=[],       # Self-registered users get no roles
        clearance=1,    # and lowest clearance
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return TokenResponse(access_token=create_token(user.id))


@router.get("/me", response_model=MeResponse)
def me(user: User = Depends(get_current_user)):
    return MeResponse(
        id=user.id, name=user.name, email=user.email,
        roles=user.roles or [], clearance=user.clearance,
    )
