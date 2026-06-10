"""Hilfsfunktionen für Tipp-Metadaten (Alternativen, Blowout)."""

from __future__ import annotations

from typing import Any

from src.model.calibration import calibrate_poisson_to_market
from src.model.odds import parse_market_odds
from src.optimizer.ev import TipRecommendation, find_optimal_tip

Score = tuple[int, int]


def parse_tip_scores(tip: str | None) -> Score | None:
    if not tip or tip == "—" or ":" not in tip:
        return None
    home, away = tip.split(":", 1)
    try:
        return int(home.strip()), int(away.strip())
    except ValueError:
        return None


def is_blowout_tip(home: int, away: int) -> bool:
    return (home, away) not in ((1, 0), (0, 1))


def recommendation_from_stored_odds(
    odds_1x2: dict[str, float],
    odds_ou25: dict[str, float],
) -> TipRecommendation:
    market = parse_market_odds(odds_1x2, odds_ou25)
    calibration = calibrate_poisson_to_market(market)
    return find_optimal_tip(calibration.distribution)


def top_alternatives_to_json(
    alternatives: list[tuple[Score, float]],
) -> list[dict[str, Any]]:
    return [
        {"score": f"{home}:{away}", "expected_points": round(ev, 4)}
        for (home, away), ev in alternatives
    ]


def ensure_top_alternatives(item: dict[str, Any]) -> list[dict[str, Any]]:
    """Lädt oder berechnet top_alternatives für einen Prediction-Eintrag."""
    stored = item.get("top_alternatives")
    if stored:
        return stored

    odds_1x2 = item.get("odds_1x2")
    odds_ou25 = item.get("odds_ou25")
    if not odds_1x2 or not odds_ou25:
        return []

    recommendation = recommendation_from_stored_odds(odds_1x2, odds_ou25)
    return top_alternatives_to_json(recommendation.top_alternatives)


def build_ev_alternatives_display(item: dict[str, Any]) -> list[dict[str, Any]]:
    """Zeile 1 = gewählter Tipp, Zeilen 2–4 = nächstbeste EV-Alternativen."""
    tip_scores = parse_tip_scores(item.get("tip"))
    if tip_scores is None:
        return []

    alternatives = ensure_top_alternatives(item)
    rows: list[dict[str, Any]] = [
        {
            "score": _format_score_display(tip_scores),
            "expected_points": float(item.get("expected_points", 0)),
            "is_pick": True,
        }
    ]
    for alt in alternatives[:3]:
        rows.append(
            {
                "score": _format_score_display(parse_tip_scores(alt["score"]) or (0, 0)),
                "expected_points": float(alt["expected_points"]),
                "is_pick": False,
            }
        )
    return rows


def _format_score_display(scores: Score) -> str:
    return f"{scores[0]} : {scores[1]}"
