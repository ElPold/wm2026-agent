from src.model.poisson import outcome_probabilities, poisson_score_distribution


def test_distribution_sums_to_one():
    dist = poisson_score_distribution(1.3, 1.1)
    assert abs(sum(dist.values()) - 1.0) < 1e-9


def test_outcome_probs_sum_sensibly():
    dist = poisson_score_distribution(1.5, 0.8)
    probs = outcome_probabilities(dist)
    assert abs(probs["home"] + probs["draw"] + probs["away"] - 1.0) < 1e-9
    assert abs(probs["over_2_5"] + probs["under_2_5"] - 1.0) < 1e-9
