from datetime import date, timezone
from pathlib import Path

from src.sources.config import Settings
from src.sources.openfootball import OpenFootballSchedule, parse_openfootball_kickoff

ROOT = Path(__file__).resolve().parents[1]


def test_parse_openfootball_kickoff_utc_minus_6():
    kickoff = parse_openfootball_kickoff("2026-06-11", "13:00 UTC-6")
    assert kickoff.tzinfo == timezone.utc
    assert kickoff.hour == 19
    assert kickoff.minute == 0


def test_load_schedule_has_104_matches():
    settings = Settings.load()
    settings = Settings(
        oddspapi_api_key=None,
        api_football_api_key=None,
        the_odds_api_key=None,
        schedule_path=ROOT / "data" / "schedule" / "worldcup.json",
    )
    schedule = OpenFootballSchedule(settings)
    matches = schedule.load_all()
    assert len(matches) == 104


def test_opening_day_has_group_matches():
    settings = Settings(
        oddspapi_api_key=None,
        api_football_api_key=None,
        the_odds_api_key=None,
        schedule_path=ROOT / "data" / "schedule" / "worldcup.json",
    )
    schedule = OpenFootballSchedule(settings)
    matches = schedule.get_fixtures_for_date(date(2026, 6, 11))
    assert len(matches) == 1
    assert matches[0].home_team == "Mexico"
    assert matches[0].away_team == "South Africa"
