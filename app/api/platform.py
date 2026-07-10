"""Platform endpoints — super_admin only. Onboard shops and shop-admins."""
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import require_role
from app.core.utils import slugify
from app.enums import Role
from app.models import Coupon, Customer, Profile, Shop
from app.schemas.auth import ProfileOut
from app.schemas.shop import ShopCreate, ShopOut, ShopUpdate
from app.schemas.user import StaffCreate
from app.services.provisioning import provision_user

router = APIRouter(prefix="/platform", tags=["platform"])

require_super = require_role(Role.SUPER_ADMIN)
DbSession = Annotated[Session, Depends(get_db)]


def _get_shop_or_404(db: Session, shop_id: uuid.UUID) -> Shop:
    shop = db.get(Shop, shop_id)
    if shop is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Shop not found")
    return shop


@router.post("/shops", response_model=ShopOut, status_code=201,
             dependencies=[Depends(require_super)])
def create_shop(payload: ShopCreate, db: DbSession) -> Shop:
    shop = Shop(
        name=payload.name,
        slug=slugify(payload.slug or payload.name),
        currency=payload.currency,
        timezone=payload.timezone,
        branding=payload.branding,
    )
    db.add(shop)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, f"Slug '{shop.slug}' already in use") from exc
    db.refresh(shop)
    return shop


@router.get("/shops", response_model=list[ShopOut], dependencies=[Depends(require_super)])
def list_shops(db: DbSession) -> list[Shop]:
    return list(db.scalars(select(Shop).order_by(Shop.created_at.desc())).all())


@router.get("/shops/{shop_id}", response_model=ShopOut, dependencies=[Depends(require_super)])
def get_shop(shop_id: uuid.UUID, db: DbSession) -> Shop:
    return _get_shop_or_404(db, shop_id)


@router.patch("/shops/{shop_id}", response_model=ShopOut, dependencies=[Depends(require_super)])
def update_shop(shop_id: uuid.UUID, payload: ShopUpdate, db: DbSession) -> Shop:
    shop = _get_shop_or_404(db, shop_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(shop, field, value)
    db.commit()
    db.refresh(shop)
    return shop


@router.delete("/shops/{shop_id}", status_code=204, dependencies=[Depends(require_super)])
def delete_shop(shop_id: uuid.UUID, db: DbSession) -> None:
    # DB-level ON DELETE CASCADE removes all tenant rows (incl. profiles). Note:
    # the corresponding Supabase Auth users are not deleted here.
    shop = _get_shop_or_404(db, shop_id)
    db.delete(shop)
    db.commit()


@router.post("/shops/{shop_id}/admins", response_model=ProfileOut, status_code=201,
             dependencies=[Depends(require_super)])
def create_shop_admin(shop_id: uuid.UUID, payload: StaffCreate, db: DbSession) -> Profile:
    _get_shop_or_404(db, shop_id)
    return provision_user(
        db,
        email=payload.email,
        password=payload.password,
        name=payload.name,
        role=Role.SHOP_ADMIN,
        shop_id=shop_id,
    )


@router.get("/shops/{shop_id}/users", response_model=list[ProfileOut],
            dependencies=[Depends(require_super)])
def list_shop_users(shop_id: uuid.UUID, db: DbSession) -> list[Profile]:
    _get_shop_or_404(db, shop_id)
    return list(db.scalars(select(Profile).where(Profile.shop_id == shop_id)).all())


@router.get("/stats", dependencies=[Depends(require_super)])
def platform_stats(db: DbSession) -> dict:
    return {
        "shops": db.scalar(select(func.count()).select_from(Shop)),
        "customers": db.scalar(select(func.count()).select_from(Customer)),
        "coupons": db.scalar(select(func.count()).select_from(Coupon)),
    }
