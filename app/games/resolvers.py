"""Prize resolution — the shared engine behind every game.

RANDOM games draw a weighted prize tier; SKILL games map the final score into a
tier's [min_score, max_score] range. Both respect per-tier stock limits.
Returns ``None`` when no tier is eligible (a legitimate "no win").
"""
import random

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.enums import PrizeStrategy
from app.models import Game, PrizeTier


def _eligible_tiers(db: Session, game: Game) -> list[PrizeTier]:
    tiers = db.scalars(
        select(PrizeTier).where(PrizeTier.game_id == game.id, PrizeTier.active.is_(True))
    ).all()
    return [t for t in tiers if t.stock_limit is None or t.issued_count < t.stock_limit]


def resolve_prize(db: Session, game: Game, score: int | None) -> PrizeTier | None:
    tiers = _eligible_tiers(db, game)
    if not tiers:
        return None

    if game.prize_strategy == PrizeStrategy.RANDOM:
        weighted = [t for t in tiers if t.weight and t.weight > 0]
        if not weighted:
            return None
        return random.choices(weighted, weights=[t.weight for t in weighted], k=1)[0]

    # SKILL: highest-value tier whose score band contains the score.
    if score is None:
        return None
    matches = [
        t
        for t in tiers
        if (t.min_score is None or score >= t.min_score)
        and (t.max_score is None or score <= t.max_score)
    ]
    if not matches:
        return None
    return max(matches, key=lambda t: float(t.value))
