"""Database engine and session management.

The engine is created lazily so the app can boot (e.g. serve ``/health``)
even when ``DATABASE_URL`` is not configured yet. Use the ``get_db``
dependency in route handlers to obtain a scoped SQLAlchemy session.
"""
from collections.abc import Generator

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def _normalize_url(url: str) -> str:
    """Ensure SQLAlchemy uses the psycopg (v3) driver for Postgres URLs.

    Supabase hands out ``postgresql://...`` which SQLAlchemy would route to
    psycopg2; we ship psycopg v3, so rewrite the scheme.
    """
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        if not settings.database_url:
            raise RuntimeError(
                "DATABASE_URL is not configured. Set it in backend/.env "
                "(see .env.example)."
            )
        _engine = create_engine(
            _normalize_url(settings.database_url),
            pool_pre_ping=True,
            future=True,
        )
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(
            bind=get_engine(), autoflush=False, autocommit=False, future=True
        )
    return _SessionLocal


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a database session."""
    db = get_session_factory()()
    try:
        yield db
    finally:
        db.close()
