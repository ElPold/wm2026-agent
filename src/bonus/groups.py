"""Gruppenphase A–L aus openfootball-Spielplan."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.sources.config import Settings

GROUP_ORDER = tuple(f"Group {letter}" for letter in "ABCDEFGHIJKL")


def load_group_teams(schedule_path: Path | None = None) -> dict[str, list[str]]:
    schedule_path = schedule_path or Settings.load().schedule_path
    with schedule_path.open(encoding="utf-8") as handle:
        payload = json.load(handle)

    teams_by_group: dict[str, set[str]] = {name: set() for name in GROUP_ORDER}
    for match in payload.get("matches", []):
        group = str(match.get("group", ""))
        if group not in teams_by_group:
            continue
        teams_by_group[group].add(str(match["team1"]))
        teams_by_group[group].add(str(match["team2"]))

    return {
        group: sorted(teams_by_group[group])
        for group in GROUP_ORDER
        if teams_by_group[group]
    }


def group_letter(group_name: str) -> str:
    return group_name.replace("Group ", "").strip()


def fixture_group_map(schedule_path: Path | None = None) -> dict[str, str]:
    schedule_path = schedule_path or Settings.load().schedule_path
    with schedule_path.open(encoding="utf-8") as handle:
        payload = json.load(handle)

    mapping: dict[str, str] = {}
    for index, match in enumerate(payload.get("matches", []), start=1):
        group = str(match.get("group", ""))
        if not group.startswith("Group "):
            continue
        match_num = int(match.get("num", index))
        mapping[f"wc26-{match_num:03d}"] = group
    return mapping
