from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.audit.logger import write_audit
from app.db.models import User
from app.db.session import get_db
from app.security.deps import require_admin
from app.security.passwords import (
    PasswordTooLong, PasswordTooShort,
    hash_password, validate_password,
)
from app.security.users import get_user, get_user_by_email

router = APIRouter(prefix="/admin", tags=["admin"])


class CreateUserRequest(BaseModel):
    name: str
    email: str
    password: str
    roles: list[str] = []
    clearance: int = 1


class UpdateRolesRequest(BaseModel):
    roles: list[str]
    clearance: int


class UpdateActiveRequest(BaseModel):
    active: bool


class UserOut(BaseModel):
    id: str
    name: str
    email: str
    roles: list[str]
    clearance: int
    active: bool


@router.post("/users", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(
    body: CreateUserRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    if body.clearance < 1 or body.clearance > 3:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Clearance must be 1-3")

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
        roles=body.roles,
        clearance=body.clearance,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    write_audit(db, user_id=admin.id, event="admin.create_user",
                details={"target": user.id, "email": user.email, "roles": user.roles, "clearance": user.clearance})
    return _to_out(user)


@router.get("/users", response_model=list[UserOut])
def list_users(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    return [_to_out(u) for u in db.query(User).all()]


@router.put("/users/{user_id}/roles", response_model=UserOut)
def update_roles(
    user_id: str,
    body: UpdateRolesRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    if body.clearance < 1 or body.clearance > 3:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Clearance must be 1-3")

    user = get_user(db, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    old = {"roles": user.roles, "clearance": user.clearance}
    user.roles = body.roles
    user.clearance = body.clearance
    db.commit()
    db.refresh(user)

    write_audit(db, user_id=admin.id, event="admin.update_roles",
                details={"target": user_id, "old": old,
                         "new": {"roles": user.roles, "clearance": user.clearance}})
    return _to_out(user)


@router.put("/users/{user_id}/active", response_model=UserOut)
def update_active(
    user_id: str,
    body: UpdateActiveRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    user = get_user(db, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    old_active = user.active
    user.active = body.active
    db.commit()
    db.refresh(user)

    write_audit(db, user_id=admin.id, event="admin.update_active",
                details={"target": user_id, "old_active": old_active, "new_active": user.active})
    return _to_out(user)


def _to_out(user: User) -> UserOut:
    return UserOut(
        id=user.id, name=user.name, email=user.email,
        roles=user.roles or [], clearance=user.clearance, active=user.active,
    )
