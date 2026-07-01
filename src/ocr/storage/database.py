"""
Async SQLAlchemy engine and session factory.

The connection string is read from settings.postgres_connection_string.
The engine is created lazily on first access and cached for the process lifetime.
"""

from typing import AsyncGenerator, Optional

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from src.config.settings import settings
from cams_otel_lib import Logger as logger

# ── ORM base ─────────────────────────────────────────────────────────────────

class Base(DeclarativeBase):
    pass


# ── Engine / session factory (lazy, process-level singletons) ────────────────

_engine: Optional[AsyncEngine] = None
_session_factory: Optional[async_sessionmaker[AsyncSession]] = None


def _get_connection_string() -> str:
    conn = settings.postgres_connection_string
    if not conn:
        raise RuntimeError(
            "postgres_connection_string is not configured. "
            "Set POSTGRES_CONNECTION_STRING in the environment."
        )
    # SQLAlchemy async requires postgresql+psycopg:// (psycopg v3)
    if conn.startswith("postgresql://"):
        conn = conn.replace("postgresql://", "postgresql+psycopg://", 1)
    elif conn.startswith("postgres://"):
        conn = conn.replace("postgres://", "postgresql+psycopg://", 1)
    return conn


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        conn_str = _get_connection_string()
        _engine = create_async_engine(
            conn_str,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,
            echo=False,
        )
        logger.info("Async SQLAlchemy engine created")
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=get_engine(),
            expire_on_commit=False,
            class_=AsyncSession,
        )
    return _session_factory


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency / context manager that yields an AsyncSession."""
    factory = get_session_factory()
    async with factory() as session:
        yield session


async def create_tables() -> None:
    """Create all registered tables. Called once at startup."""
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("OCR database tables created / verified")
