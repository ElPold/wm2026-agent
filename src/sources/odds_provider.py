"""Vereinheitlichter Quoten-Zugriff mit Fallback-Kette."""

from __future__ import annotations

import logging
from typing import Any

from .api_football import ApiFootballClient
from .config import Settings
from .http_client import ApiError
from .match_linker import link_fixtures
from .models import MarketOdds, MatchFixture
from .oddspapi import OddsPapiClient, parse_bookmaker_odds
from .the_odds_api import TheOddsApiClient, parse_event_odds

logger = logging.getLogger(__name__)


class OddsProvider:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._oddspapi = OddsPapiClient(settings) if settings.has_oddspapi() else None
        self._the_odds = (
            TheOddsApiClient(settings) if settings.has_the_odds_api() else None
        )
        self._football = (
            ApiFootballClient(settings) if settings.has_api_football() else None
        )
        self._oddspapi_raw: list[dict[str, Any]] | None = None
        self._the_odds_events: list[dict[str, Any]] | None = None

    def fetch_odds_for_schedule(
        self,
        schedule: list[MatchFixture],
    ) -> dict[str, MarketOdds]:
        if not schedule:
            return {}

        results: dict[str, MarketOdds] = {}

        if self._oddspapi:
            try:
                results.update(self._fetch_from_oddspapi(schedule))
            except ApiError as exc:
                logger.warning(
                    "OddsPapi nicht verfügbar (%s) — Fallback auf The Odds API",
                    exc,
                )
                self._oddspapi_raw = []

        missing = [game for game in schedule if game.fixture_id not in results]
        if missing and self._the_odds:
            try:
                results.update(self._fetch_from_the_odds_api(missing))
            except ApiError as exc:
                logger.warning("The Odds API nicht verfügbar: %s", exc)

        still_missing = [game for game in schedule if game.fixture_id not in results]
        if still_missing:
            logger.warning(
                "Keine Quoten für %d/%d Spiele gefunden",
                len(still_missing),
                len(schedule),
            )

        return results

    def _oddspapi_tournament_odds(self) -> list[dict[str, Any]]:
        assert self._oddspapi is not None
        if self._oddspapi_raw is None:
            self._oddspapi_raw = self._oddspapi.get_odds_by_tournament()
        return self._oddspapi_raw

    def _the_odds_api_events(self) -> list[dict[str, Any]]:
        assert self._the_odds is not None
        if self._the_odds_events is None:
            self._the_odds_events = self._the_odds.get_odds()
        return self._the_odds_events

    def _fetch_from_oddspapi(
        self,
        schedule: list[MatchFixture],
    ) -> dict[str, MarketOdds]:
        assert self._oddspapi is not None
        raw_fixtures = self._oddspapi_tournament_odds()
        odds_matches = [self._oddspapi.fixture_to_match(item) for item in raw_fixtures]
        links = link_fixtures(schedule, odds_matches)

        by_odds_id = {str(item["fixtureId"]): item for item in raw_fixtures}
        results: dict[str, MarketOdds] = {}

        for schedule_id, odds_match in links.items():
            raw = by_odds_id.get(odds_match.fixture_id)
            if not raw:
                continue
            market = parse_bookmaker_odds(
                raw, bookmaker=self.settings.oddspapi_bookmaker
            )
            if market:
                results[schedule_id] = market

        logger.info(
            "OddsPapi: %d/%d Spiele mit Quoten",
            len(results),
            len(schedule),
        )
        return results

    def _fetch_from_the_odds_api(
        self,
        schedule: list[MatchFixture],
    ) -> dict[str, MarketOdds]:
        assert self._the_odds is not None
        events = self._the_odds_api_events()
        odds_matches = [self._the_odds.event_to_match(event) for event in events]
        links = link_fixtures(schedule, odds_matches)

        by_event_id = {str(event["id"]): event for event in events}
        results: dict[str, MarketOdds] = {}

        for schedule_id, odds_match in links.items():
            raw = by_event_id.get(odds_match.fixture_id)
            if not raw:
                continue
            market = parse_event_odds(raw)
            if market:
                results[schedule_id] = market

        logger.info(
            "The Odds API: %d/%d fehlende Spiele ergänzt",
            len(results),
            len(schedule),
        )
        return results

    def has_api_football(self) -> bool:
        return self._football is not None
