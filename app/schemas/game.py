"""Game and prize-tier schemas (shop-admin managed)."""
import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.enums import DiscountType, PrizeStrategy


# ---- Game type catalog (from the in-code registry) -------------------------
class GameCatalogItem(BaseModel):
    slug: str
    name: str
    default_prize_strategy: PrizeStrategy
    is_placeholder: bool
    description: str


# ---- Games -----------------------------------------------------------------
class GameCreate(BaseModel):
    type_slug: str = Field(max_length=64)
    name: str | None = Field(default=None, max_length=120)  # defaults to catalog name
    prize_strategy: PrizeStrategy | None = None              # defaults to catalog default
    enabled: bool = True
    sort_order: int = 0
    config: dict = Field(default_factory=dict)


class GameUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    prize_strategy: PrizeStrategy | None = None
    enabled: bool | None = None
    sort_order: int | None = None
    config: dict | None = None


class GameOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    type_slug: str
    name: str
    enabled: bool
    sort_order: int
    config: dict
    prize_strategy: PrizeStrategy


# ---- Prize tiers -----------------------------------------------------------
class PrizeTierCreate(BaseModel):
    label: str = Field(min_length=1, max_length=120)
    discount_type: DiscountType
    value: float = Field(ge=0)
    weight: int = Field(default=0, ge=0)          # RANDOM strategy
    min_score: int | None = Field(default=None, ge=0)  # SKILL strategy
    max_score: int | None = Field(default=None, ge=0)  # SKILL strategy
    stock_limit: int | None = Field(default=None, ge=0)
    active: bool = True


class PrizeTierUpdate(BaseModel):
    label: str | None = Field(default=None, max_length=120)
    discount_type: DiscountType | None = None
    value: float | None = Field(default=None, ge=0)
    weight: int | None = Field(default=None, ge=0)
    min_score: int | None = Field(default=None, ge=0)
    max_score: int | None = Field(default=None, ge=0)
    stock_limit: int | None = Field(default=None, ge=0)
    active: bool | None = None


class PrizeTierOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    game_id: uuid.UUID | None
    label: str
    discount_type: DiscountType
    value: float
    weight: int
    min_score: int | None
    max_score: int | None
    stock_limit: int | None
    issued_count: int
    active: bool
