"""Kicktipp-Ergebnisse laden und in state/results.json speichern."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.sources.config import ROOT, Settings
from src.sources.models import MatchFixture
from src.sources.openfootball import OpenFootballSchedule
from src.sources.team_names import is_tippable_match

RESULT_SCORE_RE = re.compile(r"^(\d+)\s*:\s*(\d+)$")


def load_aliases(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Aliases must be a JSON object: {path}")
    return {str(k): str(v) for k, v in data.items()}


def agent_team_to_kicktipp(name: str, aliases: dict[str, str]) -> str:
    return aliases.get(name, name)


def kicktipp_team_to_agent(name: str, aliases: dict[str, str]) -> str:
    for agent, kicktipp in aliases.items():
        if kicktipp == name:
            return agent
    return name


def parse_result_score(result: str | None) -> tuple[int, int] | None:
    if not result:
        return None
    cleaned = result.strip().replace(" ", "")
    if cleaned in {"-:-", "–:–", ""}:
        return None
    match = RESULT_SCORE_RE.match(cleaned)
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


def build_fixture_index(
    fixtures: list[MatchFixture],
    aliases: dict[str, str],
) -> dict[tuple[str, str], str]:
    index: dict[tuple[str, str], str] = {}
    for fixture in fixtures:
        home = agent_team_to_kicktipp(fixture.home_team, aliases)
        away = agent_team_to_kicktipp(fixture.away_team, aliases)
        index[(home, away)] = fixture.fixture_id
    return index


def kicktipp_rows_to_results(
    rows: list[dict[str, str]],
    fixture_index: dict[tuple[str, str], str],
    *,
    source: str = "kicktipp",
) -> dict[str, dict[str, Any]]:
    results: dict[str, dict[str, Any]] = {}
    for row in rows:
        scores = parse_result_score(row.get("result"))
        if not scores:
            continue
        fixture_id = fixture_index.get((row["home"], row["away"]))
        if not fixture_id:
            continue
        home, away = scores
        results[fixture_id] = {
            "home": home,
            "away": away,
            "score": f"{home}:{away}",
            "source": source,
            "kicktipp_home": row["home"],
            "kicktipp_away": row["away"],
        }
        if row.get("date"):
            results[fixture_id]["date"] = row["date"]
    return results


def load_results(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload.get("results"), dict):
        return dict(payload["results"])
    return dict(payload) if isinstance(payload, dict) else {}


def merge_results(
    existing: dict[str, dict[str, Any]],
    incoming: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    merged = dict(existing)
    for fixture_id, entry in incoming.items():
        merged[fixture_id] = {**merged.get(fixture_id, {}), **entry}
    return merged


def save_results(
    path: Path,
    results: dict[str, dict[str, Any]],
    *,
    source: str = "kicktipp",
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "results": results,
    }
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return path


def fixture_index_for_schedule(
    settings: Settings | None = None,
    aliases_path: Path | None = None,
) -> dict[tuple[str, str], str]:
    settings = settings or Settings.load()
    aliases = load_aliases(aliases_path or ROOT / "config" / "kicktipp_aliases.json")
    fixtures = [
        fixture
        for fixture in OpenFootballSchedule(settings).load_all()
        if is_tippable_match(fixture.home_team, fixture.away_team)
    ]
    return build_fixture_index(fixtures, aliases)
