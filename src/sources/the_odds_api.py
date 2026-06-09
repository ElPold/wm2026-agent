"""The Odds API — Fallback für Wettquoten."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

from .config import Settings
from .http_client import HttpClient
from .models import MarketOdds, MatchFixture

logger = logging.getLogger(__name__)

PREFERRED_BOOKMAKERS = ("pinnacle", "betfair", "betfair_ex_eu", "unibet_eu")


class TheOddsApiClient:
    def __init__(self, settings: Settings, http: HttpClient | None = None) -> None:
        if not settings.has_the_odds_api():
            raise ValueError("THE_ODDS_API_KEY fehlt")
        self.settings = settings
        self.http = http or HttpClient(min_interval_sec=1.0)

    def _get(self, path: str, **params: Any) -> Any:
        url = f"{self.settings.the_odds_api_base_url}/{path.lstrip('/')}"
        query = {"apiKey": self.settings.the_odds_api_key, **params}
        return self.http.get_json(url, params=query)

    def get_odds(self) -> list[dict[str, Any]]:
        return self._get(
            f"sports/{self.settings.the_odds_api_sport}/odds",
            regions=self.settings.the_odds_api_region,
            markets="h2h,totals",
            oddsFormat="decimal",
        )

    def event_to_match(self, event: dict[str, Any]) -> MatchFixture:
        kickoff_utc = _parse_utc(event["commence_time"])
        berlin = ZoneInfo(self.settings.timezone)
        return MatchFixture(
            fixture_id=str(event["id"]),
            home_team=str(event["home_team"]),
            away_team=str(event["away_team"]),
            kickoff_utc=kickoff_utc,
            kickoff_berlin=kickoff_utc.astimezone(berlin),
            source="oddspapi",
        )


def parse_event_odds(event: dict[str, Any]) -> MarketOdds | None:
    bookmakers = event.get("bookmakers", [])
    if not bookmakers:
        return None

    bookmaker = _select_bookmaker(bookmakers)
    odds_1x2: dict[str, float] = {}
    odds_ou25: dict[str, float] = {}
    home = event.get("home_team", "")
    away = event.get("away_team", "")

    for market in bookmaker.get("markets", []):
        key = market.get("key")
        if key == "h2h":
            for outcome in market.get("outcomes", []):
                name = outcome.get("name", "")
                price = float(outcome["price"])
                if name == home:
                    odds_1x2["home"] = price
                elif name == away:
                    odds_1x2["away"] = price
                elif name.lower() == "draw":
                    odds_1x2["draw"] = price
        elif key == "totals":
            for outcome in market.get("outcomes", []):
                point = outcome.get("point")
                if point is not None and float(point) != 2.5:
                    continue
                name = outcome.get("name", "").lower()
                price = float(outcome["price"])
                if name == "over":
                    odds_ou25["over"] = price
                elif name == "under":
                    odds_ou25["under"] = price

    if len(odds_1x2) != 3 or len(odds_ou25) != 2:
        return None

    return MarketOdds(
        home=odds_1x2["home"],
        draw=odds_1x2["draw"],
        away=odds_1x2["away"],
        over_2_5=odds_ou25["over"],
        under_2_5=odds_ou25["under"],
        source="the_odds_api",
        bookmaker=bookmaker.get("key", "unknown"),
    )


def _select_bookmaker(bookmakers: list[dict[str, Any]]) -> dict[str, Any]:
    by_key = {bm["key"]: bm for bm in bookmakers}
    for preferred in PREFERRED_BOOKMAKERS:
        if preferred in by_key:
            return by_key[preferred]
    return bookmakers[0]


def _parse_utc(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)
