"""Runden aus dem openfootball-Spielplan (Gruppe + K.-o.)."""

from __future__ import annotations

import re

from src.sources.config import Settings
from src.sources.openfootball import OpenFootballSchedule
from src.sources.team_names import is_tippable_match


def round_sort_key(round_name: str) -> tuple:
    match = re.search(r"Matchday\s+(\d+)", round_name, re.IGNORECASE)
    if match:
        return (0, int(match.group(1)))

    order = {
        "Round of 32": (1, 0),
        "Round of 16": (1, 1),
        "Quarter-final": (1, 2),
        "Semi-final": (1, 3),
        "Match for third place": (1, 4),
        "Final": (1, 5),
    }
    if round_name in order:
        return order[round_name]
    return (2, round_name.lower())


def schedule_round_names(settings: Settings | None = None) -> list[str]:
    """Alle tippbaren Runden aus dem Spielplan, chronologisch sortiert."""
    settings = settings or Settings.load()
    rounds: set[str] = set()
    for fixture in OpenFootballSchedule(settings).load_all():
        if not fixture.round_name:
            continue
        if not is_tippable_match(fixture.home_team, fixture.away_team):
            continue
        rounds.add(fixture.round_name)
    return sorted(rounds, key=round_sort_key)
