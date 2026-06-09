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
    for day in days:
        _mark_day_highlight(day.get("predictions", []))

    context = {
        "title": "WM 2026 Agent",
        "generated_at": datetime.now(tz=ZoneInfo("Europe/Berlin")).strftime(
            "%d.%m.%Y %H:%M"
        ),
        "days": days,
        "total_matches": sum(day["match_count"] for day in days),
        "update_workflow_url": (
            "https://github.com/ElPold/wm2026-agent/actions/workflows/"
            "update-predictions.yml"
        ),
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

    days = sorted(payloads.values(), key=lambda item: item["date"])
    for day in days:
        day["predictions"].sort(key=lambda item: item.get("kickoff_berlin", ""))
        day["tab_label"] = _tab_label(day["predictions"], day_key=day["date"])
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
        predictions.append(_enrich_match(item))

    return {
        "date": day_key,
        "date_label": _format_date_label(day_key),
        "generated_at": _format_generated_at(payload.get("generated_at", "")),
        "match_count": payload.get("match_count", len(predictions)),
        "predictions": predictions,
    }


def _enrich_match(item: dict[str, Any]) -> dict[str, Any]:
    enriched = dict(item)
    probs = enriched.get("market_probs", {})
    home = float(probs.get("home", 0))
    draw = float(probs.get("draw", 0))
    away = float(probs.get("away", 0))
    max_prob = max(home, draw, away)

    enriched["prob_bars"] = [
        ("1", home),
        ("X", draw),
        ("2", away),
    ]
    enriched["prob_chips"] = [
        {"key": "1", "value": home},
        {"key": "X", "value": draw},
        {"key": "2", "value": away},
    ]
    enriched["kickoff_time"] = _format_kickoff(enriched.get("kickoff_berlin", ""))
    enriched["tip_display"] = _format_tip_display(enriched.get("tip", ""))
    enriched["has_odds"] = bool(enriched.get("odds_1x2"))
    enriched["badges"] = _build_badges(enriched, max_prob)
    enriched["confidence"] = _confidence_level(max_prob)
    enriched["signal_strength"] = int(round(max_prob * 100))
    enriched["top_scores_display"] = [
        {
            "score": _format_tip_display(item["score"]),
            "probability": item["probability"],
        }
        for item in enriched.get("top_scores", [])
    ]
    return enriched


def _format_tip_display(tip: str) -> str:
    if ":" in tip:
        home, away = tip.split(":", 1)
        return f"{home.strip()} : {away.strip()}"
    return tip


def _confidence_level(max_prob: float) -> str:
    if max_prob >= 0.55:
        return "high"
    if max_prob < 0.40:
        return "low"
    return "medium"


def _build_badges(match: dict[str, Any], max_prob: float) -> list[dict[str, str]]:
    if not match.get("has_odds", True):
        return [{"slug": "no-odds", "label": "No odds yet"}]

    badges = [
        {"slug": "ev-pick", "label": "EV Pick"},
        {"slug": "market", "label": "Market Signal"},
    ]
    if max_prob >= 0.55:
        badges.append({"slug": "high", "label": "High Confidence"})
    elif max_prob < 0.40:
        badges.append({"slug": "low", "label": "Low Confidence"})
    return badges


def _mark_day_highlight(predictions: list[dict[str, Any]]) -> None:
    if not predictions:
        return
    best = max(predictions, key=lambda item: float(item.get("expected_points", 0)))
    best_id = best.get("fixture_id")
    for item in predictions:
        item["is_day_highlight"] = item.get("fixture_id") == best_id


def _tab_label(predictions: list[dict[str, Any]], day_key: str) -> str:
    if predictions:
        round_name = predictions[0].get("round")
        if round_name:
            return round_name
    try:
        dt = datetime.strptime(day_key, "%Y-%m-%d")
        return dt.strftime("%d.%m.%Y")
    except ValueError:
        return day_key


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
