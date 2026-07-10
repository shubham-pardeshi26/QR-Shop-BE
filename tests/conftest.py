"""Shared pytest fixtures.

Tests run against an in-memory SQLite DB (shared across sessions via StaticPool),
so no Supabase/Postgres is required. Auth is exercised by overriding the
``get_current_profile`` dependency; the customer flow uses the real cookie path.
"""
import os

# Must be set before app.core.config is imported.
os.environ.setdefault("CUSTOMER_JWT_SECRET", "test-customer-secret")
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("DATABASE_URL", "sqlite://")

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core import deps
from app.core.db import get_db
from app.core.rate_limit import limiter
from app.enums import DiscountType, PlaySessionStatus, PrizeStrategy, Role, UserStatus
from app.main import app
from app.models import Base, Customer, Game, PlaySession, PrizeTier, Profile, Shop

# Rate limiting would make repeated calls flaky; disable it for tests.
limiter.enabled = False


@pytest.fixture
def engine():
    eng = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(eng)
    try:
        yield eng
    finally:
        Base.metadata.drop_all(eng)
        eng.dispose()


@pytest.fixture
def SessionLocal(engine):
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


@pytest.fixture
def db(SessionLocal):
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(SessionLocal):
    def override_get_db():
        session = SessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


# ---- Auth override ---------------------------------------------------------
@pytest.fixture
def as_profile():
    """Override the authenticated profile for protected endpoints."""
    def _set(profile: Profile) -> None:
        app.dependency_overrides[deps.get_current_profile] = lambda: profile
    return _set


# ---- Seeding factories -----------------------------------------------------
@pytest.fixture
def make_shop(db):
    def _make(slug="shop-a", name="Shop A", **kwargs):
        shop = Shop(name=name, slug=slug, **kwargs)
        db.add(shop)
        db.commit()
        db.refresh(shop)
        return shop
    return _make


@pytest.fixture
def make_user(db):
    def _make(role: Role, shop_id=None, name="User", email=None):
        profile = Profile(
            id=uuid.uuid4(),
            role=role,
            shop_id=shop_id,
            name=name,
            email=email or f"{uuid.uuid4().hex[:8]}@example.test",
            status=UserStatus.ACTIVE,
        )
        db.add(profile)
        db.commit()
        db.refresh(profile)
        return profile
    return _make


@pytest.fixture
def make_game(db):
    def _make(shop, slug="spin_wheel", strategy=PrizeStrategy.RANDOM, enabled=True, name="Spin"):
        game = Game(
            shop_id=shop.id, type_slug=slug, name=name, enabled=enabled, prize_strategy=strategy
        )
        db.add(game)
        db.commit()
        db.refresh(game)
        return game
    return _make


@pytest.fixture
def make_tier(db):
    def _make(
        shop,
        game,
        label="10% off",
        value=10,
        weight=1,
        discount_type=DiscountType.PERCENT,
        min_score=None,
        max_score=None,
        stock_limit=None,
        active=True,
    ):
        tier = PrizeTier(
            shop_id=shop.id,
            game_id=game.id,
            label=label,
            value=value,
            weight=weight,
            discount_type=discount_type,
            min_score=min_score,
            max_score=max_score,
            stock_limit=stock_limit,
            active=active,
        )
        db.add(tier)
        db.commit()
        db.refresh(tier)
        return tier
    return _make


@pytest.fixture
def make_customer(db):
    def _make(shop, name="Cust", phone="+15550000001"):
        customer = Customer(shop_id=shop.id, name=name, phone=phone)
        db.add(customer)
        db.commit()
        db.refresh(customer)
        return customer
    return _make


@pytest.fixture
def make_session(db):
    def _make(shop, customer, game):
        session = PlaySession(
            shop_id=shop.id,
            customer_id=customer.id,
            game_id=game.id,
            status=PlaySessionStatus.STARTED,
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        return session
    return _make
