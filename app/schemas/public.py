"""Public (customer-facing) schemas."""
import re
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.enums import CouponStatus, DiscountType


class ShopPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    slug: str
    currency: str
    branding: dict


class GamePublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    type_slug: str
    name: str


class ShopWithGames(BaseModel):
    shop: ShopPublic
    games: list[GamePublic]


class RegisterIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    phone: str

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str) -> str:
        cleaned = re.sub(r"[\s()\-]", "", value.strip())
        if not cleaned.isdigit() or len(cleaned) != 10:
            raise ValueError("Enter a valid 10-digit phone number")
        return cleaned


class RegisterOut(ShopWithGames):
    # Customer session token — the frontend stores it and sends it as a Bearer
    # header (works cross-site, unlike the fallback cookie).
    session_token: str


class SegmentOut(BaseModel):
    label: str


class StartOut(BaseModel):
    session_id: uuid.UUID
    game: GamePublic
    segments: list[SegmentOut]


class CompleteIn(BaseModel):
    score: int | None = Field(default=None, ge=0)


class CouponPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str
    discount_type: DiscountType
    value: float
    status: CouponStatus
    expires_at: datetime | None


class PlayResultOut(BaseModel):
    coupon: CouponPublic | None
    prize_label: str | None
    message: str | None = None
