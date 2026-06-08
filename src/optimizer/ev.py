"""Erwartungswert-Optimierer für punkteoptimale Tipps."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Tuple

from ..model.poisson import Distribution
from .scoring import kicktipp_points

Score = Tuple[int, int]


@dataclass(frozen=True)
class TipRecommendation:
    tip_home: int
    tip_away: int
    expected_points: float
    most_likely_score: Score
    most_likely_prob: float
    top_alternatives: list[Tuple[Score, float]]


def expected_points(
    distribution: Distribution,
    tip_home: int,
    tip_away: int,
) -> float:
    """Erwartete Punkte für einen Tipp über die Ergebnisverteilung."""
    total = 0.0
    for (home, away), prob in distribution.items():
        points = kicktipp_points(tip_home, tip_away, home, away)
        total += prob * points
    return total


def all_candidate_tips(max_goals: int = 6) -> Iterable[Score]:
    for home in range(max_goals + 1):
        for away in range(max_goals + 1):
            yield home, away


def find_optimal_tip(
    distribution: Distribution,
    max_goals: int = 6,
) -> TipRecommendation:
    """Wählt den Tipp mit dem höchsten Erwartungswert."""
    best_score: Score | None = None
    best_ev = -1.0

    for tip_home, tip_away in all_candidate_tips(max_goals):
        ev = expected_points(distribution, tip_home, tip_away)
        if ev > best_ev:
            best_ev = ev
            best_score = (tip_home, tip_away)

    if best_score is None:
        raise ValueError("Keine Tipps gefunden")

    most_likely = max(distribution.items(), key=lambda item: item[1])
    alternatives = sorted(
        (
            (score, expected_points(distribution, score[0], score[1]))
            for score in all_candidate_tips(max_goals)
        ),
        key=lambda item: item[1],
        reverse=True,
    )[1:4]

    return TipRecommendation(
        tip_home=best_score[0],
        tip_away=best_score[1],
        expected_points=best_ev,
        most_likely_score=most_likely[0],
        most_likely_prob=most_likely[1],
        top_alternatives=alternatives,
    )


def compare_tip_vs_naive(
    distribution: Distribution,
    max_goals: int = 6,
) -> Dict[str, object]:
    """Vergleicht EV-optimalen Tipp mit dem wahrscheinlichsten Ergebnis."""
    optimal = find_optimal_tip(distribution, max_goals=max_goals)
    ml_h, ml_a = optimal.most_likely_score

    return {
        "optimal_tip": (optimal.tip_home, optimal.tip_away),
        "optimal_ev": optimal.expected_points,
        "most_likely_tip": (ml_h, ml_a),
        "most_likely_ev": expected_points(distribution, ml_h, ml_a),
        "ev_gain": optimal.expected_points
        - expected_points(distribution, ml_h, ml_a),
    }
