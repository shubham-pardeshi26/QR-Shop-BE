"""Provision staff/admin users: a Supabase Auth user + a matching profile.

Used by the platform (create shop_admin) and shop-admin (create staff) flows.
If the auth user creation succeeds but the DB insert fails, the auth user is
rolled back so the operation is all-or-nothing.
"""
import uuid

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.enums import Role
from app.models import Profile
from app.services.supabase_admin import create_auth_user, delete_auth_user


def provision_user(
    db: Session,
    *,
    email: str,
    password: str,
    name: str,
    role: Role,
    shop_id: uuid.UUID | None,
) -> Profile:
    try:
        auth_user = create_auth_user(email, password, role.value, shop_id)
    except RuntimeError as exc:
        if "email_exists" in str(exc):
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail="A user with this email is already registered",
            ) from exc
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    user_id = uuid.UUID(auth_user["id"])
    profile = Profile(
        id=user_id,
        role=role,
        email=email,
        name=name,
        shop_id=shop_id,
    )
    try:
        db.add(profile)
        db.commit()
        db.refresh(profile)
    except Exception:
        db.rollback()
        delete_auth_user(user_id)  # keep auth + DB in sync
        raise
    return profile
