import json
from pathlib import Path

from src.site.generator import _current_round_id, build_site, resolve_site_version

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
                "kickoff_berlin": "2030-06-11T21:00:00+02:00",
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

    version_path = state / "site_version.json"
    sync_path = state / "sync_status.json"
    sync_path.write_text(
        json.dumps(
            {
                "predictions": {
                    "updated_at": "2026-06-16T10:00:00+02:00",
                    "rounds": 1,
                    "mode": "round",
                    "round": "Matchday 1",
                    "source": "manual",
                },
                "kicktipp": {
                    "synced_at": "2026-06-16T10:05:00+02:00",
                    "status": "ok",
                    "spieltag": 1,
                    "tips_count": 1,
                    "agent_rounds": ["Matchday 1"],
                    "mode": "manual",
                    "error": None,
                },
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    index_path = build_site(
        predictions_path=predictions_path,
        history_dir=history,
        output_dir=docs,
        version_path=version_path,
        sync_status_path=sync_path,
        increment_version=False,
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
    assert "manuell auf kicktipp.de" in html
    assert "Transfer to Kicktipp" not in html
    assert "data-kicktipp-btn" not in html
    assert "Top EV alternatives" in html
    assert "ev-alternatives" in html
    assert 'class="site-version' in html
    assert ">v" in html
    assert "sync-status" in html
    assert "manual entry only" in html
    assert "Tips updated" in html
    assert "is-current" in html
    assert "day-tab-now" in html

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
        version_path=version_path,
        increment_version=False,
    )
    html_multi = index_path.read_text(encoding="utf-8")
    assert html_multi.count('class="day-tab') >= 17
    assert "MD 1" in html_multi
    assert "MD 17" in html_multi
    assert (docs / "track.html").exists()
    assert (docs / "pipeline.html").exists()
    assert (docs / "bonus.html").exists()
    assert "flagcdn.com" in html or "team-flag" in html
    assert (docs / "static" / "style.css").exists()
    assert (docs / ".nojekyll").exists()


def test_current_round_id_picks_next_upcoming_matchday():
    rounds = [
        {
            "round_id": "matchday-1",
            "predictions": [
                {"kickoff_berlin": "2026-06-11T21:00:00+02:00", "is_locked": True},
            ],
        },
        {
            "round_id": "matchday-6",
            "predictions": [
                {"kickoff_berlin": "2026-06-17T00:00:00+02:00", "is_locked": False},
                {"kickoff_berlin": "2026-06-16T21:00:00+02:00", "is_locked": False},
            ],
        },
    ]
    from datetime import datetime
    from zoneinfo import ZoneInfo

    now = datetime(2026, 6, 16, 15, 0, tzinfo=ZoneInfo("Europe/Berlin"))
    assert _current_round_id(rounds, now=now) == "matchday-6"


def test_resolve_site_version_auto_increments(tmp_path):
    version_path = tmp_path / "site_version.json"
    assert resolve_site_version(version_path, increment=True) == 1
    assert resolve_site_version(version_path, increment=True) == 2
    assert json.loads(version_path.read_text(encoding="utf-8"))["version"] == 2
