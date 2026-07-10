"""In-code catalog of available game *types* — the pluggable registry.

Adding a new game means:
  1. add an entry to ``GAME_CATALOG`` here,
  2. implement its frontend component (frontend/src/games/…),
  3. create a ``games`` row for a shop referencing this ``slug``.

The launch set ships 4 real games + 2 disabled placeholder slots. A shop's
``games.prize_strategy`` column may override ``default_prize_strategy``.
"""
from dataclasses import dataclass

from app.enums import PrizeStrategy


@dataclass(frozen=True)
class GameType:
    slug: str
    name: str
    default_prize_strategy: PrizeStrategy
    is_placeholder: bool = False
    description: str = ""


GAME_CATALOG: dict[str, GameType] = {
    game.slug: game
    for game in (
        GameType(
            "spin_wheel", "Spin the Wheel", PrizeStrategy.RANDOM,
            description="Tap to spin; land on a prize segment.",
        ),
        GameType(
            "scratch_card", "Scratch Card", PrizeStrategy.RANDOM,
            description="Scratch to reveal your reward.",
        ),
        GameType(
            "reflex_tap", "Reflex Tap", PrizeStrategy.SKILL,
            description="Tap targets fast; score = number of hits, which sets the discount tier.",
        ),
        GameType(
            "trivia_quiz", "Trivia Quiz", PrizeStrategy.SKILL,
            description="Answer 3 questions; score = number correct (0–3) sets the discount tier.",
        ),
        GameType(
            "placeholder_1", "Coming Soon", PrizeStrategy.RANDOM, is_placeholder=True,
            description="Reserved slot for a future game.",
        ),
        GameType(
            "placeholder_2", "Coming Soon", PrizeStrategy.RANDOM, is_placeholder=True,
            description="Reserved slot for a future game.",
        ),
    )
}


def get_game_type(slug: str) -> GameType | None:
    return GAME_CATALOG.get(slug)


def playable_slugs() -> list[str]:
    """Slugs of games that are actually implemented (not placeholders)."""
    return [g.slug for g in GAME_CATALOG.values() if not g.is_placeholder]
