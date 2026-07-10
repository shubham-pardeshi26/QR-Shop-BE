"""Platform (super-admin) endpoints."""
import uuid

from app.enums import Role


def test_shop_admin_cannot_access_platform(client, make_shop, make_user, as_profile):
    shop = make_shop(slug="s1")
    as_profile(make_user(Role.SHOP_ADMIN, shop_id=shop.id))
    assert client.get("/api/platform/shops").status_code == 403


def test_create_and_list_shops_and_stats(client, make_user, as_profile):
    as_profile(make_user(Role.SUPER_ADMIN))
    created = client.post("/api/platform/shops", json={"name": "Bob's Cafe"})
    assert created.status_code == 201
    assert created.json()["slug"] == "bob-s-cafe"

    shops = client.get("/api/platform/shops")
    assert shops.status_code == 200 and len(shops.json()) == 1

    stats = client.get("/api/platform/stats").json()
    assert stats["shops"] == 1


def test_duplicate_slug_conflict(client, make_user, as_profile):
    as_profile(make_user(Role.SUPER_ADMIN))
    assert client.post("/api/platform/shops", json={"name": "Cafe", "slug": "dup"}).status_code == 201
    assert client.post("/api/platform/shops", json={"name": "Other", "slug": "dup"}).status_code == 409


def test_create_shop_admin_provisions_profile(client, make_shop, make_user, as_profile, monkeypatch):
    import app.services.provisioning as provisioning

    fake_id = str(uuid.uuid4())
    monkeypatch.setattr(provisioning, "create_auth_user", lambda *a, **k: {"id": fake_id})

    as_profile(make_user(Role.SUPER_ADMIN))
    shop = make_shop(slug="ps")
    resp = client.post(
        f"/api/platform/shops/{shop.id}/admins",
        json={"email": "owner@bobscafe.com", "password": "password123", "name": "Owner"},
    )
    assert resp.status_code == 201
    assert resp.json()["role"] == "shop_admin"
    assert resp.json()["id"] == fake_id

    users = client.get(f"/api/platform/shops/{shop.id}/users").json()
    assert any(u["email"] == "owner@bobscafe.com" for u in users)


def test_delete_shop(client, make_shop, make_user, as_profile):
    as_profile(make_user(Role.SUPER_ADMIN))
    shop = make_shop(slug="gone")
    assert client.delete(f"/api/platform/shops/{shop.id}").status_code == 204
    assert client.get(f"/api/platform/shops/{shop.id}").status_code == 404
