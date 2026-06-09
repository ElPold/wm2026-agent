"""Statische Website für GitHub Pages generieren."""

from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from jinja2 import Environment, FileSystemLoader, select_autoescape

ROOT = Path(__file__).resolve().parents[2]
TEMPLATES = ROOT / "site" / "templates"
STATIC = ROOT / "site" / "static"
DOCS = ROOT / "docs"


def build_site(
    *,
    predictions_path: Path | None = None,
    history_dir: Path | None = None,
    output_dir: Path | None = None,
) -> Path:
    predictions_path = predictions_path or ROOT / "state" / "predictions.json"
    history_dir = history_dir or ROOT / "state" / "history"
    output_dir = output_dir or DOCS

    days = _load_prediction_days(predictions_path, history_dir)
    context = {
        "title": "WM 2026 Kicktipp-Agent",
        "generated_at": datetime.now(tz=ZoneInfo("Europe/Berlin")).strftime(
            "%d.%m.%Y %H:%M"
        ),
        "days": days,
        "total_matches": sum(day["match_count"] for day in days),
    }

    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES)),
        autoescape=select_autoescape(["html", "xml"]),
    )
    template = env.get_template("index.html")
    html = template.render(**context)

    output_dir.mkdir(parents=True, exist_ok=True)
    index_path = output_dir / "index.html"
    index_path.write_text(html, encoding="utf-8")

    static_out = output_dir / "static"
    if static_out.exists():
        shutil.rmtree(static_out)
    if STATIC.exists():
        shutil.copytree(STATIC, static_out)

    (output_dir / ".nojekyll").touch()
    return index_path


def _load_prediction_days(
    predictions_path: Path,
    history_dir: Path,
) -> list[dict[str, Any]]:
    payloads: dict[str, dict[str, Any]] = {}

    if history_dir.exists():
        for path in sorted(history_dir.glob("*.json")):
            day_key = path.stem
            payloads[day_key] = _enrich_payload(_read_json(path), day_key)

    if predictions_path.exists():
        payload = _read_json(predictions_path)
        day_key = _day_key_from_payload(payload)
        if day_key:
            payloads[day_key] = _enrich_payload(payload, day_key)

    days = sorted(payloads.values(), key=lambda item: item["date"], reverse=True)
    for day in days:
        day["predictions"].sort(key=lambda item: item.get("kickoff_berlin", ""))
    return days


def _read_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _day_key_from_payload(payload: dict[str, Any]) -> str | None:
    predictions = payload.get("predictions", [])
    if not predictions:
        return None
    kickoff = predictions[0].get("kickoff_berlin", "")
    if not kickoff:
        return None
    return kickoff[:10]


def _enrich_payload(payload: dict[str, Any], day_key: str) -> dict[str, Any]:
    predictions = []
    for item in payload.get("predictions", []):
        enriched = dict(item)
        probs = enriched.get("market_probs", {})
        enriched["prob_bars"] = [
            ("Heimsieg", probs.get("home", 0)),
            ("Remis", probs.get("draw", 0)),
            ("Auswärtssieg", probs.get("away", 0)),
        ]
        enriched["kickoff_time"] = _format_kickoff(enriched.get("kickoff_berlin", ""))
        predictions.append(enriched)

    return {
        "date": day_key,
        "date_label": _format_date_label(day_key),
        "generated_at": _format_generated_at(payload.get("generated_at", "")),
        "match_count": payload.get("match_count", len(predictions)),
        "predictions": predictions,
    }


def _format_kickoff(value: str) -> str:
    if not value:
        return "—"
    try:
        dt = datetime.fromisoformat(value)
        return dt.strftime("%H:%M")
    except ValueError:
        return value


_WEEKDAYS_DE = (
    "Montag",
    "Dienstag",
    "Mittwoch",
    "Donnerstag",
    "Freitag",
    "Samstag",
    "Sonntag",
)


def _format_date_label(day_key: str) -> str:
    try:
        dt = datetime.strptime(day_key, "%Y-%m-%d")
        weekday = _WEEKDAYS_DE[dt.weekday()]
        return f"{weekday}, {dt.strftime('%d.%m.%Y')}"
    except ValueError:
        return day_key


def _format_generated_at(value: str) -> str:
    if not value:
        return "—"
    try:
        dt = datetime.fromisoformat(value)
        return dt.astimezone(ZoneInfo("Europe/Berlin")).strftime("%d.%m.%Y %H:%M")
    except ValueError:
        return value
