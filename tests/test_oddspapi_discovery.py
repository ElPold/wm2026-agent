from src.sources.oddspapi import (
    _is_excluded_tournament,
    _is_national_world_cup_candidate,
    _score_world_cup_candidate,
)


def test_excludes_club_world_cup():
    assert _is_excluded_tournament("fifa club world cup", "fifa-club-world-cup")


def test_accepts_national_world_cup():
    assert _is_national_world_cup_candidate("world cup", "world-cup")


def test_prefers_world_cup_slug():
    score = _score_world_cup_candidate(
        "world cup",
        "world-cup",
        {"futureFixtures": 72, "upcomingFixtures": 0},
    )
    assert score >= 172
