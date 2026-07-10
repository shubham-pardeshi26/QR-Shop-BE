"""Public customer-facing endpoints: register, list games, play, coupons.

Registration is frictionless (name + phone). It returns an httpOnly session
cookie that authorizes the play/coupon endpoints (no password).
"""
import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_db
from app.core.deps import CurrentCustomer
from app.core.rate_limit import limiter
from app.core.security import create_customer_token
from app.enums import PlaySessionStatus, ShopStatus
from app.games.resolvers import resolve_prize
from app.models import Coupon, Customer, Game, PlaySession, PrizeTier, Shop
from app.schemas.public import (
    CompleteIn,
    CouponPublic,
    GamePublic,
    PlayResultOut,
    RegisterIn,
    SegmentOut,
    ShopPublic,
    ShopWithGames,
    StartOut,
)
from app.services.coupon import issue_coupon, recent_coupon_count

router = APIRouter(prefix="/public", tags=["public"])

DbSession = Annotated[Session, Depends(get_db)]


def _active_shop(db: Session, slug: str) -> Shop:
    shop = db.scalar(select(Shop).where(Shop.slug == slug, Shop.status == ShopStatus.ACTIVE))
    if shop is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Shop not found")
    return shop


def _enabled_games(db: Session, shop_id: uuid.UUID) -> list[Game]:
    return list(
        db.scalars(
            select(Game).where(Game.shop_id == shop_id, Game.enabled.is_(True)).order_by(Game.sort_order)
        ).all()
    )


def _shop_with_games(db: Session, shop: Shop) -> ShopWithGames:
    return ShopWithGames(
        shop=ShopPublic.model_validate(shop),
        games=[GamePublic.model_validate(g) for g in _enabled_games(db, shop.id)],
    )


@router.get("/s/{slug}", response_model=ShopWithGames)
def get_shop(slug: str, db: DbSession) -> ShopWithGames:
    return _shop_with_games(db, _active_shop(db, slug))


@router.post("/s/{slug}/register", response_model=ShopWithGames)
@limiter.limit("30/minute")
def register(
    slug: str, payload: RegisterIn, request: Request, response: Response, db: DbSession
) -> ShopWithGames:
    shop = _active_shop(db, slug)
    customer = db.scalar(
        select(Customer).where(Customer.shop_id == shop.id, Customer.phone == payload.phone)
    )
    if customer is None:
        customer = Customer(shop_id=shop.id, name=payload.name, phone=payload.phone)
        db.add(customer)
    else:
        customer.name = payload.name
        customer.last_seen_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(customer)

    token = create_customer_token(str(customer.id), str(shop.id))
    response.set_cookie(
        key="qg_session",
        value=token,
        httponly=True,
        samesite="lax",  # same-origin in dev via the Vite proxy; use "none"+secure if cross-site
        secure=settings.is_production,
        max_age=settings.customer_session_ttl_minutes * 60,
        path="/",
    )
    return _shop_with_games(db, shop)


@router.get("/play/games", response_model=list[GamePublic])
def my_games(customer: CurrentCustomer, db: DbSession) -> list[Game]:
    return _enabled_games(db, customer.shop_id)


@router.post("/play/games/{game_id}/start", response_model=StartOut)
@limiter.limit("60/minute")
def start_play(
    game_id: uuid.UUID, request: Request, customer: CurrentCustomer, db: DbSession
) -> StartOut:
    game = db.scalar(
        select(Game).where(
            Game.id == game_id, Game.shop_id == customer.shop_id, Game.enabled.is_(True)
        )
    )
    if game is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Game not found")

    shop = db.get(Shop, customer.shop_id)
    if recent_coupon_count(db, customer, shop.coupon_window_hours) >= shop.max_coupons_per_phone:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "You've reached the reward limit — please come back later.",
        )

    session = PlaySession(
        shop_id=customer.shop_id,
        customer_id=customer.id,
        game_id=game.id,
        status=PlaySessionStatus.STARTED,
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    tiers = db.scalars(
        select(PrizeTier).where(PrizeTier.game_id == game.id, PrizeTier.active.is_(True))
    ).all()
    return StartOut(
        session_id=session.id,
        game=GamePublic.model_validate(game),
        segments=[SegmentOut(label=t.label) for t in tiers],
    )


@router.post("/play/sessions/{session_id}/complete", response_model=PlayResultOut)
def complete_play(
    session_id: uuid.UUID, payload: CompleteIn, customer: CurrentCustomer, db: DbSession
) -> PlayResultOut:
    # Lock the customer row so this phone's completions serialize — makes the
    # per-phone cap race-safe (no double-issue from concurrent completions).
    db.scalar(select(Customer).where(Customer.id == customer.id).with_for_update())

    # Lock the session row too, so the "already completed" guard is authoritative
    # under a concurrent double-complete of the same session.
    session = db.scalar(
        select(PlaySession)
        .where(PlaySession.id == session_id, PlaySession.customer_id == customer.id)
        .with_for_update()
    )
    if session is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Play session not found")
    if session.status != PlaySessionStatus.STARTED:
        raise HTTPException(status.HTTP_409_CONFLICT, "This game was already completed")

    shop = db.get(Shop, customer.shop_id)
    session.status = PlaySessionStatus.COMPLETED
    session.completed_at = datetime.now(timezone.utc)
    session.score = payload.score

    if recent_coupon_count(db, customer, shop.coupon_window_hours) >= shop.max_coupons_per_phone:
        db.commit()
        return PlayResultOut(coupon=None, prize_label=None, message="Reward limit reached.")

    game = db.get(Game, session.game_id)
    tier = resolve_prize(db, game, payload.score)
    if tier is None:
        db.commit()
        return PlayResultOut(
            coupon=None, prize_label=None, message="No prize this time — thanks for playing!"
        )

    # Lock the chosen tier and re-check stock, so stock_limit can't be exceeded
    # by concurrent winners drawing the same tier.
    locked_tier = db.scalar(select(PrizeTier).where(PrizeTier.id == tier.id).with_for_update())
    if locked_tier is None or not locked_tier.active or (
        locked_tier.stock_limit is not None and locked_tier.issued_count >= locked_tier.stock_limit
    ):
        db.commit()
        return PlayResultOut(
            coupon=None, prize_label=None, message="No prize this time — thanks for playing!"
        )

    coupon = issue_coupon(db, shop=shop, customer=customer, session=session, tier=locked_tier)
    session.prize_tier_id = locked_tier.id
    db.commit()
    db.refresh(coupon)
    return PlayResultOut(coupon=CouponPublic.model_validate(coupon), prize_label=locked_tier.label)


@router.get("/play/coupons/mine", response_model=list[CouponPublic])
def my_coupons(customer: CurrentCustomer, db: DbSession) -> list[Coupon]:
    return list(
        db.scalars(
            select(Coupon).where(Coupon.customer_id == customer.id).order_by(Coupon.issued_at.desc())
        ).all()
    )
