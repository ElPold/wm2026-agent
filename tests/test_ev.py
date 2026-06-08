from src.model.calibration import calibrate_poisson_to_market
from src.model.odds import parse_market_odds
from src.optimizer.ev import expected_points, find_optimal_tip


def test_optimal_tip_has_positive_ev():
    market = parse_market_odds(
        {"home": 1.85, "draw": 3.40, "away": 4.50},
        {"over": 2.10, "under": 1.75},
    )
    calibration = calibrate_poisson_to_market(market)
    tip = find_optimal_tip(calibration.distribution)

    assert tip.expected_points > 0
    assert tip.expected_points >= expected_points(
        calibration.distribution,
        tip.most_likely_score[0],
        tip.most_likely_score[1],
    )
