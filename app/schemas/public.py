"""Public (customer-facing) schemas."""
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

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
    phone: str = Field(min_length=6, max_length=32)


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
