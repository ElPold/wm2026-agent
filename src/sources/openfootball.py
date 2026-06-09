"""Spielplan aus openfootball/worldcup.json (lokal, kein API-Key)."""

from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from .config import Settings
from .models import MatchFixture
from .team_names import is_tippable_match

OPENFOOTBALL_URL = (
    "https://raw.githubusercontent.com/openfootball/worldcup.json/master/2026/worldcup.json"
)


class OpenFootballSchedule:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.schedule_path = settings.schedule_path
        self._berlin = ZoneInfo(settings.timezone)

    def load_all(self) -> list[MatchFixture]:
        payload = self._read_schedule()
        fixtures: list[MatchFixture] = []

        for index, match in enumerate(payload.get("matches", []), start=1):
            home = str(match.get("team1", ""))
            away = str(match.get("team2", ""))
            kickoff_utc = parse_openfootball_kickoff(
                str(match["date"]),
                str(match.get("time", "12:00 UTC+0")),
            )
            match_num = match.get("num", index)

            fixtures.append(
                MatchFixture(
                    fixture_id=f"wc26-{int(match_num):03d}",
                    home_team=home,
                    away_team=away,
                    kickoff_utc=kickoff_utc,
                    kickoff_berlin=kickoff_utc.astimezone(self._berlin),
                    venue=match.get("ground"),
                    round_name=match.get("round") or match.get("group"),
                    source="openfootball",
                )
            )

        return fixtures

    def get_fixtures_for_date(self, day: date) -> list[MatchFixture]:
        return [
            fixture
            for fixture in self.load_all()
            if fixture.kickoff_berlin.date() == day
            and is_tippable_match(fixture.home_team, fixture.away_team)
        ]

    def _read_schedule(self) -> dict:
        if not self.schedule_path.exists():
            raise FileNotFoundError(
                f"Spielplan fehlt: {self.schedule_path}\n"
                f"Nutze: python scripts/fetch_schedule.py"
            )
        with self.schedule_path.open(encoding="utf-8") as handle:
            return json.load(handle)


def parse_openfootball_kickoff(date_str: str, time_str: str) -> datetime:
    """
    Parst openfootball-Zeitangaben wie '13:00 UTC-6' oder '20:00 UTC+0'.

    Returns UTC datetime.
    """
    match = re.match(
        r"(\d{1,2}):(\d{2})\s+UTC([+-]?\d+(?:\.\d+)?)",
        time_str.strip(),
        re.IGNORECASE,
    )
    if not match:
        hour, minute = 12, 0
        offset_hours = 0.0
    else:
        hour = int(match.group(1))
        minute = int(match.group(2))
        offset_hours = float(match.group(3))

    offset = timedelta(hours=offset_hours)
    venue_tz = timezone(offset)
    local_dt = datetime.strptime(date_str, "%Y-%m-%d").replace(
        hour=hour,
        minute=minute,
        tzinfo=venue_tz,
    )
    return local_dt.astimezone(timezone.utc)
