#!/usr/bin/env python3
"""Funktionsnachweis: Quoten → Wahrscheinlichkeiten → Poisson → EV-optimaler Tipp."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from src.model.calibration import calibrate_poisson_to_market
from src.model.odds import parse_market_odds
from src.model.poisson import top_scores
from src.optimizer.ev import compare_tip_vs_naive, find_optimal_tip


def load_example_match() -> dict:
    path = ROOT / "data" / "example_match.json"
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def main() -> None:
    match = load_example_match()
    market = parse_market_odds(match["odds_1x2"], match["odds_ou25"])
    calibration = calibrate_poisson_to_market(market)
    recommendation = find_optimal_tip(calibration.distribution)
    comparison = compare_tip_vs_naive(calibration.distribution)

    print("=" * 60)
    print("WM 2026 Kicktipp-Agent — Pipeline-Demo")
    print("=" * 60)
    print(f"Spiel: {match['home_team']} vs. {match['away_team']}")
    print(f"Anstoß (Berlin): {match['kickoff_berlin']}")
    print()

    print("Markt (margenbereinigt):")
    for key, value in market.items():
        print(f"  {key:10s}: {value:6.1%}")
    print()

    print("Poisson-Kalibrierung:")
    print(f"  λ_home = {calibration.lambda_home:.3f}")
    print(f"  λ_away = {calibration.lambda_away:.3f}")
    print(f"  Fit-Fehler (MSE): {calibration.fit_error:.6f}")
    print()

    print("Top-5 wahrscheinlichste Ergebnisse:")
    for (h, a), prob in top_scores(calibration.distribution, n=5):
        print(f"  {h}:{a}  →  {prob:6.1%}")
    print()

    print("Tipp-Empfehlung:")
    print(
        f"  EV-optimal:  {recommendation.tip_home}:{recommendation.tip_away}  "
        f"(EV = {recommendation.expected_points:.3f} Punkte)"
    )
    ml_h, ml_a = recommendation.most_likely_score
    print(
        f"  Wahrscheinl.:  {ml_h}:{ml_a}  "
        f"(p = {recommendation.most_likely_prob:.1%}, "
        f"EV = {comparison['most_likely_ev']:.3f})"
    )
    print(f"  EV-Vorteil:    +{comparison['ev_gain']:.3f} Punkte vs. Bauchtipp")
    print()

    print("Alternative Tipps (nach EV):")
    for (h, a), ev in recommendation.top_alternatives:
        print(f"  {h}:{a}  →  EV {ev:.3f}")


if __name__ == "__main__":
    main()
