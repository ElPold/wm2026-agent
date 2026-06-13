"""Laden und Zusammenführen archivierter Vorhersagen."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from src.sources.config import ROOT

BERLIN = ZoneInfo("Europe/Berlin")


def collect_payloads(
    history_dir: Path | None = None,
    predictions_path: Path | None = None,
) -> list[dict[str, Any]]:
    history_dir = history_dir or ROOT / "state" / "history"
    predictions_path = predictions_path or ROOT / "state" / "predictions.json"
    payloads: list[dict[str, Any]] = []

    rounds_dir = history_dir / "rounds"
    if rounds_dir.exists():
        for path in sorted(rounds_dir.glob("*.json")):
            payloads.append(_read_json(path))

    if history_dir.exists():
        for path in sorted(history_dir.glob("*.json")):
            payloads.append(_read_json(path))

    if predictions_path.exists():
        payloads.append(_read_json(predictions_path))

    return payloads


def is_fixture_started(kickoff_berlin: str | None, *, now: datetime | None = None) -> bool:
    if not kickoff_berlin:
        return False
    now = now or datetime.now(tz=BERLIN)
    try:
        kickoff = datetime.fromisoformat(kickoff_berlin)
        if kickoff.tzinfo is None:
            kickoff = kickoff.replace(tzinfo=BERLIN)
        return kickoff <= now
    except ValueError:
        return False


def should_replace_prediction(
    existing: dict[str, Any],
    incoming: dict[str, Any],
    *,
    started: bool,
) -> bool:
    existing_tip = existing.get("tip")
    incoming_tip = incoming.get("tip")

    if started and existing_tip:
        return False
    if existing_tip and not incoming_tip:
        return False
    return True


def merge_predictions_index(
    payloads: list[dict[str, Any]],
    *,
    now: datetime | None = None,
) -> dict[str, dict[str, Any]]:
    now = now or datetime.now(tz=BERLIN)
    kickoffs: dict[str, str] = {}
    for payload in payloads:
        for item in payload.get("predictions", []):
            fixture_id = item.get("fixture_id")
            if fixture_id and item.get("kickoff_berlin"):
                kickoffs.setdefault(fixture_id, item["kickoff_berlin"])

    index: dict[str, dict[str, Any]] = {}
    for payload in payloads:
        for item in payload.get("predictions", []):
            fixture_id = item.get("fixture_id")
            if not fixture_id:
                continue
            kickoff = kickoffs.get(fixture_id, item.get("kickoff_berlin", ""))
            started = is_fixture_started(kickoff, now=now)
            current = index.get(fixture_id)
            if current is None or should_replace_prediction(
                current, item, started=started
            ):
                index[fixture_id] = item
    return index


def load_predictions_index(
    history_dir: Path | None = None,
    predictions_path: Path | None = None,
    *,
    now: datetime | None = None,
) -> dict[str, dict[str, Any]]:
    return merge_predictions_index(
        collect_payloads(history_dir, predictions_path),
        now=now,
    )


def _read_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)
