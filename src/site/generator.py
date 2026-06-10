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

from src.bonus.tips import compute_bonus_tips, load_bonus_payload, save_bonus_payload
from src.optimizer.scoring import kicktipp_points
from src.optimizer.tip_payload import (
    build_ev_alternatives_display,
    is_blowout_tip,
    parse_tip_scores,
)
from src.site.flags import team_flag_url
from src.sources.config import Settings
from src.sources.openfootball import OpenFootballSchedule
from src.sources.team_names import is_tippable_match

ROOT = Path(__file__).resolve().parents[2]
TEMPLATES = ROOT / "site" / "templates"
STATIC = ROOT / "site" / "static"
DOCS = ROOT / "docs"
DISPLAY_MATCHDAYS = tuple(f"Matchday {index}" for index in range(1, 6))
DEFAULT_VERSION_PATH = ROOT / "state" / "site_version.json"


def resolve_site_version(
    version_path: Path | None = None,
    *,
    increment: bool = True,
) -> int:
    """Liest/erhöht die Site-Version (persistiert in state/site_version.json)."""
    path = version_path or DEFAULT_VERSION_PATH
    current = 0
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            current = int(data.get("version", 0))
        except (json.JSONDecodeError, TypeError, ValueError):
            current = 0

    if increment:
        current += 1
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"version": current}, indent=2) + "\n",
            encoding="utf-8",
        )

    return current if current > 0 else 1


def build_site(
    *,
    predictions_path: Path | None = None,
    history_dir: Path | None = None,
    output_dir: Path | None = None,
    version_path: Path | None = None,
    increment_version: bool = True,
) -> Path:
    predictions_path = predictions_path or ROOT / "state" / "predictions.json"
    history_dir = history_dir or ROOT / "state" / "history"
    output_dir = output_dir or DOCS

    site_version = resolve_site_version(
        version_path,
        increment=increment_version,
    )

    rounds = _load_prediction_rounds(predictions_path, history_dir)
    for round_block in rounds:
        _mark_day_highlight(round_block.get("predictions", []))

    shared = _shared_context(site_version=site_version)
    track_rows, track_stats = _load_tracking_rows(predictions_path, history_dir)
    env = _jinja_env()

    output_dir.mkdir(parents=True, exist_ok=True)
    pages = {
        "index.html": {
            **shared,
            "active_page": "dashboard",
            "rounds": rounds,
            "total_matches": sum(
                round_block["match_count"] for round_block in rounds
            ),
        },
        "track.html": {
            **shared,
            "active_page": "track",
            "track_rows": track_rows,
            "track_stats": track_stats,
        },
        "pipeline.html": {
            **shared,
            "active_page": "pipeline",
        },
        "bonus.html": {
            **shared,
            "active_page": "bonus",
            "bonus": _load_bonus_context(),
        },
    }

    index_path = output_dir / "index.html"
    for filename, context in pages.items():
        html = env.get_template(filename).render(**context)
        (output_dir / filename).write_text(html, encoding="utf-8")

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
        kicktipp_spieltag = _kicktipp_spieltag(round_name)
        rounds.append(
            {
                "round_id": _round_id(round_name),
                "round": round_name,
                "tab_label": round_name,
                "date_label": _round_date_label(fixtures),
                "generated_at": _format_generated_at(meta.get("generated_at", "")),
                "match_count": len(predictions),
                "kicktipp_spieltag": kicktipp_spieltag,
                "kicktipp_workflow_url": _kicktipp_workflow_url(kicktipp_spieltag),
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
        enriched["ev_alternatives_display"] = []
        enriched["is_blowout"] = False
        return _attach_team_flags(enriched)

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
    tip_scores = parse_tip_scores(enriched.get("tip"))
    enriched["is_blowout"] = (
        tip_scores is not None and is_blowout_tip(*tip_scores)
    )
    enriched["badges"] = _build_badges(enriched, max_prob)
    enriched["ev_alternatives_display"] = build_ev_alternatives_display(enriched)
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
    return _attach_team_flags(enriched)


def _jinja_env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(TEMPLATES)),
        autoescape=select_autoescape(["html", "xml"]),
    )


def _load_bonus_context() -> dict[str, Any]:
    payload = load_bonus_payload()
    if not payload:
        payload = compute_bonus_tips()
        save_bonus_payload(payload)
    return _enrich_bonus_payload(payload)


def _enrich_bonus_payload(payload: dict[str, Any]) -> dict[str, Any]:
    generated_at = payload.get("generated_at", "")
    display = ""
    if generated_at:
        try:
            dt = datetime.fromisoformat(generated_at)
            display = dt.strftime("%d.%m.%Y %H:%M")
        except ValueError:
            display = generated_at[:16]

    enriched = dict(payload)
    enriched["generated_at_display"] = display or "—"

    for key in ("world_champion", "top_scorer_team"):
        item = dict(enriched[key])
        item["flag_url"] = team_flag_url(item.get("pick", ""))
        enriched[key] = item

    semi = dict(enriched["semi_finalists"])
    semi["picks"] = [
        {
            "pick": team,
            "flag_url": team_flag_url(team),
        }
        for team in semi.get("picks", [])
    ]
    enriched["semi_finalists"] = semi

    group_winners = []
    for item in enriched.get("group_winners", []):
        row = dict(item)
        row["flag_url"] = team_flag_url(row.get("pick", ""))
        group_winners.append(row)
    enriched["group_winners"] = group_winners
    return enriched


def _shared_context(*, site_version: int) -> dict[str, Any]:
    return {
        "title": "WM 2026 Agent",
        "generated_at": datetime.now(tz=ZoneInfo("Europe/Berlin")).strftime(
            "%d.%m.%Y %H:%M"
        ),
        "github_repo": "ElPold/wm2026-agent",
        "update_workflow_url": (
            "https://github.com/ElPold/wm2026-agent/actions/workflows/"
            "update-predictions.yml"
        ),
        "site_version": site_version,
    }


def _kicktipp_spieltag(round_name: str) -> int:
    match = re.search(r"Matchday\s+(\d+)", round_name, re.IGNORECASE)
    if not match:
        return 1
    agent_matchday = int(match.group(1))
    return (agent_matchday + 2) // 3


def _kicktipp_workflow_url(spieltag: int, repo: str = "ElPold/wm2026-agent") -> str:
    return (
        f"https://github.com/{repo}/actions/workflows/"
        f"kicktipp-spieltag-{spieltag}.yml"
    )


def _attach_team_flags(item: dict[str, Any]) -> dict[str, Any]:
    item["home_flag_url"] = team_flag_url(item.get("home_team", ""))
    item["away_flag_url"] = team_flag_url(item.get("away_team", ""))
    return item


def _load_results() -> dict[str, dict[str, Any]]:
    path = ROOT / "state" / "results.json"
    if not path.exists():
        return {}
    payload = _read_json(path)
    if isinstance(payload.get("results"), dict):
        return payload["results"]
    return payload if isinstance(payload, dict) else {}


def _parse_tip_scores(tip: str | None) -> tuple[int, int] | None:
    if not tip or tip == "—" or ":" not in tip:
        return None
    home, away = tip.split(":", 1)
    try:
        return int(home.strip()), int(away.strip())
    except ValueError:
        return None


def _load_tracking_rows(
    predictions_path: Path,
    history_dir: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    predictions_by_id = _predictions_index(predictions_path, history_dir)
    results = _load_results()
    settings = Settings.load()
    fixtures = [
        fixture
        for fixture in OpenFootballSchedule(settings).load_all()
        if is_tippable_match(fixture.home_team, fixture.away_team)
    ]
    fixtures.sort(key=lambda item: item.kickoff_berlin)

    rows: list[dict[str, Any]] = []
    points_scored = 0
    results_known = 0
    tips_submitted = 0
    exact_hits = 0
    played_with_points = 0

    for fixture in fixtures:
        prediction = predictions_by_id.get(fixture.fixture_id)
        tip_raw = prediction.get("tip") if prediction else None
        tip_display = _format_tip_display(tip_raw) if tip_raw else "—"
        if tip_raw:
            tips_submitted += 1

        result_entry = results.get(fixture.fixture_id, {})
        result_scores = None
        if isinstance(result_entry, dict):
            if "home" in result_entry and "away" in result_entry:
                result_scores = (
                    int(result_entry["home"]),
                    int(result_entry["away"]),
                )
            elif result_entry.get("score"):
                result_scores = _parse_tip_scores(str(result_entry["score"]))

        result_display = "—"
        points: int | None = None
        status = "upcoming"

        if result_scores:
            results_known += 1
            result_display = _format_tip_display(
                f"{result_scores[0]}:{result_scores[1]}"
            )
            tip_scores = _parse_tip_scores(tip_raw)
            if tip_scores:
                points = kicktipp_points(
                    tip_scores[0],
                    tip_scores[1],
                    result_scores[0],
                    result_scores[1],
                )
                points_scored += points
                played_with_points += 1
                if points == 4:
                    exact_hits += 1
                status = "scored"
            else:
                status = "no-tip"
        elif tip_raw:
            status = "tipped"
        else:
            status = "open"

        kickoff = fixture.kickoff_berlin
        rows.append(
            _attach_team_flags(
                {
                    "fixture_id": fixture.fixture_id,
                    "round": fixture.round_name,
                    "round_short": _round_short_label(fixture.round_name),
                    "date_short": kickoff.strftime("%d.%m."),
                    "home_team": fixture.home_team,
                    "away_team": fixture.away_team,
                    "tip_display": tip_display,
                    "result_display": result_display,
                    "points": points,
                    "status": status,
                }
            )
        )

    avg_points = (
        round(points_scored / played_with_points, 2)
        if played_with_points
        else "—"
    )
    stats = {
        "total_games": len(rows),
        "tips_submitted": tips_submitted,
        "results_known": results_known,
        "points_scored": points_scored,
        "avg_points": avg_points,
        "exact_hits": exact_hits,
    }
    return rows, stats


def _predictions_index(
    predictions_path: Path,
    history_dir: Path,
) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for payload in _collect_payloads(predictions_path, history_dir):
        for item in payload.get("predictions", []):
            fixture_id = item.get("fixture_id")
            if fixture_id:
                index[fixture_id] = item
    return index


def _round_short_label(round_name: str | None) -> str:
    if not round_name:
        return "—"
    match = re.search(r"Matchday\s+(\d+)", round_name, re.IGNORECASE)
    if match:
        return f"MD{match.group(1)}"
    replacements = {
        "Round of 32": "R32",
        "Round of 16": "R16",
        "Quarter-final": "QF",
        "Semi-final": "SF",
        "Final": "Final",
    }
    return replacements.get(round_name, round_name[:8])


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
    tip_scores = parse_tip_scores(match.get("tip"))
    if tip_scores and is_blowout_tip(*tip_scores):
        badges.append(
            {
                "slug": "blowout",
                "label": "Clear mismatch · wider score band",
            }
        )
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
