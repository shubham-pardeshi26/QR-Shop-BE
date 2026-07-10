"""Shop-admin endpoints: RBAC, tenant scoping, games/prizes, analytics, leads."""
from app.enums import Role


def test_auth_me(client, make_shop, make_user, as_profile):
    shop = make_shop(slug="s1")
    admin = make_user(Role.SHOP_ADMIN, shop_id=shop.id)
    as_profile(admin)
    body = client.get("/api/auth/me").json()
    assert body["role"] == "shop_admin"


def test_staff_cannot_access_admin(client, make_shop, make_user, as_profile):
    shop = make_shop(slug="s1")
    as_profile(make_user(Role.STAFF, shop_id=shop.id))
    assert client.get("/api/admin/games").status_code == 403


def test_game_and_prize_crud(client, make_shop, make_user, as_profile):
    shop = make_shop(slug="s1")
    as_profile(make_user(Role.SHOP_ADMIN, shop_id=shop.id))

    assert client.get("/api/admin/game-catalog").status_code == 200

    created = client.post("/api/admin/games", json={"type_slug": "spin_wheel"})
    assert created.status_code == 201
    game_id = created.json()["id"]
    # Catalog defaults applied:
    assert created.json()["prize_strategy"] == "random"

    prize = client.post(
        f"/api/admin/games/{game_id}/prizes",
        json={"label": "10% off", "discount_type": "percent", "value": 10, "weight": 3},
    )
    assert prize.status_code == 201

    assert len(client.get("/api/admin/games").json()) == 1
    assert len(client.get(f"/api/admin/games/{game_id}/prizes").json()) == 1

    # Toggle + delete
    assert client.patch(f"/api/admin/games/{game_id}", json={"enabled": False}).json()["enabled"] is False
    assert client.delete(f"/api/admin/games/{game_id}").status_code == 204


def test_unknown_game_type_rejected(client, make_shop, make_user, as_profile):
    shop = make_shop(slug="s1")
    as_profile(make_user(Role.SHOP_ADMIN, shop_id=shop.id))
    assert client.post("/api/admin/games", json={"type_slug": "bogus"}).status_code == 400


def test_qr_and_shop_settings(client, make_shop, make_user, as_profile):
    shop = make_shop(slug="s1")
    as_profile(make_user(Role.SHOP_ADMIN, shop_id=shop.id))

    qr = client.get("/api/admin/qr").json()
    assert "svg" in qr and shop.slug in qr["url"]

    updated = client.patch("/api/admin/shop", json={"name": "Renamed", "max_coupons_per_phone": 3})
    assert updated.status_code == 200
    assert updated.json()["name"] == "Renamed"
    assert updated.json()["max_coupons_per_phone"] == 3


def test_analytics_and_leads(client, make_shop, make_game, make_customer, make_user, as_profile):
    shop = make_shop(slug="s1")
    make_game(shop)
    make_customer(shop, name="Lead", phone="+15551230000")
    as_profile(make_user(Role.SHOP_ADMIN, shop_id=shop.id))

    analytics = client.get("/api/admin/analytics")
    assert analytics.status_code == 200
    assert analytics.json()["total_customers"] == 1
    assert len(analytics.json()["coupons_last_7_days"]) == 7

    leads = client.get("/api/admin/leads.csv")
    assert leads.status_code == 200
    assert "name,phone" in leads.text
    assert "+15551230000" in leads.text


def test_admin_tenant_isolation(client, make_shop, make_game, make_user, as_profile):
    shop_a = make_shop(slug="a")
    shop_b = make_shop(slug="b")
    game_b = make_game(shop_b)
    as_profile(make_user(Role.SHOP_ADMIN, shop_id=shop_a.id))
    # Admin A cannot modify shop B's game.
    assert client.patch(f"/api/admin/games/{game_b.id}", json={"enabled": False}).status_code == 404
    assert client.delete(f"/api/admin/games/{game_b.id}").status_code == 404
