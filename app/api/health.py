"""Health and readiness endpoints."""
from fastapi import APIRouter
from sqlalchemy import text

from app.core.db import get_engine

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    """Liveness — the process is up. Does not touch the database."""
    return {"status": "ok"}


@router.get("/health/db")
def health_db() -> dict:
    """Readiness — can we reach the database?"""
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected"}
    except Exception as exc:  # noqa: BLE001 - report any connection failure
        return {"status": "error", "database": "unavailable", "detail": str(exc)}
