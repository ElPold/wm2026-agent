import json
from pathlib import Path

from src.site.generator import build_site

ROOT = Path(__file__).resolve().parents[1]


def test_build_site_from_predictions(tmp_path):
    state = tmp_path / "state"
    history = state / "history"
    docs = tmp_path / "docs"
    history.mkdir(parents=True)

    payload = {
        "generated_at": "2026-06-09T18:29:46+02:00",
        "match_count": 1,
        "predictions": [
            {
                "fixture_id": "wc26-001",
                "home_team": "Mexico",
                "away_team": "South Africa",
                "kickoff_berlin": "2026-06-11T21:00:00+02:00",
                "venue": "Mexico City",
                "round": "Matchday 1",
                "bookmaker": "pinnacle",
                "tip": "1:0",
                "expected_points": 1.79,
                "most_likely_score": "1:0",
                "market_probs": {
                    "home": 0.68,
                    "draw": 0.21,
                    "away": 0.11,
                },
                "top_scores": [
                    {"score": "1:0", "probability": 0.16},
                ],
            }
        ],
    }

    predictions_path = state / "predictions.json"
    with predictions_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle)

    index_path = build_site(
        predictions_path=predictions_path,
        history_dir=history,
        output_dir=docs,
    )

    html = index_path.read_text(encoding="utf-8")
    assert "Mexico" in html
    assert "1 : 0" in html
    assert "WM 2026 Agent" in html
    assert "catify-btn" in html
    assert "Why this works" in html
    assert "Parameter reference" in html
    assert "Update matchday" in html
    assert 'id="update-btn"' in html
    assert "data-update-url" in html
    assert 'id="update-gate"' in html
    assert 'class="matchup"' in html
    assert "day-tab" in html
    assert "match-list" in html
    assert "Matchday 1" in html
    assert "Transfer to Kicktipp" in html
    assert "data-kicktipp-btn" in html
    assert "kicktipp-spieltag-1.yml" in html
    assert "Kicktipp Spieltag" in html
    assert "Top EV alternatives" in html
    assert "ev-alternatives" in html

    # Test with multiple round archives
    rounds_dir = history / "rounds"
    rounds_dir.mkdir(parents=True)
    for md in ("Matchday 2", "Matchday 3"):
        with (rounds_dir / f"{md.lower().replace(' ', '-')}.json").open("w") as handle:
            json.dump({"round": md, "generated_at": payload["generated_at"], "match_count": 0, "predictions": []}, handle)

    build_site(
        predictions_path=predictions_path,
        history_dir=history,
        output_dir=docs,
    )
    html_multi = index_path.read_text(encoding="utf-8")
    assert html_multi.count('class="day-tab') >= 5
    assert (docs / "track.html").exists()
    assert (docs / "pipeline.html").exists()
    assert (docs / "bonus.html").exists()
    assert "flagcdn.com" in html or "team-flag" in html
    assert (docs / "static" / "style.css").exists()
    assert (docs / ".nojekyll").exists()
