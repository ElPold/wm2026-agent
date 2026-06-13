from src.site.generator import _enrich_match, _mark_day_highlight


def test_enrich_match_marks_started_tip_as_locked():
    match = _enrich_match(
        {
            "tip": "1:0",
            "kickoff_berlin": "2026-06-11T21:00:00+02:00",
            "expected_points": 1.79,
            "market_probs": {"home": 0.68, "draw": 0.21, "away": 0.11},
            "odds_1x2": {"home": 1.4, "draw": 4.6, "away": 8.7},
        }
    )
    assert match["is_locked"] is True
    assert match["is_pending"] is False
    assert any(b["slug"] == "final" for b in match["badges"])


def test_enrich_match_adds_display_and_badges():
    match = _enrich_match(
        {
            "tip": "1:0",
            "kickoff_berlin": "2030-06-11T21:00:00+02:00",
            "expected_points": 1.79,
            "market_probs": {"home": 0.68, "draw": 0.21, "away": 0.11},
            "odds_1x2": {"home": 1.4, "draw": 4.6, "away": 8.7},
        }
    )
    assert match["tip_display"] == "1 : 0"
    assert match["confidence"] == "high"
    assert any(b["slug"] == "ev-pick" for b in match["badges"])


def test_enrich_match_backfills_ev_alternatives_without_stored_field():
    match = _enrich_match(
        {
            "tip": "1:0",
            "expected_points": 1.21,
            "most_likely_score": "1:1",
            "market_probs": {"home": 0.36, "draw": 0.44, "away": 0.2},
            "odds_1x2": {"home": 2.62, "draw": 2.17, "away": 4.66},
            "odds_ou25": {"over": 1.99, "under": 1.9},
            "top_scores": [{"score": "1:1", "probability": 0.13}],
        }
    )
    assert len(match["ev_alternatives_display"]) == 4
    assert match["ev_alternatives_display"][0]["is_pick"] is True
    assert match["is_blowout"] is False


def test_mark_day_highlight_flags_best_ev():
    picks = [
        {"fixture_id": "a", "expected_points": 1.2},
        {"fixture_id": "b", "expected_points": 1.9},
    ]
    _mark_day_highlight(picks)
    assert picks[0]["is_day_highlight"] is False
    assert picks[1]["is_day_highlight"] is True
