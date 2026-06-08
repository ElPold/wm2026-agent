from src.optimizer.scoring import kicktipp_points


def test_exact_score_four_points():
    assert kicktipp_points(2, 1, 2, 1) == 4


def test_goal_difference_three_points():
    assert kicktipp_points(1, 0, 2, 1) == 3


def test_tendency_two_points():
    assert kicktipp_points(3, 0, 2, 0) == 2


def test_draw_tendency_two_points():
    assert kicktipp_points(1, 1, 0, 0) == 2


def test_wrong_winner_zero_points():
    assert kicktipp_points(0, 1, 2, 1) == 0
