"""Customer public flow: register → start → complete → coupon, incl. anti-abuse."""


def _register(client, slug, phone="+15550000009"):
    return client.post(f"/api/public/s/{slug}/register", json={"name": "Ada", "phone": phone})


def test_health(client):
    assert client.get("/api/health").json()["status"] == "ok"


def test_unknown_shop_404(client):
    assert client.get("/api/public/s/does-not-exist").status_code == 404


def test_get_shop_lists_enabled_games(client, make_shop, make_game):
    shop = make_shop(slug="cafe")
    make_game(shop, slug="spin_wheel", name="Spin")
    make_game(shop, slug="scratch_card", name="Scratch", enabled=False)  # hidden
    body = client.get(f"/api/public/s/{shop.slug}").json()
    assert body["shop"]["slug"] == "cafe"
    assert [g["name"] for g in body["games"]] == ["Spin"]


def test_play_requires_session(client, make_shop, make_game):
    shop = make_shop(slug="cafe")
    game = make_game(shop)
    assert client.post(f"/api/public/play/games/{game.id}/start", json={}).status_code == 401


def test_full_win_flow(client, make_shop, make_game, make_tier):
    shop = make_shop(slug="cafe", coupon_valid_days=7)
    game = make_game(shop, slug="spin_wheel")
    make_tier(shop, game, label="10% off", value=10, weight=1)

    assert _register(client, shop.slug).status_code == 200

    start = client.post(f"/api/public/play/games/{game.id}/start", json={})
    assert start.status_code == 200
    assert len(start.json()["segments"]) == 1
    session_id = start.json()["session_id"]

    complete = client.post(f"/api/public/play/sessions/{session_id}/complete", json={})
    assert complete.status_code == 200
    coupon = complete.json()["coupon"]
    assert coupon is not None and float(coupon["value"]) == 10 and coupon["code"]

    mine = client.get("/api/public/play/coupons/mine")
    assert mine.status_code == 200 and len(mine.json()) == 1


def test_no_prize_when_no_tiers(client, make_shop, make_game):
    shop = make_shop(slug="cafe")
    game = make_game(shop)
    _register(client, shop.slug)
    session_id = client.post(f"/api/public/play/games/{game.id}/start", json={}).json()["session_id"]
    body = client.post(f"/api/public/play/sessions/{session_id}/complete", json={}).json()
    assert body["coupon"] is None


def test_double_complete_conflicts(client, make_shop, make_game, make_tier):
    shop = make_shop(slug="cafe")
    game = make_game(shop)
    make_tier(shop, game, weight=1)
    _register(client, shop.slug)
    session_id = client.post(f"/api/public/play/games/{game.id}/start", json={}).json()["session_id"]
    assert client.post(f"/api/public/play/sessions/{session_id}/complete", json={}).status_code == 200
    assert client.post(f"/api/public/play/sessions/{session_id}/complete", json={}).status_code == 409


def test_per_phone_cap_blocks_second_start(client, make_shop, make_game, make_tier):
    shop = make_shop(slug="cafe", max_coupons_per_phone=1, coupon_window_hours=24)
    game = make_game(shop)
    make_tier(shop, game, weight=1)
    _register(client, shop.slug)
    session_id = client.post(f"/api/public/play/games/{game.id}/start", json={}).json()["session_id"]
    client.post(f"/api/public/play/sessions/{session_id}/complete", json={})  # win 1
    # Cap reached → a new start is refused.
    assert client.post(f"/api/public/play/games/{game.id}/start", json={}).status_code == 429
