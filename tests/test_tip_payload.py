from src.optimizer.tip_payload import (
    build_ev_alternatives_display,
    ensure_top_alternatives,
    is_blowout_tip,
    parse_tip_scores,
    recommendation_from_stored_odds,
    top_alternatives_to_json,
)
from src.site.generator import _build_badges, _enrich_match


def test_parse_tip_scores():
    assert parse_tip_scores("1:0") == (1, 0)
    assert parse_tip_scores("2:0") == (2, 0)
    assert parse_tip_scores(None) is None


def test_is_blowout_tip():
    assert is_blowout_tip(1, 0) is False
    assert is_blowout_tip(0, 1) is False
    assert is_blowout_tip(2, 0) is True


def test_top_alternatives_from_heavy_favorite():
    recommendation = recommendation_from_stored_odds(
        {"home": 1.15, "draw": 8.0, "away": 21.0},
        {"over": 1.45, "under": 2.8},
    )
    payload = top_alternatives_to_json(recommendation.top_alternatives)
    assert len(payload) == 3
    assert recommendation.tip_home == 2
    assert recommendation.tip_away == 0


def test_ensure_top_alternatives_backfills_from_odds():
    item = {
        "tip": "1:0",
        "expected_points": 1.2,
        "odds_1x2": {"home": 2.5, "draw": 2.18, "away": 5.03},
        "odds_ou25": {"over": 2.22, "under": 1.704},
    }
    alternatives = ensure_top_alternatives(item)
    assert len(alternatives) == 3
    assert "score" in alternatives[0]
    assert "expected_points" in alternatives[0]


def test_build_ev_alternatives_display_includes_pick_first():
    item = {
        "tip": "2:0",
        "expected_points": 2.031,
        "top_alternatives": [
            {"score": "3:0", "expected_points": 1.989},
            {"score": "3:1", "expected_points": 1.97},
            {"score": "1:0", "expected_points": 1.961},
        ],
    }
    rows = build_ev_alternatives_display(item)
    assert len(rows) == 4
    assert rows[0]["is_pick"] is True
    assert rows[0]["score"] == "2 : 0"
    assert rows[1]["score"] == "3 : 0"


def test_enrich_match_adds_blowout_badge_and_ev_alternatives():
    match = _enrich_match(
        {
            "tip": "2:0",
            "expected_points": 2.03,
            "most_likely_score": "2:0",
            "market_probs": {"home": 0.7, "draw": 0.15, "away": 0.15},
            "odds_1x2": {"home": 1.15, "draw": 8.0, "away": 21.0},
            "odds_ou25": {"over": 1.45, "under": 2.8},
            "top_scores": [{"score": "2:0", "probability": 0.2}],
        }
    )
    assert match["is_blowout"] is True
    assert any(badge["slug"] == "blowout" for badge in match["badges"])
    assert len(match["ev_alternatives_display"]) == 4
    assert match["ev_alternatives_display"][0]["is_pick"] is True


def test_build_badges_no_blowout_for_narrow_win():
    badges = _build_badges(
        {"tip": "1:0", "has_odds": True},
        max_prob=0.5,
    )
    assert not any(badge["slug"] == "blowout" for badge in badges)
