from src.site.generator import _enrich_match, _mark_day_highlight


def test_enrich_match_adds_display_and_badges():
    match = _enrich_match(
        {
            "tip": "1:0",
            "expected_points": 1.79,
            "market_probs": {"home": 0.68, "draw": 0.21, "away": 0.11},
            "odds_1x2": {"home": 1.4, "draw": 4.6, "away": 8.7},
        }
    )
    assert match["tip_display"] == "1 : 0"
    assert match["confidence"] == "high"
    assert any(b["slug"] == "ev-pick" for b in match["badges"])


def test_mark_day_highlight_flags_best_ev():
    picks = [
        {"fixture_id": "a", "expected_points": 1.2},
        {"fixture_id": "b", "expected_points": 1.9},
    ]
    _mark_day_highlight(picks)
    assert picks[0]["is_day_highlight"] is False
    assert picks[1]["is_day_highlight"] is True
