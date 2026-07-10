"""Seed (or repair) the platform super_admin.

Idempotent: creates the Supabase Auth user if missing, or adopts an existing
one (resetting its password + setting super_admin metadata), then upserts the
matching ``profiles`` row (role=super_admin, shop_id=NULL).

Run from the backend/ directory with your .env populated:

    python -m scripts.seed_super_admin --email you@example.com --password 'S3cret!'
"""
import argparse
import uuid

from app.enums import Role, UserStatus
from app.core.db import get_session_factory
from app.models import Profile
from app.services.supabase_admin import (
    create_auth_user,
    find_auth_user_by_email,
    update_auth_user,
)


def _ensure_auth_user(email: str, password: str) -> uuid.UUID:
    """Return the auth user id, creating or adopting as needed."""
    try:
        user = create_auth_user(email, password, Role.SUPER_ADMIN.value)
        print(f"Created new auth user for {email}.")
        return uuid.UUID(user["id"])
    except RuntimeError as exc:
        if "email_exists" not in str(exc):
            raise
        existing = find_auth_user_by_email(email)
        if existing is None:
            raise RuntimeError(
                f"{email} reports as existing but could not be found via the admin list"
            ) from exc
        user_id = uuid.UUID(existing["id"])
        update_auth_user(user_id, password=password, role=Role.SUPER_ADMIN.value)
        print(f"Adopted existing auth user for {email}; reset password + role.")
        return user_id


def main() -> None:
    parser = argparse.ArgumentParser(description="Create/repair the platform super_admin")
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--name", default="Platform Admin")
    args = parser.parse_args()

    user_id = _ensure_auth_user(args.email, args.password)

    session_factory = get_session_factory()
    with session_factory() as db:
        profile = db.get(Profile, user_id)
        if profile is None:
            db.add(
                Profile(
                    id=user_id,
                    role=Role.SUPER_ADMIN,
                    email=args.email,
                    shop_id=None,
                    name=args.name,
                    status=UserStatus.ACTIVE,
                )
            )
        else:
            profile.role = Role.SUPER_ADMIN
            profile.email = args.email
            profile.status = UserStatus.ACTIVE
        db.commit()

    print(f"super_admin ready: {args.email} ({user_id})")


if __name__ == "__main__":
    main()
