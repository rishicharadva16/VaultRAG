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
from app.security.roles import ROLES
from app.security.users import get_user, get_user_by_email

router = APIRouter(prefix="/admin", tags=["admin"])


class CreateUserRequest(BaseModel):
    name: str
    email: str
    password: str
    roles: list[str] = []
    employee_id: str | None = None
    department: str | None = None
    external_id: str | None = None


class UpdateRolesRequest(BaseModel):
    roles: list[str]


class UpdateActiveRequest(BaseModel):
    active: bool


class UserOut(BaseModel):
    id: str
    name: str
    email: str
    roles: list[str]
    employee_id: str | None = None
    department: str | None = None
    external_id: str | None = None
    active: bool


def _validate_roles(roles: list[str]) -> None:
    for r in roles:
        if r not in ROLES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid role: {r!r}. Allowed roles: {sorted(ROLES)}",
            )


@router.post("/users", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(
    body: CreateUserRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    _validate_roles(body.roles)

    try:
        validate_password(body.password)
    except (PasswordTooShort, PasswordTooLong) as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))

    if get_user_by_email(db, body.email):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    if body.external_id:
        existing_ext = db.query(User).filter(User.external_id == body.external_id).first()
        if existing_ext:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="external_id already in use")

    user = User(
        name=body.name,
        email=body.email,
        password_hash=hash_password(body.password),
        roles=body.roles,
        employee_id=body.employee_id,
        department=body.department,
        external_id=body.external_id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    write_audit(
        db,
        user_id=admin.id,
        event="admin.create_user",
        details={
            "target": user.id,
            "email": user.email,
            "roles": user.roles,
            "employee_id": user.employee_id,
            "external_id": user.external_id,
        },
    )
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
    _validate_roles(body.roles)

    user = get_user(db, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    old = {"roles": user.roles}
    user.roles = body.roles
    db.commit()
    db.refresh(user)

    write_audit(
        db,
        user_id=admin.id,
        event="admin.update_roles",
        details={"target": user_id, "old": old, "new": {"roles": user.roles}},
    )
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

    write_audit(
        db,
        user_id=admin.id,
        event="admin.update_active",
        details={"target": user_id, "old_active": old_active, "new_active": user.active},
    )
    return _to_out(user)


def _to_out(user: User) -> UserOut:
    return UserOut(
        id=user.id,
        name=user.name,
        email=user.email,
        roles=user.roles or [],
        employee_id=user.employee_id,
        department=user.department,
        external_id=user.external_id,
        active=user.active,
    )
