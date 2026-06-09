"""Statische Website für GitHub Pages generieren."""

from __future__ import annotations

import json
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from jinja2 import Environment, FileSystemLoader, select_autoescape

from src.sources.config import Settings
from src.sources.openfootball import OpenFootballSchedule
from src.sources.team_names import is_tippable_match

ROOT = Path(__file__).resolve().parents[2]
TEMPLATES = ROOT / "site" / "templates"
STATIC = ROOT / "site" / "static"
DOCS = ROOT / "docs"
DISPLAY_MATCHDAYS = tuple(f"Matchday {index}" for index in range(1, 6))


def build_site(
    *,
    predictions_path: Path | None = None,
    history_dir: Path | None = None,
    output_dir: Path | None = None,
) -> Path:
    predictions_path = predictions_path or ROOT / "state" / "predictions.json"
    history_dir = history_dir or ROOT / "state" / "history"
    output_dir = output_dir or DOCS

    rounds = _load_prediction_rounds(predictions_path, history_dir)
    for round_block in rounds:
        _mark_day_highlight(round_block.get("predictions", []))

    context = {
        "title": "WM 2026 Agent",
        "generated_at": datetime.now(tz=ZoneInfo("Europe/Berlin")).strftime(
            "%d.%m.%Y %H:%M"
        ),
        "rounds": rounds,
        "total_matches": sum(round_block["match_count"] for round_block in rounds),
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


def _load_prediction_rounds(
    predictions_path: Path,
    history_dir: Path,
) -> list[dict[str, Any]]:
    payloads = _collect_payloads(predictions_path, history_dir)
    predictions_by_id: dict[str, dict[str, Any]] = {}
    round_meta: dict[str, dict[str, str]] = {}

    for payload in payloads:
        generated_at = payload.get("generated_at", "")
        payload_round = payload.get("round")
        if payload_round:
            round_meta[payload_round] = {
                "generated_at": generated_at,
                "round": payload_round,
            }

        for item in payload.get("predictions", []):
            fixture_id = item.get("fixture_id")
            if not fixture_id:
                continue
            predictions_by_id[fixture_id] = item
            round_name = item.get("round") or payload_round
            if round_name and round_name not in round_meta:
                round_meta[round_name] = {
                    "generated_at": generated_at,
                    "round": round_name,
                }

    settings = Settings.load()
    schedule = OpenFootballSchedule(settings).load_all()
    schedule_by_round: dict[str, list] = {}
    for fixture in schedule:
        if not fixture.round_name or not is_tippable_match(
            fixture.home_team, fixture.away_team
        ):
            continue
        schedule_by_round.setdefault(fixture.round_name, []).append(fixture)

    rounds: list[dict[str, Any]] = []
    for round_name in DISPLAY_MATCHDAYS:
        fixtures = sorted(
            schedule_by_round.get(round_name, []),
            key=lambda item: item.kickoff_berlin,
        )
        if not fixtures:
            continue

        predictions: list[dict[str, Any]] = []
        for fixture in fixtures:
            raw = predictions_by_id.get(fixture.fixture_id)
            if raw:
                predictions.append(_enrich_match(raw))
            else:
                predictions.append(
                    _enrich_match(
                        {
                            "fixture_id": fixture.fixture_id,
                            "home_team": fixture.home_team,
                            "away_team": fixture.away_team,
                            "kickoff_berlin": fixture.kickoff_berlin.isoformat(),
                            "venue": fixture.venue,
                            "round": fixture.round_name,
                            "pending": True,
                        }
                    )
                )

        meta = round_meta.get(round_name, {})
        rounds.append(
            {
                "round_id": _round_id(round_name),
                "round": round_name,
                "tab_label": round_name,
                "date_label": _round_date_label(fixtures),
                "generated_at": _format_generated_at(meta.get("generated_at", "")),
                "match_count": len(predictions),
                "predictions": predictions,
            }
        )

    return rounds


def _collect_payloads(
    predictions_path: Path,
    history_dir: Path,
) -> list[dict[str, Any]]:
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


def _read_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _enrich_match(item: dict[str, Any]) -> dict[str, Any]:
    enriched = dict(item)
    pending = bool(enriched.get("pending")) or not enriched.get("tip")
    enriched["is_pending"] = pending

    if pending:
        enriched["tip_display"] = "—"
        enriched["most_likely_display"] = None
        enriched["expected_points"] = 0.0
        enriched["kickoff_time"] = _format_kickoff(enriched.get("kickoff_berlin", ""))
        enriched["prob_bars"] = [("1", 0.0), ("X", 0.0), ("2", 0.0)]
        enriched["prob_chips"] = [
            {"key": "1", "value": 0.0},
            {"key": "X", "value": 0.0},
            {"key": "2", "value": 0.0},
        ]
        enriched["has_odds"] = False
        enriched["badges"] = [{"slug": "no-odds", "label": "No odds yet"}]
        enriched["confidence"] = "low"
        enriched["signal_strength"] = 0
        enriched["top_scores_display"] = []
        return enriched

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
    most_likely = enriched.get("most_likely_score", "")
    enriched["most_likely_display"] = (
        _format_tip_display(most_likely) if most_likely else None
    )
    enriched["has_odds"] = bool(enriched.get("odds_1x2"))
    enriched["badges"] = _build_badges(enriched, max_prob)
    enriched["confidence"] = _confidence_level(max_prob)
    enriched["signal_strength"] = int(round(max_prob * 100))
    top_scores = enriched.get("top_scores", [])
    max_prob_score = max(
        (float(item["probability"]) for item in top_scores),
        default=0.0,
    )
    enriched["top_scores_display"] = [
        {
            "score": _format_tip_display(item["score"]),
            "probability": item["probability"],
            "pct": round(float(item["probability"]) * 100, 1),
            "bar_width": (
                int(round(float(item["probability"]) / max_prob_score * 100))
                if max_prob_score
                else 0
            ),
            "is_pick": _format_tip_display(item["score"]) == enriched["tip_display"],
        }
        for item in top_scores
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
    with_tips = [
        item
        for item in predictions
        if not item.get("is_pending") and item.get("expected_points", 0) > 0
    ]
    if not with_tips:
        return
    best = max(with_tips, key=lambda item: float(item.get("expected_points", 0)))
    best_id = best.get("fixture_id")
    for item in predictions:
        item["is_day_highlight"] = item.get("fixture_id") == best_id


def _round_sort_key(round_name: str) -> tuple:
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


def _round_id(round_name: str) -> str:
    slug = round_name.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    return slug.strip("-")


def _round_date_label(fixtures: list) -> str:
    if not fixtures:
        return ""
    dates = sorted({fixture.kickoff_berlin.date().isoformat() for fixture in fixtures})
    if len(dates) == 1:
        return _format_date_label(dates[0])
    first = _format_date_label(dates[0])
    last = _format_date_label(dates[-1])
    return f"{first} – {last}"


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
