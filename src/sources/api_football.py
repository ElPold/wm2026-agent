"""API-Football-Client (api-sports.io) für Spielplan und Ergebnisse."""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

from .config import Settings
from .http_client import HttpClient
from .models import MatchFixture

logger = logging.getLogger(__name__)


class ApiFootballClient:
    def __init__(self, settings: Settings, http: HttpClient | None = None) -> None:
        if not settings.has_api_football():
            raise ValueError("API_FOOTBALL_API_KEY fehlt")
        self.settings = settings
        self.http = http or HttpClient(min_interval_sec=0.5)
        self._headers = {
            "x-apisports-key": settings.api_football_api_key or "",
        }

    def _get(self, path: str, **params: Any) -> dict[str, Any]:
        url = f"{self.settings.api_football_base_url}/{path.lstrip('/')}"
        payload = self.http.get_json(url, params=params, headers=self._headers)
        if not isinstance(payload, dict):
            raise ValueError(f"Unerwartete API-Football-Antwort: {type(payload)}")
        errors = payload.get("errors")
        if errors:
            logger.warning("API-Football Warnung: %s", errors)
        return payload

    def get_league_coverage(self) -> dict[str, Any]:
        payload = self._get(
            "leagues",
            id=self.settings.api_football_league_id,
            season=self.settings.api_football_season,
        )
        items = payload.get("response", [])
        return items[0] if items else {}

    def get_fixtures_for_date(self, day: date) -> list[MatchFixture]:
        payload = self._get(
            "fixtures",
            league=self.settings.api_football_league_id,
            season=self.settings.api_football_season,
            date=day.isoformat(),
            timezone=self.settings.timezone,
        )
        fixtures = []
        for item in payload.get("response", []):
            fixtures.append(self._to_match_fixture(item))
        return fixtures

    def get_all_fixtures(self) -> list[MatchFixture]:
        payload = self._get(
            "fixtures",
            league=self.settings.api_football_league_id,
            season=self.settings.api_football_season,
        )
        return [self._to_match_fixture(item) for item in payload.get("response", [])]

    def get_fixture_by_id(self, fixture_id: int) -> MatchFixture | None:
        payload = self._get("fixtures", id=fixture_id)
        items = payload.get("response", [])
        if not items:
            return None
        return self._to_match_fixture(items[0])

    def _to_match_fixture(self, item: dict[str, Any]) -> MatchFixture:
        fixture = item["fixture"]
        teams = item["teams"]
        league = item.get("league", {})
        kickoff_utc = _parse_utc(fixture["date"])
        berlin = ZoneInfo(self.settings.timezone)

        return MatchFixture(
            fixture_id=str(fixture["id"]),
            home_team=teams["home"]["name"],
            away_team=teams["away"]["name"],
            kickoff_utc=kickoff_utc,
            kickoff_berlin=kickoff_utc.astimezone(berlin),
            venue=fixture.get("venue", {}).get("name"),
            round_name=league.get("round"),
            status=fixture.get("status", {}).get("short"),
            source="api_football",
        )


def _parse_utc(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)
