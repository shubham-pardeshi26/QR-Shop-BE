"""Staff (counter) endpoints — validate & redeem coupons, live activity.

Accessible to staff and shop_admin, scoped to their own shop.
"""
import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import require_role
from app.enums import CouponStatus, Role
from app.models import Coupon, PlaySession, Profile
from app.schemas.staff import ActivityOut, StaffCouponOut, ValidateIn

router = APIRouter(prefix="/staff", tags=["staff"])

DbSession = Annotated[Session, Depends(get_db)]
_require_counter = require_role(Role.STAFF, Role.SHOP_ADMIN)


def current_counter(profile: Annotated[Profile, Depends(_require_counter)]) -> Profile:
    if profile.shop_id is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not attached to a shop")
    return profile


Counter = Annotated[Profile, Depends(current_counter)]


def _validity(coupon: Coupon, now: datetime) -> tuple[bool, str | None]:
    if coupon.status == CouponStatus.REDEEMED:
        return False, "Already redeemed"
    if coupon.status == CouponStatus.EXPIRED:
        return False, "Expired"
    if coupon.expires_at is not None and coupon.expires_at < now:
        return False, "Expired"
    if coupon.status != CouponStatus.ISSUED:
        return False, "Not redeemable"
    return True, None


def _to_out(coupon: Coupon, now: datetime) -> StaffCouponOut:
    valid, reason = _validity(coupon, now)
    return StaffCouponOut(
        id=coupon.id,
        code=coupon.code,
        discount_type=coupon.discount_type,
        value=float(coupon.value),
        status=coupon.status,
        expires_at=coupon.expires_at,
        redeemed_at=coupon.redeemed_at,
        customer_name=coupon.customer.name if coupon.customer else None,
        customer_phone=coupon.customer.phone if coupon.customer else None,
        prize_label=coupon.prize_tier.label if coupon.prize_tier else None,
        valid=valid,
        reason=reason,
    )


@router.post("/coupons/validate", response_model=StaffCouponOut)
def validate_coupon(payload: ValidateIn, counter: Counter, db: DbSession) -> StaffCouponOut:
    code = payload.code.strip().upper()
    coupon = db.scalar(
        select(Coupon).where(Coupon.shop_id == counter.shop_id, Coupon.code == code)
    )
    if coupon is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No coupon with that code")
    return _to_out(coupon, datetime.now(timezone.utc))


@router.post("/coupons/{coupon_id}/redeem", response_model=StaffCouponOut)
def redeem_coupon(coupon_id: uuid.UUID, counter: Counter, db: DbSession) -> StaffCouponOut:
    now = datetime.now(timezone.utc)
    # Lock the coupon row so a double-scan can't redeem twice.
    coupon = db.scalar(
        select(Coupon)
        .where(Coupon.id == coupon_id, Coupon.shop_id == counter.shop_id)
        .with_for_update()
    )
    if coupon is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Coupon not found")
    if coupon.status == CouponStatus.REDEEMED:
        raise HTTPException(status.HTTP_409_CONFLICT, "Coupon already redeemed")
    if coupon.expires_at is not None and coupon.expires_at < now:
        coupon.status = CouponStatus.EXPIRED
        db.commit()
        raise HTTPException(status.HTTP_409_CONFLICT, "Coupon has expired")
    if coupon.status != CouponStatus.ISSUED:
        raise HTTPException(status.HTTP_409_CONFLICT, "Coupon is not redeemable")

    coupon.status = CouponStatus.REDEEMED
    coupon.redeemed_at = now
    coupon.redeemed_by_user_id = counter.id
    db.commit()
    db.refresh(coupon)
    return _to_out(coupon, now)


@router.get("/activity", response_model=ActivityOut)
def activity(counter: Counter, db: DbSession) -> ActivityOut:
    now = datetime.now(timezone.utc)
    since = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
    shop_id = counter.shop_id

    def count(stmt) -> int:
        return db.scalar(stmt) or 0

    plays = count(
        select(func.count()).select_from(PlaySession).where(
            PlaySession.shop_id == shop_id, PlaySession.started_at >= since
        )
    )
    coupons = count(
        select(func.count()).select_from(Coupon).where(
            Coupon.shop_id == shop_id, Coupon.issued_at >= since
        )
    )
    redeemed = count(
        select(func.count()).select_from(Coupon).where(
            Coupon.shop_id == shop_id, Coupon.redeemed_at >= since
        )
    )
    recent = db.scalars(
        select(Coupon).where(Coupon.shop_id == shop_id).order_by(Coupon.issued_at.desc()).limit(10)
    ).all()

    return ActivityOut(
        plays_today=plays,
        coupons_today=coupons,
        redeemed_today=redeemed,
        recent=[_to_out(c, now) for c in recent],
    )
