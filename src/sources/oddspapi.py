"""OddsPapi-Client (v4) für Wettquoten."""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

from .config import Settings
from .http_client import HttpClient
from .models import MarketOdds, MatchFixture

logger = logging.getLogger(__name__)

OUTCOME_HOME = {"1", "home"}
OUTCOME_DRAW = {"x", "draw"}
OUTCOME_AWAY = {"2", "away"}


class OddsPapiClient:
    def __init__(self, settings: Settings, http: HttpClient | None = None) -> None:
        if not settings.has_oddspapi():
            raise ValueError("ODDSPAPI_API_KEY fehlt")
        self.settings = settings
        self.http = http or HttpClient(min_interval_sec=1.0)

    def _get(self, path: str, **params: Any) -> Any:
        url = f"{self.settings.oddspapi_base_url}/{path.lstrip('/')}"
        query = {"apiKey": self.settings.oddspapi_api_key, **params}
        return self.http.get_json(url, params=query)

    def list_tournaments(self, sport_id: int | None = None) -> list[dict[str, Any]]:
        sport = sport_id or self.settings.oddspapi_sport_id
        data = self._get("tournaments", sportId=sport)
        return data if isinstance(data, list) else data.get("tournaments", data)

    def find_world_cup_tournament_id(self) -> int | None:
        """Findet die WM-Nationalmannschaften-ID (nicht Club/Quali/Virtual)."""
        candidates: list[tuple[int, int, str]] = []

        for tournament in self.list_tournaments():
            name = str(tournament.get("tournamentName", "")).lower()
            slug = str(tournament.get("tournamentSlug", "")).lower()
            tid = int(tournament["tournamentId"])

            if _is_excluded_tournament(name, slug):
                continue
            if not _is_national_world_cup_candidate(name, slug):
                continue

            score = _score_world_cup_candidate(name, slug, tournament)
            candidates.append((score, tid, name))

        if not candidates:
            return None

        candidates.sort(reverse=True)
        return candidates[0][1]

    def get_odds_by_tournament(
        self,
        tournament_id: int | None = None,
        bookmaker: str | None = None,
    ) -> list[dict[str, Any]]:
        tournament = tournament_id or self.settings.oddspapi_tournament_id
        if tournament is None:
            raise ValueError(
                "ODDSPAPI_TOURNAMENT_ID fehlt — nutze scripts/discover_ids.py"
            )

        data = self._get(
            "odds-by-tournaments",
            tournamentIds=str(tournament),
            bookmakers=bookmaker or self.settings.oddspapi_bookmaker,
            oddsFormat="decimal",
            verbosity=3,
        )
        if isinstance(data, list):
            return data
        return [data]

    def get_fixture_odds(self, fixture_id: str, bookmaker: str | None = None) -> dict:
        return self._get(
            "odds",
            fixtureId=fixture_id,
            bookmakers=bookmaker or self.settings.oddspapi_bookmaker,
            oddsFormat="decimal",
            verbosity=3,
        )

    def fixture_to_match(self, fixture: dict[str, Any]) -> MatchFixture:
        kickoff_utc = _parse_utc(fixture["startTime"])
        berlin = ZoneInfo(self.settings.timezone)
        return MatchFixture(
            fixture_id=str(fixture["fixtureId"]),
            home_team=str(fixture.get("participant1Name", "")),
            away_team=str(fixture.get("participant2Name", "")),
            kickoff_utc=kickoff_utc,
            kickoff_berlin=kickoff_utc.astimezone(berlin),
            source="oddspapi",
        )


def parse_bookmaker_odds(
    fixture: dict[str, Any],
    bookmaker: str = "pinnacle",
) -> MarketOdds | None:
    """Extrahiert 1X2 + O/U 2.5 aus einer OddsPapi-Fixture."""
    bookmakers = fixture.get("bookmakerOdds", {})
    if bookmaker not in bookmakers:
        for fallback in ("pinnacle", "betfair-ex", "betfair"):
            if fallback in bookmakers:
                bookmaker = fallback
                break
        else:
            if not bookmakers:
                return None
            bookmaker = next(iter(bookmakers))

    markets = bookmakers[bookmaker].get("markets", {})
    odds_1x2: dict[str, float] = {}
    odds_ou25: dict[str, float] = {}

    for market in markets.values():
        for outcome in market.get("outcomes", {}).values():
            for player in outcome.get("players", {}).values():
                if not player.get("active", True):
                    continue
                price = player.get("price")
                if not price or price <= 1.0:
                    continue

                label = str(player.get("bookmakerOutcomeId", "")).strip().lower()
                _assign_1x2(label, float(price), odds_1x2)
                _assign_ou25(label, float(price), bool(player.get("mainLine")), odds_ou25)

    if len(odds_1x2) != 3 or len(odds_ou25) != 2:
        logger.debug(
            "Unvollständige OddsPapi-Quoten (%s): 1x2=%s ou25=%s",
            bookmaker,
            odds_1x2,
            odds_ou25,
        )
        return None

    return MarketOdds(
        home=odds_1x2["home"],
        draw=odds_1x2["draw"],
        away=odds_1x2["away"],
        over_2_5=odds_ou25["over"],
        under_2_5=odds_ou25["under"],
        source="oddspapi",
        bookmaker=bookmaker,
    )


def _assign_1x2(label: str, price: float, odds_1x2: dict[str, float]) -> None:
    if label in OUTCOME_HOME:
        odds_1x2["home"] = price
    elif label in OUTCOME_DRAW:
        odds_1x2["draw"] = price
    elif label in OUTCOME_AWAY:
        odds_1x2["away"] = price


def _assign_ou25(
    label: str,
    price: float,
    main_line: bool,
    odds_ou25: dict[str, float],
) -> None:
    if not re.search(r"2\.5", label):
        return
    if "over" in label and ("over" not in odds_ou25 or main_line):
        odds_ou25["over"] = price
    elif "under" in label and ("under" not in odds_ou25 or main_line):
        odds_ou25["under"] = price


_EXCLUDED_SLUG_PARTS = (
    "club",
    "qualification",
    "qualifiers",
    "women",
    "u17",
    "u20",
    "u19",
    "virtual",
    "srl",
    "influencer",
    "kings",
    "novelties",
    "youth",
    "intercontinental",
    "nations-league",
)


def _is_excluded_tournament(name: str, slug: str) -> bool:
    blob = f"{name} {slug}"
    return any(part in blob for part in _EXCLUDED_SLUG_PARTS)


def _is_national_world_cup_candidate(name: str, slug: str) -> bool:
    if slug in {"world-cup", "fifa-world-cup"}:
        return True
    if name in {"world cup", "fifa world cup"}:
        return True
    return "world cup" in name and "fifa" in name and "club" not in name


def _score_world_cup_candidate(name: str, slug: str, tournament: dict[str, Any]) -> int:
    score = 0
    if slug == "world-cup":
        score += 100
    if slug == "fifa-world-cup":
        score += 90
    if name == "world cup":
        score += 80
    score += int(tournament.get("futureFixtures", 0) or 0)
    score += int(tournament.get("upcomingFixtures", 0) or 0)
    return score


def _parse_utc(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)
