"""Kalibriert Poisson-Parameter an Marktwahrscheinlichkeiten."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Mapping

import numpy as np
from scipy.optimize import minimize

from .poisson import Distribution, outcome_probabilities, poisson_score_distribution

MARKET_KEYS = ("home", "draw", "away", "over_2_5")


@dataclass(frozen=True)
class CalibrationResult:
    lambda_home: float
    lambda_away: float
    distribution: Distribution
    market_probs: Dict[str, float]
    model_probs: Dict[str, float]
    fit_error: float


def _fit_error(
    params: np.ndarray,
    target: Mapping[str, float],
    max_goals: int,
) -> float:
    lambda_home, lambda_away = float(params[0]), float(params[1])
    if lambda_home <= 0.01 or lambda_away <= 0.01:
        return 1e6

    dist = poisson_score_distribution(lambda_home, lambda_away, max_goals=max_goals)
    model = outcome_probabilities(dist)

    error = 0.0
    for key in MARKET_KEYS:
        diff = model[key] - target[key]
        error += diff * diff
    return error


def calibrate_poisson_to_market(
    market_probs: Mapping[str, float],
    max_goals: int = 6,
    initial_guess: tuple[float, float] = (1.4, 1.0),
) -> CalibrationResult:
    """
    Findet λ_h, λ_a, sodass 1X2 und O/U 2.5 möglichst gut zum Markt passen.
    """
    target = {key: float(market_probs[key]) for key in MARKET_KEYS}

    result = minimize(
        _fit_error,
        x0=np.array(initial_guess, dtype=float),
        args=(target, max_goals),
        method="L-BFGS-B",
        bounds=[(0.05, 5.0), (0.05, 5.0)],
    )

    lambda_home, lambda_away = float(result.x[0]), float(result.x[1])
    distribution = poisson_score_distribution(lambda_home, lambda_away, max_goals=max_goals)
    model_probs = outcome_probabilities(distribution)

    return CalibrationResult(
        lambda_home=lambda_home,
        lambda_away=lambda_away,
        distribution=distribution,
        market_probs=target,
        model_probs=model_probs,
        fit_error=float(result.fun),
    )
