"""Chunk schema: pydantic v2 model for Qdrant point payloads with permission tokens."""

import uuid
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, field_validator, model_validator

from app.security.principals import doc_tokens, finalize_acl_tokens
from app.security.roles import ROLES

# Fixed namespace for deterministic point ids
QDRANT_ID_NAMESPACE = uuid.UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")


def point_id(chunk_id: str) -> str:
    """Deterministic UUID5 from chunk_id, as a string for Qdrant."""
    return str(uuid.uuid5(QDRANT_ID_NAMESPACE, chunk_id))


class Chunk(BaseModel):
    chunk_id: str  # "<doc_id>-p<page>-c<n>", page 1-based
    doc_id: str
    source_doc: str
    source_id: str
    source_type: Literal["pdf", "md", "html", "image", "db_row", "csv", "text"]
    source_name: str
    corpus: Literal["main", "poison_test"] = "main"
    page: int | None = None
    bbox: list[float] | None = None
    table: str | None = None
    row_pk: str | None = None
    file: str | None = None
    row_id: str | None = None
    kind: str | None = None
    ocr_confidence: float | None = None
    boxes: list[dict] | None = None
    image_width: int | None = None
    image_height: int | None = None
    file_ref: str | None = None
    chunk_type: Literal["text", "table"] = "text"
    text: str
    allowed_roles: list[str] = []
    allowed_employees: list[str] = []
    allowed_departments: list[str] = []
    acl_tokens: list[str] = []
    classification_label: str = "internal"
    owner_id: str = "u_admin"
    deleted: bool = False
    flagged: bool = False
    is_sensitive: bool = False
    created_at: str = ""

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

    @field_validator("page")
    @classmethod
    def check_page(cls, v: int | None) -> int | None:
        if v is not None and v < 1:
            raise ValueError("page must be >= 1")
        return v

    @model_validator(mode="after")
    def validate_and_compute_tokens(self):
        if not self.acl_tokens:
            computed = doc_tokens({
                "allowed_roles": self.allowed_roles,
                "allowed_employees": self.allowed_employees,
                "allowed_departments": self.allowed_departments,
            })
            if not computed:
                raise ValueError("acl_tokens cannot be empty (fail-closed access control)")
            self.acl_tokens = finalize_acl_tokens(computed)
        else:
            self.acl_tokens = finalize_acl_tokens(self.acl_tokens)

        if not self.acl_tokens:
            raise ValueError("acl_tokens cannot be empty (fail-closed access control)")

        if self.source_type == "pdf" and self.page is not None and self.page < 1:
            raise ValueError("PDF page must be >= 1")

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
