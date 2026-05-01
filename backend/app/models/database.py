"""
SQLAlchemy Database Models + Engine Setup
==========================================
Defines the ORM models for sessions, messages, and scorecards.
Uses async SQLAlchemy ORM for non-blocking DB access within FastAPI.
Local development and production are intended to run on PostgreSQL/Supabase via DATABASE_URL.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import AsyncIterator

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    inspect,
    String,
    Text,
    text,
)
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, relationship
from sqlalchemy.pool import NullPool

from app.config import get_settings


def utc_now() -> datetime:
    """Return a UTC timestamp compatible with existing timestamp columns."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ── Base ──────────────────────────────────────────────────────────
class Base(DeclarativeBase):
    """Declarative base for all ORM models."""
    pass


# ── Models ────────────────────────────────────────────────────────

class SessionModel(Base):
    """An interview session."""

    __tablename__ = "sessions"

    id = Column(String, primary_key=True, default=lambda: uuid.uuid4().hex)
    job_role = Column(String, nullable=False)
    job_description = Column(Text, nullable=False)
    resume_text = Column(Text, default="")
    resume_highlights = Column(JSON, default=dict)
    resume_context = Column(JSON, default=dict)
    voice_mode = Column(Boolean, default=False)
    difficulty = Column(String, default="medium")  # easy | medium | hard
    max_turns = Column(Integer, default=9)
    turn_count = Column(Integer, default=0)
    private_scores = Column(JSON, default=list)
    status = Column(String, default="active")  # active | synthesizing | completed
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(
        DateTime,
        default=utc_now,
        onupdate=utc_now,
    )

    # Relationships
    messages = relationship("MessageModel", back_populates="session", cascade="all, delete-orphan")
    scorecard = relationship("ScorecardModel", back_populates="session", uselist=False, cascade="all, delete-orphan")


class MessageModel(Base):
    """A single message in the interview transcript."""

    __tablename__ = "messages"

    id = Column(String, primary_key=True, default=lambda: uuid.uuid4().hex)
    session_id = Column(String, ForeignKey("sessions.id"), nullable=False)
    role = Column(String, nullable=False)  # "user" | "agent"
    agent_name = Column(String, nullable=True)  # "hr" | "technical" | "behavioral" | null for user
    content = Column(Text, nullable=False)
    audio_url = Column(String, nullable=True)  # future: S3/R2 URL
    timestamp = Column(DateTime, default=utc_now)

    # Relationships
    session = relationship("SessionModel", back_populates="messages")


class ScorecardModel(Base):
    """Final scorecard produced by the Synthesizer agent."""

    __tablename__ = "scorecards"

    id = Column(String, primary_key=True, default=lambda: uuid.uuid4().hex)
    session_id = Column(String, ForeignKey("sessions.id"), nullable=False, unique=True)
    scores_json = Column(JSON, nullable=False)  # Full scorecard JSON
    resume_accuracy = Column(JSON, nullable=True)  # {verified, unverified, inflated}
    final_score = Column(Integer, nullable=True)
    hire_recommendation = Column(String, nullable=True)
    created_at = Column(DateTime, default=utc_now)

    # Relationships
    session = relationship("SessionModel", back_populates="scorecard")


# ── Engine + Session Factory ──────────────────────────────────────

_settings = get_settings()


def normalize_database_url(database_url: str) -> str:
    """Return an async SQLAlchemy URL for supported database backends."""
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    url = make_url(database_url)
    if url.drivername == "postgresql+asyncpg":
        remove_query_keys = []
        query_updates = {}
        if "pgbouncer" in url.query:
            remove_query_keys.append("pgbouncer")
            query_updates["prepared_statement_cache_size"] = "0"
        if "sslmode" in url.query:
            remove_query_keys.append("sslmode")
        if remove_query_keys:
            url = url.difference_update_query(remove_query_keys)
        if query_updates:
            url = url.update_query_dict(query_updates)
    return url.render_as_string(hide_password=False)


def _is_sqlite_url(database_url: str) -> bool:
    return make_url(database_url).get_backend_name() == "sqlite"


def _create_engine(database_url: str):
    uses_supabase_pooler = "pgbouncer=true" in database_url or "pooler.supabase.com" in database_url
    uses_ssl = "sslmode=require" in database_url
    database_url = normalize_database_url(database_url)
    is_sqlite = _is_sqlite_url(database_url)
    connect_args = {"check_same_thread": False} if is_sqlite else {}
    if uses_supabase_pooler:
        connect_args["statement_cache_size"] = 0
    if uses_ssl:
        connect_args["ssl"] = "require"

    engine_kwargs = {
        "echo": False,
        "pool_pre_ping": not is_sqlite,
        "connect_args": connect_args,
    }
    if uses_supabase_pooler:
        engine_kwargs["poolclass"] = NullPool

    return create_async_engine(database_url, **engine_kwargs)


engine = _create_engine(_settings.DATABASE_URL)
async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


def configure_database(database_url: str) -> None:
    """Reconfigure the global engine/session factory, primarily for tests."""
    global engine, async_session_factory
    engine = _create_engine(database_url)
    async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def _ensure_session_columns() -> None:
    """Apply lightweight additive migrations for existing demo environments."""
    async with engine.begin() as conn:
        column_names = await conn.run_sync(
            lambda sync_conn: {column["name"] for column in inspect(sync_conn).get_columns("sessions")}
        )

        if "resume_context" not in column_names:
            await conn.execute(text("ALTER TABLE sessions ADD COLUMN resume_context JSON"))

        if "private_scores" not in column_names:
            await conn.execute(text("ALTER TABLE sessions ADD COLUMN private_scores JSON"))


async def init_db() -> None:
    """Create all tables if they don't exist."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await _ensure_session_columns()


async def get_db() -> AsyncIterator[AsyncSession]:
    """Dependency for FastAPI route injection."""
    async with async_session_factory() as session:
        try:
            yield session
        finally:
            await session.close()
