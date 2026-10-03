import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, Column, DateTime, Integer, String, Text,
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
    clearance = Column(Integer, nullable=False, default=1)
    active = Column(Boolean, nullable=False, default=True)


class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    ts = Column(DateTime(timezone=True), nullable=False,
                default=lambda: datetime.now(timezone.utc))
    user_id = Column(String, nullable=False)
    event = Column(String, nullable=False)
    details = Column(JSONB, nullable=True)
