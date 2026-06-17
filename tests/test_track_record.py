"""Track record: Ergebnisse aus state/results.json in track.html."""

import json
from pathlib import Path

from src.site.generator import build_site


ROOT = Path(__file__).resolve().parents[1]


def test_track_page_shows_locked_agent_tips(tmp_path):
    state = tmp_path / "state"
    history = state / "history" / "rounds"
    docs = tmp_path / "docs"
    history.mkdir(parents=True)

    payload = {
        "round": "Matchday 1",
        "generated_at": "2026-06-09T18:29:46+02:00",
        "match_count": 2,
        "predictions": [
            {
                "fixture_id": "wc26-001",
                "home_team": "Mexico",
                "away_team": "South Africa",
                "kickoff_berlin": "2026-06-11T21:00:00+02:00",
                "round": "Matchday 1",
                "tip": "1:0",
            },
            {
                "fixture_id": "wc26-002",
                "home_team": "South Korea",
                "away_team": "Czech Republic",
                "kickoff_berlin": "2026-06-12T04:00:00+02:00",
                "round": "Matchday 1",
                "tip": "2:1",
            },
        ],
    }
    (state / "predictions.json").write_text(
        json.dumps({"predictions": [{"fixture_id": "wc26-001", "pending": True}]}, ensure_ascii=False),
        encoding="utf-8",
    )
    (history / "matchday-1.json").write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )
    (state / "results.json").write_text(
        json.dumps(
            {
                "updated_at": "2026-06-13T10:00:00+00:00",
                "source": "kicktipp",
                "results": {
                    "wc26-001": {"home": 2, "away": 0, "score": "2:0"},
                    "wc26-002": {"home": 2, "away": 1, "score": "2:1"},
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    schedule_src = ROOT / "data" / "schedule" / "worldcup.json"
    schedule_dst = tmp_path / "data" / "schedule" / "worldcup.json"
    schedule_dst.parent.mkdir(parents=True)
    schedule_dst.write_text(schedule_src.read_text(encoding="utf-8"), encoding="utf-8")

    import os

    os.environ["SCHEDULE_PATH"] = str(schedule_dst)

    build_site(
        predictions_path=state / "predictions.json",
        history_dir=state / "history",
        results_path=state / "results.json",
        output_dir=docs,
        version_path=state / "site_version.json",
        increment_version=False,
    )

    track_html = (docs / "track.html").read_text(encoding="utf-8")
    assert "1 : 0" in track_html
    assert "2 : 1" in track_html


def test_track_page_shows_result_and_points(tmp_path):
    state = tmp_path / "state"
    history = state / "history" / "rounds"
    docs = tmp_path / "docs"
    history.mkdir(parents=True)

    predictions = {
        "generated_at": "2026-06-09T18:29:46+02:00",
        "match_count": 1,
        "predictions": [
            {
                "fixture_id": "wc26-001",
                "home_team": "Mexico",
                "away_team": "South Africa",
                "kickoff_berlin": "2026-06-11T21:00:00+02:00",
                "round": "Matchday 1",
                "tip": "1:0",
                "expected_points": 1.79,
            }
        ],
    }
    (state / "predictions.json").write_text(
        json.dumps(predictions, ensure_ascii=False),
        encoding="utf-8",
    )
    (history / "matchday-1.json").write_text(
        json.dumps(predictions, ensure_ascii=False),
        encoding="utf-8",
    )
    (state / "results.json").write_text(
        json.dumps(
            {
                "updated_at": "2026-06-12T10:00:00+00:00",
                "source": "kicktipp",
                "results": {
                    "wc26-001": {"home": 2, "away": 0, "score": "2:0"},
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    schedule_src = ROOT / "data" / "schedule" / "worldcup.json"
    schedule_dst = tmp_path / "data" / "schedule" / "worldcup.json"
    schedule_dst.parent.mkdir(parents=True)
    schedule_dst.write_text(schedule_src.read_text(encoding="utf-8"), encoding="utf-8")

    import os

    os.environ["SCHEDULE_PATH"] = str(schedule_dst)

    build_site(
        predictions_path=state / "predictions.json",
        history_dir=state / "history",
        results_path=state / "results.json",
        output_dir=docs,
        version_path=state / "site_version.json",
        increment_version=False,
    )

    track_html = (docs / "track.html").read_text(encoding="utf-8")
    assert "2 : 0" in track_html
    assert "track-row-scored" in track_html
    assert ">2<" in track_html
    assert "track-row-summary" in track_html
    assert "Total points" in track_html
