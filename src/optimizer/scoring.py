"""Kicktipp-Punktesystem (2/3/4-Schema)."""

from __future__ import annotations


def kicktipp_points(
    tip_home: int,
    tip_away: int,
    actual_home: int,
    actual_away: int,
) -> int:
    """
    Punkte für einen Tipp gegen ein tatsächliches Ergebnis.

    Schema:
      - Sieg/Niederlage: Tendenz 2, Tordifferenz 3, exakt 4
      - Unentschieden: Tendenz 2, exakt 4 (keine Tordifferenz-Stufe)
    """
    if tip_home == actual_home and tip_away == actual_away:
        return 4

    tip_is_draw = tip_home == tip_away
    actual_is_draw = actual_home == actual_away

    if actual_is_draw:
        return 2 if tip_is_draw else 0

    if tip_is_draw:
        return 0

    tip_winner = "home" if tip_home > tip_away else "away"
    actual_winner = "home" if actual_home > actual_away else "away"

    if tip_winner != actual_winner:
        return 0

    tip_diff = abs(tip_home - tip_away)
    actual_diff = abs(actual_home - actual_away)

    if tip_diff == actual_diff:
        return 3

    return 2
