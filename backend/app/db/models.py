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
