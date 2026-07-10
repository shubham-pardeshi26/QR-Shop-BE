"""Analytics schemas (shop-admin dashboards)."""
from pydantic import BaseModel


class GameStat(BaseModel):
    game: str
    plays: int


class DayStat(BaseModel):
    date: str  # ISO date (YYYY-MM-DD)
    coupons: int


class AnalyticsOut(BaseModel):
    total_customers: int
    total_plays: int
    coupons_issued: int
    coupons_redeemed: int
    redemption_rate: float  # redeemed / issued, 0..1
    plays_by_game: list[GameStat]
    coupons_last_7_days: list[DayStat]
