"""Bivariates Poisson-Modell für Torergebnisse."""

from __future__ import annotations

from typing import Dict, Tuple

from scipy.stats import poisson

Score = Tuple[int, int]
Distribution = Dict[Score, float]


def poisson_score_distribution(
    lambda_home: float,
    lambda_away: float,
    max_goals: int = 6,
) -> Distribution:
    """
    P(h,a) = Poisson(h; λ_h) × Poisson(a; λ_a) für h,a ∈ [0, max_goals].

    Der verbleibende Tail (mehr als max_goals) wird auf das Raster
    umverteilt, damit die Verteilung auf 1 normiert bleibt.
    """
    if lambda_home <= 0 or lambda_away <= 0:
        raise ValueError("Lambdas müssen positiv sein")

    dist: Distribution = {}
    for home_goals in range(max_goals + 1):
        for away_goals in range(max_goals + 1):
            prob = poisson.pmf(home_goals, lambda_home) * poisson.pmf(
                away_goals, lambda_away
            )
            dist[(home_goals, away_goals)] = float(prob)

    total = sum(dist.values())
    if total <= 0:
        raise ValueError("Verteilung ist leer")

    return {score: prob / total for score, prob in dist.items()}


def outcome_probabilities(dist: Distribution) -> Dict[str, float]:
    """Leitet 1X2- und Over/Under-2.5-Wahrscheinlichkeiten aus der Verteilung ab."""
    p_home = sum(prob for (h, a), prob in dist.items() if h > a)
    p_draw = sum(prob for (h, a), prob in dist.items() if h == a)
    p_away = sum(prob for (h, a), prob in dist.items() if h < a)
    p_over = sum(prob for (h, a), prob in dist.items() if h + a >= 3)

    return {
        "home": p_home,
        "draw": p_draw,
        "away": p_away,
        "over_2_5": p_over,
        "under_2_5": 1.0 - p_over,
    }


def most_likely_score(dist: Distribution) -> Tuple[Score, float]:
    """Ergebnis mit höchster Einzelwahrscheinlichkeit."""
    score, prob = max(dist.items(), key=lambda item: item[1])
    return score, prob


def top_scores(dist: Distribution, n: int = 5) -> list[Tuple[Score, float]]:
    """Top-n Ergebnisse nach Wahrscheinlichkeit."""
    return sorted(dist.items(), key=lambda item: item[1], reverse=True)[:n]
