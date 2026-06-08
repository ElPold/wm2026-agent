"""Wettquoten in margenbereinigte Wahrscheinlichkeiten umwandeln."""

from __future__ import annotations

from typing import Dict, Mapping


def implied_probability(odds: float) -> float:
    """Einzelne Quote in implizite Wahrscheinlichkeit (ohne Marge-Bereinigung)."""
    if odds <= 1.0:
        raise ValueError(f"Ungültige Quote: {odds}")
    return 1.0 / odds


def remove_overround(probabilities: Mapping[str, float]) -> Dict[str, float]:
    """Normiert Wahrscheinlichkeiten auf 100 % (Overround entfernen)."""
    total = sum(probabilities.values())
    if total <= 0:
        raise ValueError("Summe der Wahrscheinlichkeiten muss positiv sein")
    return {key: value / total for key, value in probabilities.items()}


def odds_to_probabilities(odds: Mapping[str, float]) -> Dict[str, float]:
    """Quotes dict → margenbereinigte Wahrscheinlichkeiten."""
    implied = {key: implied_probability(value) for key, value in odds.items()}
    return remove_overround(implied)


def parse_market_odds(
    odds_1x2: Mapping[str, float],
    odds_ou25: Mapping[str, float],
) -> Dict[str, float]:
    """
    Kombiniert 1X2- und Over/Under-2.5-Märkte zu einem Zielvektor.

    Erwartete Keys:
      1X2: home, draw, away
      O/U: over, under
    """
    probs_1x2 = odds_to_probabilities(odds_1x2)
    probs_ou = odds_to_probabilities(odds_ou25)

    return {
        "home": probs_1x2["home"],
        "draw": probs_1x2["draw"],
        "away": probs_1x2["away"],
        "over_2_5": probs_ou["over"],
        "under_2_5": probs_ou["under"],
    }
