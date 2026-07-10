"""Shop schemas (platform-managed tenants)."""
import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.enums import ShopStatus


class ShopCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    slug: str | None = Field(default=None, max_length=64)  # derived from name if omitted
    currency: str = Field(default="INR", max_length=8)
    timezone: str = Field(default="UTC", max_length=64)
    branding: dict = Field(default_factory=dict)


class ShopUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    currency: str | None = Field(default=None, max_length=8)
    timezone: str | None = Field(default=None, max_length=64)
    branding: dict | None = None
    status: ShopStatus | None = None
    max_coupons_per_phone: int | None = Field(default=None, ge=1)
    coupon_window_hours: int | None = Field(default=None, ge=1)
    coupon_valid_days: int | None = Field(default=None, ge=1)


class ShopOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    currency: str
    timezone: str
    branding: dict
    status: ShopStatus
    max_coupons_per_phone: int
    coupon_window_hours: int
    coupon_valid_days: int
