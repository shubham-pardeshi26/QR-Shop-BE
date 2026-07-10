"""Token handling.

- Staff/admin tokens are issued by **Supabase Auth** and only *verified* here.
  Supabase may sign with a symmetric secret (legacy HS256) or, on newer
  projects, asymmetric keys (ES256/RS256) exposed via a JWKS endpoint — this
  module supports both.
- Customer sessions are password-less and *minted* here (separate HS256
  secret), so transient shoppers never become Supabase Auth users.
"""
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from jose import jwt

from app.core.config import settings

CUSTOMER_ALGORITHM = "HS256"

# Cached JWKS (public keys) for verifying asymmetric Supabase tokens.
_jwks_cache: dict[str, Any] | None = None


def _customer_secret() -> str:
    """The customer-session signing key, validated (fail loudly if unset)."""
    secret = settings.customer_jwt_secret
    if not secret:
        raise ValueError("CUSTOMER_JWT_SECRET is not configured")
    if settings.is_production and secret == "change-me-in-production":
        raise ValueError("CUSTOMER_JWT_SECRET must be changed from the placeholder in production")
    return secret


def _fetch_jwks(force: bool = False) -> dict[str, Any]:
    global _jwks_cache
    if _jwks_cache is None or force:
        url = f"{settings.supabase_base_url}/auth/v1/.well-known/jwks.json"
        headers = {"apikey": settings.supabase_anon_key} if settings.supabase_anon_key else {}
        resp = httpx.get(url, headers=headers, timeout=10.0)
        resp.raise_for_status()
        _jwks_cache = resp.json()
    return _jwks_cache


def _jwk_for_kid(kid: str) -> dict[str, Any] | None:
    jwks = _fetch_jwks()
    for key in jwks.get("keys", []):
        if key.get("kid") == kid:
            return key
    # Miss — refresh once in case keys were rotated, then retry.
    jwks = _fetch_jwks(force=True)
    for key in jwks.get("keys", []):
        if key.get("kid") == kid:
            return key
    return None


def verify_supabase_jwt(token: str) -> dict[str, Any]:
    """Verify a Supabase Auth access token and return its claims.

    Raises ``jose.JWTError`` (or ``ValueError``) on any validation failure.
    """
    header = jwt.get_unverified_header(token)
    alg = header.get("alg", "")

    if alg == "HS256":
        if not settings.supabase_jwt_secret:
            raise ValueError("SUPABASE_JWT_SECRET is not configured (HS256 token)")
        key: Any = settings.supabase_jwt_secret
    else:
        # Asymmetric (ES256 / RS256) — verify against the project's JWKS.
        kid = header.get("kid")
        if not kid:
            raise ValueError("Token header missing 'kid' for asymmetric verification")
        key = _jwk_for_kid(kid)
        if key is None:
            raise ValueError(f"No JWKS key matching kid={kid}")

    return jwt.decode(token, key, algorithms=[alg], audience="authenticated")


def create_customer_token(customer_id: str, shop_id: str) -> str:
    """Mint a short-lived customer session token."""
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.customer_session_ttl_minutes)
    payload = {
        "sub": str(customer_id),
        "shop_id": str(shop_id),
        "typ": "customer",
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    return jwt.encode(payload, _customer_secret(), algorithm=CUSTOMER_ALGORITHM)


def verify_customer_token(token: str) -> dict[str, Any]:
    """Verify a customer session token. Raises on failure."""
    claims = jwt.decode(token, _customer_secret(), algorithms=[CUSTOMER_ALGORITHM])
    if claims.get("typ") != "customer":
        raise ValueError("Not a customer token")
    return claims
