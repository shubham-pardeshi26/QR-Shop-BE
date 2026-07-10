"""SQLAlchemy declarative base + shared column helpers."""
from datetime import datetime, timezone
from enum import Enum as PyEnum

from sqlalchemy import DateTime, Enum as SAEnum, JSON, TypeDecorator, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all ORM models."""


class TZDateTime(TypeDecorator):
    """A timezone-aware DateTime that always returns UTC-aware values.

    Postgres ``timestamptz`` already returns aware datetimes; SQLite (used in
    tests) drops tzinfo. Normalizing on both bind and result keeps comparisons
    like ``coupon.expires_at < datetime.now(timezone.utc)`` safe everywhere.
    """

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect) -> datetime | None:
        if value is not None and value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value

    def process_result_value(self, value: datetime | None, dialect) -> datetime | None:
        if value is not None and value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value


class TimestampMixin:
    """Adds created_at / updated_at columns (DB-managed)."""

    created_at: Mapped[datetime] = mapped_column(
        TZDateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        TZDateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )


# JSON column that upgrades to JSONB on Postgres, plain JSON elsewhere.
JSONType = JSON().with_variant(JSONB, "postgresql")


def make_enum(py_enum: type[PyEnum], name: str) -> SAEnum:
    """A portable VARCHAR-backed enum that stores the enum *values*.

    ``native_enum=False`` avoids Postgres CREATE TYPE (painful to migrate);
    ``values_callable`` ensures we persist ``"super_admin"`` rather than the
    member name ``"SUPER_ADMIN"``.
    """
    return SAEnum(
        py_enum,
        name=name,
        native_enum=False,
        values_callable=lambda enum_cls: [member.value for member in enum_cls],
    )
