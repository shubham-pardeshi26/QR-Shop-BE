"""All ORM models in one module.

Kept in a single file so relationship string references resolve cleanly via
the shared declarative registry without cross-module import cycles.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.enums import (
    CouponStatus,
    DiscountType,
    PlaySessionStatus,
    PrizeStrategy,
    Role,
    ShopStatus,
    UserStatus,
)
from app.models.base import Base, JSONType, TZDateTime, TimestampMixin, make_enum


class Shop(Base, TimestampMixin):
    """A tenant. Every tenant-scoped row carries this shop's id."""

    __tablename__ = "shops"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    branding: Mapped[dict] = mapped_column(JSONType, nullable=False, default=dict)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="UTC")
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="INR")
    status: Mapped[ShopStatus] = mapped_column(
        make_enum(ShopStatus, "shop_status"), nullable=False, default=ShopStatus.ACTIVE
    )
    # Per-shop anti-abuse configuration
    max_coupons_per_phone: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    coupon_window_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=24)
    coupon_valid_days: Mapped[int] = mapped_column(Integer, nullable=False, default=7)

    games: Mapped[list[Game]] = relationship(
        back_populates="shop", cascade="all, delete-orphan"
    )
    customers: Mapped[list[Customer]] = relationship(
        back_populates="shop", cascade="all, delete-orphan"
    )


class Profile(Base, TimestampMixin):
    """App-side identity, 1:1 with a Supabase Auth user (same id).

    Email/password/JWT live in Supabase ``auth``; role + tenancy live here.
    ``shop_id`` is NULL for super_admins.
    """

    __tablename__ = "profiles"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)  # == auth.users.id
    role: Mapped[Role] = mapped_column(make_enum(Role, "user_role"), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    shop_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("shops.id", ondelete="CASCADE"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[UserStatus] = mapped_column(
        make_enum(UserStatus, "user_status"), nullable=False, default=UserStatus.ACTIVE
    )

    shop: Mapped[Shop | None] = relationship()


class Customer(Base, TimestampMixin):
    """A frictionless lead: name + phone, unique per shop."""

    __tablename__ = "customers"
    __table_args__ = (UniqueConstraint("shop_id", "phone", name="uq_customer_shop_phone"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    shop_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("shops.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    phone: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    first_seen_at: Mapped[datetime] = mapped_column(
        TZDateTime, server_default=func.now(), nullable=False
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        TZDateTime, server_default=func.now(), nullable=False
    )

    shop: Mapped[Shop] = relationship(back_populates="customers")
    coupons: Mapped[list[Coupon]] = relationship(
        back_populates="customer", cascade="all, delete-orphan"
    )


class Game(Base, TimestampMixin):
    """A per-shop instance of a game type (see games.registry.GAME_CATALOG)."""

    __tablename__ = "games"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    shop_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("shops.id", ondelete="CASCADE"), nullable=False, index=True
    )
    type_slug: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    config: Mapped[dict] = mapped_column(JSONType, nullable=False, default=dict)
    prize_strategy: Mapped[PrizeStrategy] = mapped_column(
        make_enum(PrizeStrategy, "prize_strategy"), nullable=False
    )

    shop: Mapped[Shop] = relationship(back_populates="games")
    prize_tiers: Mapped[list[PrizeTier]] = relationship(
        back_populates="game", cascade="all, delete-orphan"
    )


class PrizeTier(Base, TimestampMixin):
    """A reward the admin configures. ``weight`` drives RANDOM games;
    ``[min_score, max_score]`` drives SKILL games."""

    __tablename__ = "prize_tiers"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    shop_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("shops.id", ondelete="CASCADE"), nullable=False, index=True
    )
    game_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("games.id", ondelete="CASCADE"), nullable=True, index=True
    )
    label: Mapped[str] = mapped_column(String(120), nullable=False)
    discount_type: Mapped[DiscountType] = mapped_column(
        make_enum(DiscountType, "discount_type"), nullable=False
    )
    value: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    weight: Mapped[int] = mapped_column(Integer, nullable=False, default=0)   # RANDOM
    min_score: Mapped[int | None] = mapped_column(Integer, nullable=True)      # SKILL
    max_score: Mapped[int | None] = mapped_column(Integer, nullable=True)      # SKILL
    stock_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    issued_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    shop: Mapped[Shop] = relationship()
    game: Mapped[Game | None] = relationship(back_populates="prize_tiers")


class PlaySession(Base, TimestampMixin):
    """One attempt at a game by a customer."""

    __tablename__ = "play_sessions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    shop_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("shops.id", ondelete="CASCADE"), nullable=False, index=True
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    game_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("games.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[PlaySessionStatus] = mapped_column(
        make_enum(PlaySessionStatus, "play_status"),
        nullable=False,
        default=PlaySessionStatus.STARTED,
    )
    score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    result_payload: Mapped[dict] = mapped_column(JSONType, nullable=False, default=dict)
    prize_tier_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("prize_tiers.id", ondelete="SET NULL"), nullable=True
    )
    started_at: Mapped[datetime] = mapped_column(
        TZDateTime, server_default=func.now(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(TZDateTime, nullable=True)

    prize_tier: Mapped[PrizeTier | None] = relationship()
    # One-to-one: the coupon (if any) minted from this session.
    coupon: Mapped[Coupon | None] = relationship(back_populates="play_session", uselist=False)


class Coupon(Base, TimestampMixin):
    """A single-use, expiring discount code redeemed at the counter."""

    __tablename__ = "coupons"
    __table_args__ = (UniqueConstraint("shop_id", "code", name="uq_coupon_shop_code"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    shop_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("shops.id", ondelete="CASCADE"), nullable=False, index=True
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    play_session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("play_sessions.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    prize_tier_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("prize_tiers.id", ondelete="SET NULL"), nullable=True
    )
    code: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    discount_type: Mapped[DiscountType] = mapped_column(
        make_enum(DiscountType, "discount_type"), nullable=False
    )
    value: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    status: Mapped[CouponStatus] = mapped_column(
        make_enum(CouponStatus, "coupon_status"), nullable=False, default=CouponStatus.ISSUED
    )
    issued_at: Mapped[datetime] = mapped_column(
        TZDateTime, server_default=func.now(), nullable=False
    )
    expires_at: Mapped[datetime | None] = mapped_column(TZDateTime, nullable=True)
    redeemed_at: Mapped[datetime | None] = mapped_column(TZDateTime, nullable=True)
    redeemed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True
    )

    customer: Mapped[Customer] = relationship(back_populates="coupons")
    play_session: Mapped[PlaySession] = relationship(back_populates="coupon")
    prize_tier: Mapped[PrizeTier | None] = relationship()
    redeemed_by: Mapped[Profile | None] = relationship()


class AnalyticsEvent(Base):
    """Lightweight event stream for dashboards (scans/plays/wins/redemptions)."""

    __tablename__ = "analytics_events"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    shop_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("shops.id", ondelete="CASCADE"), nullable=False, index=True
    )
    type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    payload: Mapped[dict] = mapped_column(JSONType, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        TZDateTime, server_default=func.now(), nullable=False
    )
