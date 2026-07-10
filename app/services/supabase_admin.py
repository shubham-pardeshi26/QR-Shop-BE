"""Thin wrapper over the Supabase Auth Admin API (service-role only).

Used to create staff/admin auth users. The returned ``id`` becomes the
``profiles.id`` we store, and ``app_metadata`` carries role + shop_id so a
custom access-token hook can mirror them into JWT claims (for RLS).
"""
from typing import Any
from uuid import UUID

import httpx

from app.core.config import settings


def _admin_headers() -> dict[str, str]:
    key = settings.supabase_service_role_key
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }


def create_auth_user(
    email: str,
    password: str,
    role: str,
    shop_id: UUID | str | None = None,
) -> dict[str, Any]:
    """Create a confirmed Supabase Auth user. Returns the user JSON (incl. id)."""
    if not settings.supabase_url or not settings.supabase_service_role_key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")

    url = f"{settings.supabase_base_url}/auth/v1/admin/users"
    body = {
        "email": email,
        "password": password,
        "email_confirm": True,
        "app_metadata": {
            "user_role": role,
            "shop_id": str(shop_id) if shop_id else None,
        },
    }
    resp = httpx.post(url, json=body, headers=_admin_headers(), timeout=20.0)
    if resp.is_error:
        raise RuntimeError(
            f"Supabase Admin API {resp.status_code} at {url}: {resp.text}"
        )
    return resp.json()


def update_auth_user(
    user_id: UUID | str,
    *,
    password: str | None = None,
    role: str | None = None,
    shop_id: UUID | str | None = None,
) -> dict[str, Any]:
    """Update an existing auth user's password and/or app_metadata."""
    url = f"{settings.supabase_base_url}/auth/v1/admin/users/{user_id}"
    body: dict[str, Any] = {}
    if password is not None:
        body["password"] = password
    if role is not None:
        body["app_metadata"] = {"user_role": role, "shop_id": str(shop_id) if shop_id else None}
    resp = httpx.put(url, json=body, headers=_admin_headers(), timeout=20.0)
    if resp.is_error:
        raise RuntimeError(f"Supabase Admin API {resp.status_code} at {url}: {resp.text}")
    return resp.json()


def find_auth_user_by_email(email: str) -> dict[str, Any] | None:
    """Find an auth user by email by paging the admin list endpoint."""
    url = f"{settings.supabase_base_url}/auth/v1/admin/users"
    target = email.strip().lower()
    for page in range(1, 51):  # safety cap: 50 pages
        resp = httpx.get(
            url,
            params={"page": page, "per_page": 200},
            headers=_admin_headers(),
            timeout=20.0,
        )
        if resp.is_error:
            raise RuntimeError(f"Supabase Admin API {resp.status_code} at {url}: {resp.text}")
        data = resp.json()
        users = data.get("users", []) if isinstance(data, dict) else data
        if not users:
            return None
        for user in users:
            if (user.get("email") or "").strip().lower() == target:
                return user
        if len(users) < 200:
            return None
    return None


def delete_auth_user(user_id: UUID | str) -> None:
    """Delete a Supabase Auth user (used to roll back a failed provisioning)."""
    url = f"{settings.supabase_base_url}/auth/v1/admin/users/{user_id}"
    resp = httpx.delete(url, headers=_admin_headers(), timeout=20.0)
    if resp.is_error:
        raise RuntimeError(
            f"Supabase Admin API {resp.status_code} at {url}: {resp.text}"
        )
