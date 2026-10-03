"""Chunk schema: pydantic v2 model for Qdrant point payloads."""

import uuid
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, field_validator, model_validator

ROLES = {"admin", "hr", "finance", "intern"}

# Fixed namespace for deterministic point ids
QDRANT_ID_NAMESPACE = uuid.UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")


def point_id(chunk_id: str) -> str:
    """Deterministic UUID5 from chunk_id, as a string for Qdrant."""
    return str(uuid.uuid5(QDRANT_ID_NAMESPACE, chunk_id))


class Chunk(BaseModel):
    chunk_id: str  # "<doc_id>-p<page>-c<n>", page 1-based
    doc_id: str
    source_type: Literal["pdf", "image", "db_row"]
    source_name: str
    page: int | None = None
    bbox: list[float] | None = None
    row_id: str | None = None
    chunk_type: Literal["text", "table"] = "text"
    text: str
    allowed_roles: list[str] = []
    allowed_users: list[str] = []  # user UUIDs
    owner_id: str  # user UUID, required
    classification: int = 1
    is_public: bool = False
    deleted: bool = False
    created_at: str = ""

    @field_validator("classification")
    @classmethod
    def check_classification(cls, v: int) -> int:
        if v < 1 or v > 3:
            raise ValueError("classification must be 1, 2, or 3")
        return v

    @field_validator("allowed_roles", mode="before")
    @classmethod
    def check_roles(cls, v: list[str]) -> list[str]:
        for r in v:
            if r not in ROLES:
                raise ValueError(f"unknown role: {r!r} (valid: {sorted(ROLES)})")
        return v

    @field_validator("text")
    @classmethod
    def check_text_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("text must not be empty after stripping")
        return v

    @field_validator("owner_id")
    @classmethod
    def check_owner_id(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("owner_id is required")
        return v

    @model_validator(mode="after")
    def enforce_acl_defaults(self):
        # "admin" is always in allowed_roles
        if "admin" not in self.allowed_roles:
            self.allowed_roles = ["admin"] + list(self.allowed_roles)

        # A chunk with no roles (except admin), no users, and not public
        # → admin-only with owner added to allowed_users
        non_admin_roles = [r for r in self.allowed_roles if r != "admin"]
        if not non_admin_roles and not self.allowed_users and not self.is_public:
            if self.owner_id not in self.allowed_users:
                self.allowed_users = [self.owner_id]

        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()
        return self

    def to_payload(self) -> dict:
        """Convert to Qdrant point payload."""
        return self.model_dump()

    @classmethod
    def from_payload(cls, payload: dict) -> "Chunk":
        """Reconstruct a Chunk from a Qdrant point payload."""
        return cls(**payload)
