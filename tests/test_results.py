import json
from pathlib import Path

from src.pipeline.results import (
    build_fixture_index,
    kicktipp_rows_to_results,
    merge_results,
    parse_result_score,
    save_results,
)
from src.sources.models import MatchFixture
from datetime import datetime, timezone
from zoneinfo import ZoneInfo


def _fixture(home: str, away: str, fixture_id: str) -> MatchFixture:
    berlin = ZoneInfo("Europe/Berlin")
    kickoff = datetime(2026, 6, 11, 21, 0, tzinfo=berlin)
    return MatchFixture(
        fixture_id=fixture_id,
        home_team=home,
        away_team=away,
        kickoff_utc=kickoff.astimezone(timezone.utc),
        kickoff_berlin=kickoff,
        venue="Test",
        round_name="Matchday 1",
        source="openfootball",
    )


def test_parse_result_score():
    assert parse_result_score("2:1") == (2, 1)
    assert parse_result_score(" 3 : 0 ") == (3, 0)
    assert parse_result_score("-:-") is None
    assert parse_result_score("") is None


def test_kicktipp_rows_to_results_with_aliases():
    aliases = {
        "Mexico": "Mexiko",
        "South Africa": "Südafrika",
    }
    fixtures = [_fixture("Mexico", "South Africa", "wc26-001")]
    index = build_fixture_index(fixtures, aliases)
    rows = [
        {
            "date": "11.06. 21:00",
            "home": "Mexiko",
            "away": "Südafrika",
            "result": "2:0",
        },
        {
            "date": "12.06. 03:00",
            "home": "Südkorea",
            "away": "Tschechien",
            "result": "-:-",
        },
    ]
    results = kicktipp_rows_to_results(rows, index)
    assert results == {
        "wc26-001": {
            "home": 2,
            "away": 0,
            "score": "2:0",
            "source": "kicktipp",
            "kicktipp_home": "Mexiko",
            "kicktipp_away": "Südafrika",
            "date": "11.06. 21:00",
        }
    }


def test_merge_results_keeps_existing():
    existing = {"wc26-001": {"home": 1, "away": 0, "score": "1:0"}}
    incoming = {"wc26-002": {"home": 3, "away": 1, "score": "3:1"}}
    merged = merge_results(existing, incoming)
    assert merged["wc26-001"]["score"] == "1:0"
    assert merged["wc26-002"]["score"] == "3:1"


def test_save_results_writes_wrapper(tmp_path: Path):
    path = tmp_path / "results.json"
    save_results(path, {"wc26-001": {"home": 2, "away": 1, "score": "2:1"}})
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["results"]["wc26-001"]["score"] == "2:1"
    assert "updated_at" in payload
