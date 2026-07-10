"""Staff (counter) schemas."""
import uuid
from datetime import datetime

from pydantic import BaseModel

from app.enums import CouponStatus, DiscountType


class ValidateIn(BaseModel):
    code: str


class StaffCouponOut(BaseModel):
    id: uuid.UUID
    code: str
    discount_type: DiscountType
    value: float
    status: CouponStatus
    expires_at: datetime | None
    redeemed_at: datetime | None
    customer_name: str | None
    customer_phone: str | None
    prize_label: str | None
    valid: bool
    reason: str | None


class ActivityOut(BaseModel):
    plays_today: int
    coupons_today: int
    redeemed_today: int
    recent: list[StaffCouponOut]
