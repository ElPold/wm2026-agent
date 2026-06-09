"""Konfiguration aus Umgebungsvariablen."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    oddspapi_api_key: str | None
    api_football_api_key: str | None
    the_odds_api_key: str | None

    oddspapi_base_url: str = "https://api.oddspapi.io/v4"
    oddspapi_sport_id: int = 10
    oddspapi_tournament_id: int | None = None
    oddspapi_bookmaker: str = "pinnacle"

    api_football_base_url: str = "https://v3.football.api-sports.io"
    api_football_league_id: int = 1
    api_football_season: int = 2026

    the_odds_api_base_url: str = "https://api.the-odds-api.com/v4"
    the_odds_api_sport: str = "soccer_fifa_world_cup"
    the_odds_api_region: str = "eu"

    timezone: str = "Europe/Berlin"
    schedule_path: Path = ROOT / "data" / "schedule" / "worldcup.json"
    cache_dir: Path = ROOT / "data" / "cache"

    @classmethod
    def load(cls, env_file: Path | None = None) -> "Settings":
        if env_file is None:
            env_file = ROOT / ".env"
        load_dotenv(env_file)

        tournament_raw = os.getenv("ODDSPAPI_TOURNAMENT_ID")
        tournament_id = int(tournament_raw) if tournament_raw else None

        return cls(
            oddspapi_api_key=os.getenv("ODDSPAPI_API_KEY"),
            api_football_api_key=os.getenv("API_FOOTBALL_API_KEY"),
            the_odds_api_key=os.getenv("THE_ODDS_API_KEY"),
            oddspapi_base_url=os.getenv(
                "ODDSPAPI_BASE_URL", "https://api.oddspapi.io/v4"
            ),
            oddspapi_sport_id=int(os.getenv("ODDSPAPI_SPORT_ID", "10")),
            oddspapi_tournament_id=tournament_id,
            oddspapi_bookmaker=os.getenv("ODDSPAPI_BOOKMAKER", "pinnacle"),
            api_football_base_url=os.getenv(
                "API_FOOTBALL_BASE_URL", "https://v3.football.api-sports.io"
            ),
            api_football_league_id=int(os.getenv("API_FOOTBALL_LEAGUE_ID", "1")),
            api_football_season=int(os.getenv("API_FOOTBALL_SEASON", "2026")),
            the_odds_api_base_url=os.getenv(
                "THE_ODDS_API_BASE_URL", "https://api.the-odds-api.com/v4"
            ),
            the_odds_api_sport=os.getenv(
                "THE_ODDS_API_SPORT", "soccer_fifa_world_cup"
            ),
            the_odds_api_region=os.getenv("THE_ODDS_API_REGION", "eu"),
            timezone=os.getenv("TIMEZONE", "Europe/Berlin"),
            schedule_path=Path(
                os.getenv(
                    "SCHEDULE_PATH",
                    str(ROOT / "data" / "schedule" / "worldcup.json"),
                )
            ),
        )

    def has_oddspapi(self) -> bool:
        return bool(self.oddspapi_api_key)

    def has_api_football(self) -> bool:
        return bool(self.api_football_api_key)

    def has_the_odds_api(self) -> bool:
        return bool(self.the_odds_api_key)
