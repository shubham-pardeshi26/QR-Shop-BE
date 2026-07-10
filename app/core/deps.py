"""FastAPI dependencies: authentication, role checks, tenant scoping."""
import uuid
from typing import Annotated

from fastapi import Cookie, Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import verify_customer_token, verify_supabase_jwt
from app.enums import Role, UserStatus
from app.models import Customer, Profile

_bearer = HTTPBearer(auto_error=True)

CUSTOMER_COOKIE = "qg_session"


def get_current_claims(
    creds: Annotated[HTTPAuthorizationCredentials, Depends(_bearer)],
) -> dict:
    """Verify the Supabase JWT on the Authorization header."""
    try:
        return verify_supabase_jwt(creds.credentials)
    except (JWTError, ValueError) as exc:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token"
        ) from exc


def get_current_profile(
    claims: Annotated[dict, Depends(get_current_claims)],
    db: Annotated[Session, Depends(get_db)],
) -> Profile:
    """Load the app-side profile for the authenticated Supabase user."""
    sub = claims.get("sub")
    try:
        user_id = uuid.UUID(str(sub))
    except (ValueError, TypeError) as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Malformed token subject") from exc

    profile = db.get(Profile, user_id)
    if profile is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "No profile for this user")
    if profile.status != UserStatus.ACTIVE:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Account disabled")
    return profile


def require_role(*roles: Role):
    """Dependency factory enforcing that the caller has one of ``roles``."""
    allowed = set(roles)

    def _dep(profile: Annotated[Profile, Depends(get_current_profile)]) -> Profile:
        if profile.role not in allowed:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient permissions")
        return profile

    return _dep


def get_tenant_shop_id(
    profile: Annotated[Profile, Depends(get_current_profile)],
) -> uuid.UUID:
    """Resolve the shop a shop-scoped request operates on.

    shop_admin/staff are bound to their own shop. super_admins must go through
    the platform routes (which take an explicit shop id in the path).
    """
    if profile.role in (Role.SHOP_ADMIN, Role.STAFF):
        if profile.shop_id is None:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Profile is not attached to a shop")
        return profile.shop_id
    raise HTTPException(
        status.HTTP_400_BAD_REQUEST,
        "super_admin must target a specific shop via the platform routes",
    )


# Convenience aliases
CurrentProfile = Annotated[Profile, Depends(get_current_profile)]
TenantShopId = Annotated[uuid.UUID, Depends(get_tenant_shop_id)]


def get_current_customer(
    db: Annotated[Session, Depends(get_db)],
    qg_session: Annotated[str | None, Cookie()] = None,
    authorization: Annotated[str | None, Header()] = None,
) -> Customer:
    """Resolve the customer from a Bearer token or the session cookie.

    The Bearer header is preferred (works cross-site, where the cookie won't be
    sent); the httpOnly cookie is a same-origin fallback.
    """
    token: str | None = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
    elif qg_session:
        token = qg_session
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "No customer session")
    try:
        claims = verify_customer_token(token)
        customer_id = uuid.UUID(str(claims.get("sub")))
    except (JWTError, ValueError) as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid customer session") from exc

    customer = db.get(Customer, customer_id)
    if customer is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Customer not found")
    return customer


CurrentCustomer = Annotated[Customer, Depends(get_current_customer)]
