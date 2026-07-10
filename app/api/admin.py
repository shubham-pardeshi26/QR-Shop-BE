"""Shop-admin endpoints — shop_admin only, scoped to the caller's own shop."""
import csv
import io
import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import require_role
from app.enums import CouponStatus, Role
from app.games.registry import GAME_CATALOG, get_game_type
from app.models import Coupon, Customer, Game, PlaySession, PrizeTier, Profile, Shop
from app.schemas.analytics import AnalyticsOut, DayStat, GameStat
from app.schemas.auth import ProfileOut
from app.schemas.game import (
    GameCatalogItem,
    GameCreate,
    GameOut,
    GameUpdate,
    PrizeTierCreate,
    PrizeTierOut,
    PrizeTierUpdate,
)
from app.schemas.shop import ShopOut, ShopUpdate
from app.schemas.user import StaffCreate, StaffUpdate
from app.services.provisioning import provision_user
from app.services.qr import customer_url, qr_svg

router = APIRouter(prefix="/admin", tags=["shop-admin"])

_require_shop_admin = require_role(Role.SHOP_ADMIN)
DbSession = Annotated[Session, Depends(get_db)]


def current_shop_admin(profile: Annotated[Profile, Depends(_require_shop_admin)]) -> Profile:
    if profile.shop_id is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Shop admin is not attached to a shop")
    return profile


ShopAdmin = Annotated[Profile, Depends(current_shop_admin)]


def _get_game(db: Session, shop_id: uuid.UUID, game_id: uuid.UUID) -> Game:
    game = db.scalar(select(Game).where(Game.id == game_id, Game.shop_id == shop_id))
    if game is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Game not found")
    return game


def _get_prize(db: Session, shop_id: uuid.UUID, prize_id: uuid.UUID) -> PrizeTier:
    prize = db.scalar(select(PrizeTier).where(PrizeTier.id == prize_id, PrizeTier.shop_id == shop_id))
    if prize is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Prize tier not found")
    return prize


# ---- Shop settings ---------------------------------------------------------
@router.get("/shop", response_model=ShopOut)
def get_my_shop(admin: ShopAdmin, db: DbSession) -> Shop:
    return db.get(Shop, admin.shop_id)


@router.patch("/shop", response_model=ShopOut)
def update_my_shop(payload: ShopUpdate, admin: ShopAdmin, db: DbSession) -> Shop:
    shop = db.get(Shop, admin.shop_id)
    data = payload.model_dump(exclude_unset=True)
    data.pop("status", None)  # a shop admin cannot change their own shop's status
    for field, value in data.items():
        setattr(shop, field, value)
    db.commit()
    db.refresh(shop)
    return shop


@router.get("/qr")
def get_qr(admin: ShopAdmin, db: DbSession) -> dict:
    shop = db.get(Shop, admin.shop_id)
    return {"url": customer_url(shop.slug), "svg": qr_svg(shop.slug)}


# ---- Games -----------------------------------------------------------------
@router.get("/game-catalog", response_model=list[GameCatalogItem])
def game_catalog(admin: ShopAdmin) -> list[GameCatalogItem]:
    return [
        GameCatalogItem(
            slug=g.slug,
            name=g.name,
            default_prize_strategy=g.default_prize_strategy,
            is_placeholder=g.is_placeholder,
            description=g.description,
        )
        for g in GAME_CATALOG.values()
    ]


@router.get("/games", response_model=list[GameOut])
def list_games(admin: ShopAdmin, db: DbSession) -> list[Game]:
    return list(
        db.scalars(
            select(Game).where(Game.shop_id == admin.shop_id).order_by(Game.sort_order)
        ).all()
    )


@router.post("/games", response_model=GameOut, status_code=201)
def create_game(payload: GameCreate, admin: ShopAdmin, db: DbSession) -> Game:
    game_type = get_game_type(payload.type_slug)
    if game_type is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Unknown game type '{payload.type_slug}'")
    game = Game(
        shop_id=admin.shop_id,
        type_slug=game_type.slug,
        name=payload.name or game_type.name,
        enabled=payload.enabled,
        sort_order=payload.sort_order,
        config=payload.config,
        prize_strategy=payload.prize_strategy or game_type.default_prize_strategy,
    )
    db.add(game)
    db.commit()
    db.refresh(game)
    return game


@router.patch("/games/{game_id}", response_model=GameOut)
def update_game(game_id: uuid.UUID, payload: GameUpdate, admin: ShopAdmin, db: DbSession) -> Game:
    game = _get_game(db, admin.shop_id, game_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(game, field, value)
    db.commit()
    db.refresh(game)
    return game


@router.delete("/games/{game_id}", status_code=204)
def delete_game(game_id: uuid.UUID, admin: ShopAdmin, db: DbSession) -> None:
    db.delete(_get_game(db, admin.shop_id, game_id))
    db.commit()


# ---- Prize tiers -----------------------------------------------------------
@router.get("/games/{game_id}/prizes", response_model=list[PrizeTierOut])
def list_prizes(game_id: uuid.UUID, admin: ShopAdmin, db: DbSession) -> list[PrizeTier]:
    _get_game(db, admin.shop_id, game_id)
    return list(db.scalars(select(PrizeTier).where(PrizeTier.game_id == game_id)).all())


@router.post("/games/{game_id}/prizes", response_model=PrizeTierOut, status_code=201)
def create_prize(game_id: uuid.UUID, payload: PrizeTierCreate, admin: ShopAdmin, db: DbSession) -> PrizeTier:
    _get_game(db, admin.shop_id, game_id)
    prize = PrizeTier(shop_id=admin.shop_id, game_id=game_id, **payload.model_dump())
    db.add(prize)
    db.commit()
    db.refresh(prize)
    return prize


@router.patch("/prizes/{prize_id}", response_model=PrizeTierOut)
def update_prize(prize_id: uuid.UUID, payload: PrizeTierUpdate, admin: ShopAdmin, db: DbSession) -> PrizeTier:
    prize = _get_prize(db, admin.shop_id, prize_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(prize, field, value)
    db.commit()
    db.refresh(prize)
    return prize


@router.delete("/prizes/{prize_id}", status_code=204)
def delete_prize(prize_id: uuid.UUID, admin: ShopAdmin, db: DbSession) -> None:
    db.delete(_get_prize(db, admin.shop_id, prize_id))
    db.commit()


# ---- Staff -----------------------------------------------------------------
@router.get("/staff", response_model=list[ProfileOut])
def list_staff(admin: ShopAdmin, db: DbSession) -> list[Profile]:
    return list(db.scalars(select(Profile).where(Profile.shop_id == admin.shop_id)).all())


@router.post("/staff", response_model=ProfileOut, status_code=201)
def create_staff(payload: StaffCreate, admin: ShopAdmin, db: DbSession) -> Profile:
    return provision_user(
        db,
        email=payload.email,
        password=payload.password,
        name=payload.name,
        role=Role.STAFF,
        shop_id=admin.shop_id,
    )


@router.patch("/staff/{user_id}", response_model=ProfileOut)
def update_staff(user_id: uuid.UUID, payload: StaffUpdate, admin: ShopAdmin, db: DbSession) -> Profile:
    profile = db.scalar(
        select(Profile).where(Profile.id == user_id, Profile.shop_id == admin.shop_id)
    )
    if profile is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Staff member not found")
    if profile.role != Role.STAFF:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Can only modify staff accounts")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(profile, field, value)
    db.commit()
    db.refresh(profile)
    return profile


# ---- Analytics & leads -----------------------------------------------------
@router.get("/analytics", response_model=AnalyticsOut)
def analytics(admin: ShopAdmin, db: DbSession) -> AnalyticsOut:
    shop_id = admin.shop_id

    def count(stmt) -> int:
        return db.scalar(stmt) or 0

    total_customers = count(select(func.count()).select_from(Customer).where(Customer.shop_id == shop_id))
    total_plays = count(select(func.count()).select_from(PlaySession).where(PlaySession.shop_id == shop_id))
    issued = count(select(func.count()).select_from(Coupon).where(Coupon.shop_id == shop_id))
    redeemed = count(
        select(func.count()).select_from(Coupon).where(
            Coupon.shop_id == shop_id, Coupon.status == CouponStatus.REDEEMED
        )
    )

    game_rows = db.execute(
        select(Game.id, Game.name, func.count(PlaySession.id))
        .join(PlaySession, PlaySession.game_id == Game.id)
        .where(Game.shop_id == shop_id)
        .group_by(Game.id, Game.name)
        .order_by(func.count(PlaySession.id).desc())
    ).all()
    plays_by_game = [GameStat(game=name, plays=n) for _id, name, n in game_rows]

    today = datetime.now(timezone.utc).date()
    days: list[DayStat] = []
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        start = datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
        end = start + timedelta(days=1)
        n = count(
            select(func.count()).select_from(Coupon).where(
                Coupon.shop_id == shop_id, Coupon.issued_at >= start, Coupon.issued_at < end
            )
        )
        days.append(DayStat(date=day.isoformat(), coupons=n))

    return AnalyticsOut(
        total_customers=total_customers,
        total_plays=total_plays,
        coupons_issued=issued,
        coupons_redeemed=redeemed,
        redemption_rate=round(redeemed / issued, 3) if issued else 0.0,
        plays_by_game=plays_by_game,
        coupons_last_7_days=days,
    )


@router.get("/leads.csv")
def export_leads(admin: ShopAdmin, db: DbSession) -> StreamingResponse:
    customers = db.scalars(
        select(Customer).where(Customer.shop_id == admin.shop_id).order_by(Customer.created_at.desc())
    ).all()

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["name", "phone", "first_seen_at", "last_seen_at"])
    for c in customers:
        writer.writerow([c.name, c.phone, c.first_seen_at.isoformat(), c.last_seen_at.isoformat()])
    buffer.seek(0)

    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=leads.csv"},
    )
