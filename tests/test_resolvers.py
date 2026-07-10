"""Prize resolution engine — weighted-random and skill strategies."""
from app.enums import PrizeStrategy
from app.games.resolvers import resolve_prize


def test_random_only_draws_weighted_tiers(db, make_shop, make_game, make_tier):
    shop = make_shop()
    game = make_game(shop, strategy=PrizeStrategy.RANDOM)
    winner = make_tier(shop, game, label="win", weight=5)
    make_tier(shop, game, label="never", weight=0)  # weight 0 → excluded
    for _ in range(25):
        assert resolve_prize(db, game, None).id == winner.id


def test_random_none_when_no_tiers(db, make_shop, make_game):
    shop = make_shop()
    game = make_game(shop, strategy=PrizeStrategy.RANDOM)
    assert resolve_prize(db, game, None) is None


def test_random_respects_stock_limit(db, make_shop, make_game, make_tier):
    shop = make_shop()
    game = make_game(shop, strategy=PrizeStrategy.RANDOM)
    tier = make_tier(shop, game, weight=1, stock_limit=1)
    tier.issued_count = 1
    db.commit()
    assert resolve_prize(db, game, None) is None


def test_random_skips_inactive(db, make_shop, make_game, make_tier):
    shop = make_shop()
    game = make_game(shop, strategy=PrizeStrategy.RANDOM)
    make_tier(shop, game, weight=1, active=False)
    assert resolve_prize(db, game, None) is None


def test_skill_maps_score_to_band(db, make_shop, make_game, make_tier):
    shop = make_shop()
    game = make_game(shop, strategy=PrizeStrategy.SKILL)
    low = make_tier(shop, game, label="low", value=5, weight=0, min_score=0, max_score=1)
    high = make_tier(shop, game, label="high", value=20, weight=0, min_score=2, max_score=3)
    assert resolve_prize(db, game, 0).id == low.id
    assert resolve_prize(db, game, 3).id == high.id
    assert resolve_prize(db, game, 99) is None  # out of every band
    assert resolve_prize(db, game, None) is None  # skill needs a score


def test_skill_picks_highest_value_in_band(db, make_shop, make_game, make_tier):
    shop = make_shop()
    game = make_game(shop, strategy=PrizeStrategy.SKILL)
    make_tier(shop, game, label="small", value=5, weight=0, min_score=0, max_score=10)
    big = make_tier(shop, game, label="big", value=15, weight=0, min_score=0, max_score=10)
    assert resolve_prize(db, game, 5).id == big.id
