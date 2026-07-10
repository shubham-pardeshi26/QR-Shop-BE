"""Debug helper: log a staff/admin user in and exercise the auth chain.

Reads SUPABASE_URL / SUPABASE_ANON_KEY from .env (via app settings), so you
don't need shell env vars. Run from backend/ with the venv active:

    python -m scripts.get_token --email you@example.com --password 'S3cret!'

It prints the token's claims (to confirm the access-token hook injected
user_role/shop_id) and then calls the local /api/auth/me endpoint.
"""
import argparse

import httpx
from jose import jwt

from app.core.config import settings


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch a Supabase token and test /auth/me")
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--api", default="http://localhost:8000", help="Base URL of the running API")
    args = parser.parse_args()

    token_url = f"{settings.supabase_base_url}/auth/v1/token?grant_type=password"
    resp = httpx.post(
        token_url,
        headers={"apikey": settings.supabase_anon_key, "Content-Type": "application/json"},
        json={"email": args.email, "password": args.password},
        timeout=20.0,
    )
    print(f"[token] POST {token_url} -> HTTP {resp.status_code}")
    if resp.status_code != 200:
        print(resp.text)
        print("\nIf this is 400 'Invalid login credentials', the seed user "
              "doesn't exist (or the password differs) — re-run seed_super_admin.")
        return

    token = resp.json()["access_token"]
    claims = jwt.get_unverified_claims(token)
    print(f"[token] claims.aud       = {claims.get('aud')!r}")
    print(f"[token] claims.user_role = {claims.get('user_role')!r}  (None => hook not enabled)")
    print(f"[token] claims.shop_id   = {claims.get('shop_id')!r}")
    print("\n[token] access_token:")
    print(token)

    try:
        me = httpx.get(
            f"{args.api}/api/auth/me",
            headers={"Authorization": f"Bearer {token}"},
            timeout=20.0,
        )
        print(f"\n[/auth/me] HTTP {me.status_code}")
        print(me.text)
    except httpx.ConnectError:
        print("\n[/auth/me] could not reach the API — is `uvicorn app.main:app --reload` running?")


if __name__ == "__main__":
    main()
