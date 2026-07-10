"""Staff (counter) endpoints: validate, redeem, expiry, activity, isolation."""
from datetime import datetime, timedelta, timezone

from app.enums import Role
from app.services.coupon import issue_coupon


def _issue(db, shop, game, tier, customer, make_session):
    coupon = issue_coupon(
        db, shop=shop, customer=customer, session=make_session(shop, customer, game), tier=tier
    )
    db.commit()
    db.refresh(coupon)
    return coupon


def test_validate_and_redeem(
    client, db, make_shop, make_game, make_tier, make_customer, make_session, make_user, as_profile
):
    shop = make_shop(slug="rs", coupon_valid_days=7)
    game = make_game(shop)
    tier = make_tier(shop, game, value=10)
    customer = make_customer(shop)
    coupon = _issue(db, shop, game, tier, customer, make_session)

    as_profile(make_user(Role.STAFF, shop_id=shop.id))

    check = client.post("/api/staff/coupons/validate", json={"code": coupon.code})
    assert check.status_code == 200
    assert check.json()["valid"] is True
    assert check.json()["customer_name"] == "Cust"

    redeemed = client.post(f"/api/staff/coupons/{coupon.id}/redeem")
    assert redeemed.status_code == 200
    assert redeemed.json()["status"] == "redeemed"

    # Second redeem is rejected.
    assert client.post(f"/api/staff/coupons/{coupon.id}/redeem").status_code == 409


def test_validate_unknown_code_404(client, make_shop, make_user, as_profile):
    shop = make_shop(slug="rs")
    as_profile(make_user(Role.STAFF, shop_id=shop.id))
    assert client.post("/api/staff/coupons/validate", json={"code": "NOPE1234"}).status_code == 404


def test_redeem_expired(
    client, db, make_shop, make_game, make_tier, make_customer, make_session, make_user, as_profile
):
    shop = make_shop(slug="rs", coupon_valid_days=7)
    game = make_game(shop)
    tier = make_tier(shop, game)
    customer = make_customer(shop)
    coupon = _issue(db, shop, game, tier, customer, make_session)
    coupon.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
    db.commit()

    as_profile(make_user(Role.STAFF, shop_id=shop.id))
    assert client.post(f"/api/staff/coupons/{coupon.id}/redeem").status_code == 409


def test_activity(client, make_shop, make_user, as_profile):
    shop = make_shop(slug="rs")
    as_profile(make_user(Role.STAFF, shop_id=shop.id))
    body = client.get("/api/staff/activity").json()
    assert set(body) >= {"plays_today", "coupons_today", "redeemed_today", "recent"}


def test_staff_cannot_see_other_shop_coupon(
    client, db, make_shop, make_game, make_tier, make_customer, make_session, make_user, as_profile
):
    shop_a = make_shop(slug="a")
    shop_b = make_shop(slug="b")
    game_b = make_game(shop_b)
    tier_b = make_tier(shop_b, game_b)
    customer_b = make_customer(shop_b)
    coupon_b = _issue(db, shop_b, game_b, tier_b, customer_b, make_session)

    as_profile(make_user(Role.STAFF, shop_id=shop_a.id))
    # Staff of shop A cannot validate or redeem shop B's coupon.
    assert client.post("/api/staff/coupons/validate", json={"code": coupon_b.code}).status_code == 404
    assert client.post(f"/api/staff/coupons/{coupon_b.id}/redeem").status_code == 404
