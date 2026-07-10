"""Token security + small utilities + the game registry."""
import pytest
from jose import JWTError

from app.core import security
from app.core.security import create_customer_token, verify_customer_token
from app.core.utils import slugify
from app.games.registry import GAME_CATALOG, get_game_type, playable_slugs


def test_customer_token_roundtrip():
    token = create_customer_token("cust-1", "shop-1")
    claims = verify_customer_token(token)
    assert claims["sub"] == "cust-1"
    assert claims["shop_id"] == "shop-1"
    assert claims["typ"] == "customer"


def test_customer_token_rejects_tampering():
    token = create_customer_token("cust-1", "shop-1")
    with pytest.raises(JWTError):
        verify_customer_token(token + "tamper")


def test_customer_secret_required(monkeypatch):
    monkeypatch.setattr(security.settings, "customer_jwt_secret", "")
    with pytest.raises(ValueError):
        create_customer_token("a", "b")


def test_slugify():
    assert slugify("Bob's Cafe!") == "bob-s-cafe"
    assert slugify("  Multiple   Spaces  ") == "multiple-spaces"
    assert slugify("") == "shop"
    assert slugify("!!!") == "shop"


def test_game_catalog():
    assert len(GAME_CATALOG) == 6
    assert set(playable_slugs()) == {"spin_wheel", "scratch_card", "reflex_tap", "trivia_quiz"}
    assert get_game_type("placeholder_1").is_placeholder is True
    assert get_game_type("nope") is None
