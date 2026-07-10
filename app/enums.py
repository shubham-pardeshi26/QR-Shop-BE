"""Shared enums used across models, schemas, and the game registry.

Single source of truth so the DB, API, and game layer agree on string values.
Stored in the DB as VARCHAR (see ``make_enum``) using the lowercase *values*.
"""
from enum import Enum


class Role(str, Enum):
    SUPER_ADMIN = "super_admin"  # platform owner
    SHOP_ADMIN = "shop_admin"    # shop owner
    STAFF = "staff"              # counter staff


class PrizeStrategy(str, Enum):
    RANDOM = "random"  # weighted draw over prize_tiers (odds set by admin)
    SKILL = "skill"    # final score maps into a tier's [min_score, max_score]


class DiscountType(str, Enum):
    PERCENT = "percent"
    AMOUNT = "amount"
    FREE_ITEM = "free_item"


class CouponStatus(str, Enum):
    ISSUED = "issued"
    REDEEMED = "redeemed"
    EXPIRED = "expired"


class PlaySessionStatus(str, Enum):
    STARTED = "started"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


class ShopStatus(str, Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"


class UserStatus(str, Enum):
    ACTIVE = "active"
    DISABLED = "disabled"
