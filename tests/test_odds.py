import pytest

from src.model.odds import odds_to_probabilities, parse_market_odds


def test_odds_sum_to_one():
    probs = odds_to_probabilities({"home": 2.0, "draw": 3.5, "away": 4.0})
    assert abs(sum(probs.values()) - 1.0) < 1e-9


def test_parse_market_odds_keys():
    market = parse_market_odds(
        {"home": 1.9, "draw": 3.4, "away": 4.2},
        {"over": 2.0, "under": 1.8},
    )
    assert set(market.keys()) == {"home", "draw", "away", "over_2_5", "under_2_5"}


def test_invalid_odds_raises():
    with pytest.raises(ValueError):
        odds_to_probabilities({"home": 0.5})
