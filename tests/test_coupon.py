"""Coupon issuance + anti-abuse counting."""
from datetime import datetime, timedelta, timezone

from app.enums import CouponStatus
from app.models import Coupon
from app.services.coupon import _generate_code, issue_coupon, recent_coupon_count


def test_generate_code_shape():
    code = _generate_code()
    assert len(code) == 8
    assert code.isalnum() and code.isupper()


def test_issue_coupon_sets_fields_and_increments_stock(
    db, make_shop, make_game, make_tier, make_customer, make_session
):
    shop = make_shop(coupon_valid_days=7)
    game = make_game(shop)
    tier = make_tier(shop, game, value=15)
    customer = make_customer(shop)
    session = make_session(shop, customer, game)

    coupon = issue_coupon(db, shop=shop, customer=customer, session=session, tier=tier)
    db.commit()
    db.refresh(coupon)
    db.refresh(tier)

    assert coupon.status == CouponStatus.ISSUED
    assert float(coupon.value) == 15
    assert coupon.code
    assert coupon.expires_at is not None
    assert coupon.expires_at > datetime.now(timezone.utc)
    assert tier.issued_count == 1


def test_issue_coupon_no_expiry_when_zero_valid_days(
    db, make_shop, make_game, make_tier, make_customer, make_session
):
    shop = make_shop(coupon_valid_days=0)
    game = make_game(shop)
    tier = make_tier(shop, game)
    customer = make_customer(shop)
    session = make_session(shop, customer, game)
    coupon = issue_coupon(db, shop=shop, customer=customer, session=session, tier=tier)
    db.commit()
    assert coupon.expires_at is None


def test_recent_coupon_count_window(
    db, make_shop, make_game, make_tier, make_customer, make_session
):
    shop = make_shop()
    game = make_game(shop)
    tier = make_tier(shop, game)
    customer = make_customer(shop)
    assert recent_coupon_count(db, customer, 24) == 0

    coupon = issue_coupon(
        db, shop=shop, customer=customer, session=make_session(shop, customer, game), tier=tier
    )
    db.commit()
    assert recent_coupon_count(db, customer, 24) == 1

    # A coupon issued 48h ago falls outside a 24h window.
    coupon.issued_at = datetime.now(timezone.utc) - timedelta(hours=48)
    db.commit()
    assert recent_coupon_count(db, customer, 24) == 0


def test_coupon_code_unique_per_shop(
    db, make_shop, make_game, make_tier, make_customer, make_session
):
    shop = make_shop()
    game = make_game(shop)
    tier = make_tier(shop, game)
    customer = make_customer(shop)
    codes = set()
    for _ in range(5):
        c = issue_coupon(
            db, shop=shop, customer=customer, session=make_session(shop, customer, game), tier=tier
        )
        db.commit()
        codes.add(c.code)
    assert len(codes) == 5
