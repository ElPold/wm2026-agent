from datetime import datetime, timezone

from src.sources.match_linker import link_fixtures
from src.sources.team_names import normalize_team_name, teams_match
from src.sources.models import MatchFixture


def _fixture(
    fixture_id: str,
    home: str,
    away: str,
    hour: int,
) -> MatchFixture:
    kickoff = datetime(2026, 6, 11, hour, 0, tzinfo=timezone.utc)
    return MatchFixture(
        fixture_id=fixture_id,
        home_team=home,
        away_team=away,
        kickoff_utc=kickoff,
        kickoff_berlin=kickoff,
    )


def test_normalize_team_name():
    assert normalize_team_name("Südafrika") == "sudafrika"


def test_teams_match_aliases():
    assert teams_match("Mexico", "mexico")
    assert teams_match("USA", "United States")
    assert teams_match("Turkey", "Turkiye")
    assert teams_match("Curaçao", "Curacao")


def test_link_fixtures_by_time_and_name():
    schedule = [_fixture("1", "Mexico", "South Africa", 18)]
    odds = [_fixture("odds-1", "Mexico", "South Africa", 18)]

    links = link_fixtures(schedule, odds)
    assert links["1"].fixture_id == "odds-1"
