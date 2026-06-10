"""Gemeinsame Datenmodelle für API-Quellen."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

OddsSource = Literal["oddspapi", "the_odds_api", "api_football", "manual"]


@dataclass(frozen=True)
class MarketOdds:
    home: float
    draw: float
    away: float
    over_2_5: float
    under_2_5: float
    source: OddsSource
    bookmaker: str

    def as_1x2_dict(self) -> dict[str, float]:
        return {"home": self.home, "draw": self.draw, "away": self.away}

    def as_ou25_dict(self) -> dict[str, float]:
        return {"over": self.over_2_5, "under": self.under_2_5}


@dataclass(frozen=True)
class MatchFixture:
    fixture_id: str
    home_team: str
    away_team: str
    kickoff_utc: datetime
    kickoff_berlin: datetime
    venue: str | None = None
    round_name: str | None = None
    status: str | None = None
    source: Literal["openfootball", "api_football", "oddspapi"] = "openfootball"


@dataclass
class MatchPrediction:
    fixture: MatchFixture
    odds: MarketOdds
    tip_home: int
    tip_away: int
    expected_points: float
    most_likely_score: tuple[int, int]
    lambda_home: float
    lambda_away: float
    market_probs: dict[str, float]
    top_scores: list[tuple[tuple[int, int], float]] = field(default_factory=list)
    top_alternatives: list[tuple[tuple[int, int], float]] = field(
        default_factory=list
    )
