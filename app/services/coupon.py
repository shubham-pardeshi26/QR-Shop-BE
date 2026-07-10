"""Coupon issuance + anti-abuse helpers."""
import secrets
import string
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.enums import CouponStatus
from app.models import Coupon, Customer, PlaySession, PrizeTier, Shop

_CODE_ALPHABET = string.ascii_uppercase + string.digits


def _generate_code(length: int = 8) -> str:
    return "".join(secrets.choice(_CODE_ALPHABET) for _ in range(length))


def recent_coupon_count(db: Session, customer: Customer, window_hours: int) -> int:
    """How many coupons this customer has been issued within the window."""
    since = datetime.now(timezone.utc) - timedelta(hours=window_hours)
    return (
        db.scalar(
            select(func.count())
            .select_from(Coupon)
            .where(Coupon.customer_id == customer.id, Coupon.issued_at >= since)
        )
        or 0
    )


def issue_coupon(
    db: Session,
    *,
    shop: Shop,
    customer: Customer,
    session: PlaySession,
    tier: PrizeTier,
) -> Coupon:
    """Mint a single-use coupon for a resolved prize tier (not yet committed)."""
    code = _unique_code(db, shop.id)
    expires_at = (
        datetime.now(timezone.utc) + timedelta(days=shop.coupon_valid_days)
        if shop.coupon_valid_days
        else None
    )
    coupon = Coupon(
        shop_id=shop.id,
        customer_id=customer.id,
        play_session_id=session.id,
        prize_tier_id=tier.id,
        code=code,
        discount_type=tier.discount_type,
        value=tier.value,
        status=CouponStatus.ISSUED,
        expires_at=expires_at,
    )
    tier.issued_count += 1
    db.add(coupon)
    return coupon


def _unique_code(db: Session, shop_id, attempts: int = 12) -> str:
    for _ in range(attempts):
        code = _generate_code()
        exists = db.scalar(
            select(Coupon.id).where(Coupon.shop_id == shop_id, Coupon.code == code)
        )
        if exists is None:
            return code
    raise RuntimeError("Could not generate a unique coupon code")
