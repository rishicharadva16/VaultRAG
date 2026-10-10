import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, Column, DateTime, Float, Integer, String, Text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    roles = Column(ARRAY(String), nullable=False, default=list)
    employee_id = Column(String, nullable=True)
    department = Column(String, nullable=True)
    external_id = Column(String, unique=True, nullable=True, index=True)
    active = Column(Boolean, nullable=False, default=True)
    shown_in_demo = Column(Boolean, nullable=False, default=False)


class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    ts = Column(DateTime(timezone=True), nullable=False,
                default=lambda: datetime.now(timezone.utc))
    created_at = Column(DateTime(timezone=True), nullable=True,
                        default=lambda: datetime.now(timezone.utc))
    user_id = Column(String, nullable=False)
    event = Column(String, nullable=True)
    event_type = Column(String, nullable=True)
    refused = Column(Boolean, nullable=True)
    reason_code = Column(String, nullable=True)
    latency_ms = Column(Float, nullable=True)
    chunk_count = Column(Integer, nullable=True)
    admin_access = Column(Boolean, nullable=True, default=False)
    question_hash = Column(String, nullable=True)
    question_length = Column(Integer, nullable=True)
    details = Column(JSONB, nullable=True)


class Document(Base):
    __tablename__ = "documents"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    source_id = Column(String, unique=True, nullable=False, index=True)
    filename = Column(String, nullable=False)
    kind = Column(String, nullable=False)  # pdf | image | csv | text
    size_bytes = Column(Integer, nullable=False)
    sha256 = Column(String, nullable=False, index=True)
    owner_id = Column(String, nullable=False, index=True)
    status = Column(String, nullable=False, default="queued")  # queued | processing | ready | failed
    reason_code = Column(String, nullable=True)
    chunk_count = Column(Integer, nullable=False, default=0)
    sensitive_columns = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False,
                         default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False,
                         default=lambda: datetime.now(timezone.utc),
                         onupdate=lambda: datetime.now(timezone.utc))
    deleted_at = Column(DateTime(timezone=True), nullable=True)


class DocumentShare(Base):
    __tablename__ = "document_shares"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id = Column(String, nullable=False, index=True)
    grantee_type = Column(String, nullable=False)  # user | role | department
    grantee_value = Column(String, nullable=False)  # user uuid, role name, or department name
    include_sensitive = Column(Boolean, nullable=False, default=False)
    granted_by = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False,
                         default=lambda: datetime.now(timezone.utc))

