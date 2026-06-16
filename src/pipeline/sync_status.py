"""Persistierter Sync-Status für Tipps-Update und Kicktipp-Übertragung."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from src.sources.config import ROOT

BERLIN = ZoneInfo("Europe/Berlin")
DEFAULT_SYNC_PATH = ROOT / "state" / "sync_status.json"


def load_sync_status(path: Path | None = None) -> dict[str, Any]:
    sync_path = path or DEFAULT_SYNC_PATH
    if not sync_path.exists():
        return {}
    try:
        data = json.loads(sync_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def update_sync_status(
    section: str,
    data: dict[str, Any],
    *,
    path: Path | None = None,
) -> Path:
    sync_path = path or DEFAULT_SYNC_PATH
    payload = load_sync_status(sync_path)
    payload[section] = data
    sync_path.parent.mkdir(parents=True, exist_ok=True)
    sync_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return sync_path


def sync_mode() -> str:
    import os

    return "auto" if os.environ.get("GITHUB_EVENT_NAME") == "schedule" else "manual"


def format_sync_timestamp(value: str | None) -> str:
    if not value:
        return "—"
    try:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=BERLIN)
        return dt.astimezone(BERLIN).strftime("%d.%m.%Y %H:%M")
    except ValueError:
        return value[:16] if value else "—"


def build_sync_display(path: Path | None = None) -> dict[str, Any] | None:
    payload = load_sync_status(path)
    if not payload:
        return None

    display: dict[str, Any] = {}
    predictions = payload.get("predictions")
    if isinstance(predictions, dict):
        display["predictions"] = {
            "updated_at": format_sync_timestamp(predictions.get("updated_at")),
            "rounds": predictions.get("rounds"),
            "mode": predictions.get("mode"),
            "round": predictions.get("round"),
            "source": predictions.get("source"),
        }

    kicktipp = payload.get("kicktipp")
    if isinstance(kicktipp, dict):
        status = str(kicktipp.get("status", "unknown"))
        display["kicktipp"] = {
            "synced_at": format_sync_timestamp(kicktipp.get("synced_at")),
            "status": status,
            "status_class": status if status in {"ok", "failed", "skipped"} else "unknown",
            "spieltag": kicktipp.get("spieltag"),
            "tips_count": kicktipp.get("tips_count"),
            "agent_rounds": kicktipp.get("agent_rounds") or [],
            "mode": kicktipp.get("mode"),
            "error": kicktipp.get("error"),
        }

    return display or None
