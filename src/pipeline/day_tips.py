"""Erzeugt Tipps für Kalendertage oder komplette Spieltage (Runden)."""

from __future__ import annotations

import json
import logging
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from src.model.calibration import calibrate_poisson_to_market
from src.model.odds import parse_market_odds
from src.model.poisson import top_scores
from src.optimizer.ev import find_optimal_tip
from src.optimizer.tip_payload import top_alternatives_to_json
from src.sources.config import Settings
from src.sources.models import MatchFixture, MatchPrediction
from src.sources.odds_provider import OddsProvider
from src.sources.openfootball import OpenFootballSchedule

logger = logging.getLogger(__name__)


def generate_day_tips(
    day: date,
    settings: Settings | None = None,
    *,
    skip_started: bool = False,
) -> list[MatchPrediction]:
    settings = settings or Settings.load()
    schedule = OpenFootballSchedule(settings).get_fixtures_for_date(day)
    return _generate_predictions_for_fixtures(
        schedule,
        settings=settings,
        skip_started=skip_started,
    )


def generate_round_tips(
    round_name: str,
    settings: Settings | None = None,
    *,
    skip_started: bool = False,
) -> dict[str, Any]:
    """Erzeugt Tipps für alle Spiele einer Runde (z. B. Matchday 1)."""
    settings = settings or Settings.load()
    schedule = OpenFootballSchedule(settings).get_fixtures_for_round(round_name)
    if not schedule:
        logger.info("Keine tippbaren Spiele für %s", round_name)
        return _empty_round_payload(round_name)

    predictions = _generate_predictions_for_fixtures(
        schedule,
        settings=settings,
        skip_started=skip_started,
    )
    prediction_by_id = {
        item.fixture.fixture_id: item for item in predictions
    }

    entries: list[dict[str, Any]] = []
    for fixture in sorted(schedule, key=lambda item: item.kickoff_berlin):
        prediction = prediction_by_id.get(fixture.fixture_id)
        if prediction:
            entries.append(_prediction_to_dict(prediction))
        else:
            entries.append(_pending_fixture_dict(fixture))

    return {
        "round": round_name,
        "generated_at": datetime.now(tz=ZoneInfo("Europe/Berlin")).isoformat(),
        "match_count": len(entries),
        "predictions": entries,
    }


def _generate_predictions_for_fixtures(
    schedule: list[MatchFixture],
    *,
    settings: Settings,
    skip_started: bool,
) -> list[MatchPrediction]:
    now = datetime.now(tz=ZoneInfo("Europe/Berlin"))

    if not schedule:
        return []

    if not settings.has_oddspapi() and not settings.has_the_odds_api():
        raise ValueError(
            "ODDSPAPI_API_KEY oder THE_ODDS_API_KEY fehlt — keine Quotenquelle"
        )

    provider = OddsProvider(settings)
    odds_by_fixture = provider.fetch_odds_for_schedule(schedule)
    predictions: list[MatchPrediction] = []

    for fixture in schedule:
        if skip_started and fixture.kickoff_berlin <= now:
            logger.info(
                "Überspringe gestartetes Spiel %s vs. %s",
                fixture.home_team,
                fixture.away_team,
            )
            continue

        odds = odds_by_fixture.get(fixture.fixture_id)
        if not odds:
            logger.warning(
                "Überspringe %s vs. %s — keine Quoten",
                fixture.home_team,
                fixture.away_team,
            )
            continue

        market = parse_market_odds(odds.as_1x2_dict(), odds.as_ou25_dict())
        calibration = calibrate_poisson_to_market(market)
        recommendation = find_optimal_tip(calibration.distribution)

        predictions.append(
            MatchPrediction(
                fixture=fixture,
                odds=odds,
                tip_home=recommendation.tip_home,
                tip_away=recommendation.tip_away,
                expected_points=recommendation.expected_points,
                most_likely_score=recommendation.most_likely_score,
                lambda_home=calibration.lambda_home,
                lambda_away=calibration.lambda_away,
                market_probs=calibration.market_probs,
                top_scores=top_scores(calibration.distribution, n=5),
                top_alternatives=recommendation.top_alternatives,
            )
        )

    return predictions


def _empty_round_payload(round_name: str) -> dict[str, Any]:
    return {
        "round": round_name,
        "generated_at": datetime.now(tz=ZoneInfo("Europe/Berlin")).isoformat(),
        "match_count": 0,
        "predictions": [],
    }


def _pending_fixture_dict(fixture: MatchFixture) -> dict[str, Any]:
    return {
        "fixture_id": fixture.fixture_id,
        "home_team": fixture.home_team,
        "away_team": fixture.away_team,
        "kickoff_berlin": fixture.kickoff_berlin.isoformat(),
        "venue": fixture.venue,
        "round": fixture.round_name,
        "pending": True,
    }


def round_slug(round_name: str) -> str:
    slug = round_name.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    return slug.strip("-")


def archive_predictions(
    output_path: Path,
    history_dir: Path,
    *,
    day: date | None = None,
) -> Path | None:
    """Kopiert Tipps nach state/history/YYYY-MM-DD.json."""
    if not output_path.exists():
        return None

    with output_path.open(encoding="utf-8") as handle:
        payload = json.load(handle)

    if day is None:
        predictions = payload.get("predictions", [])
        if predictions:
            kickoff = predictions[0].get("kickoff_berlin", "")
            day = date.fromisoformat(kickoff[:10]) if kickoff else date.today()
        else:
            day = date.today()

    history_dir.mkdir(parents=True, exist_ok=True)
    archive_path = history_dir / f"{day.isoformat()}.json"
    with archive_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    return archive_path


def archive_round_predictions(
    payload: dict[str, Any],
    history_dir: Path,
) -> Path | None:
    """Archiviert einen kompletten Spieltag nach state/history/rounds/."""
    round_name = payload.get("round")
    if not round_name:
        return None

    archive_dir = history_dir / "rounds"
    archive_dir.mkdir(parents=True, exist_ok=True)
    archive_path = archive_dir / f"{round_slug(round_name)}.json"
    with archive_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    return archive_path


def save_predictions(
    predictions: list[MatchPrediction],
    output_path: Path,
    *,
    generated_at: datetime | None = None,
) -> Path:
    generated_at = generated_at or datetime.now(tz=ZoneInfo("Europe/Berlin"))
    payload = {
        "generated_at": generated_at.isoformat(),
        "match_count": len(predictions),
        "predictions": [_prediction_to_dict(item) for item in predictions],
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    return output_path


def save_round_payload(payload: dict[str, Any], output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    return output_path


def _prediction_to_dict(prediction: MatchPrediction) -> dict[str, Any]:
    fixture = prediction.fixture
    return {
        "fixture_id": fixture.fixture_id,
        "home_team": fixture.home_team,
        "away_team": fixture.away_team,
        "kickoff_berlin": fixture.kickoff_berlin.isoformat(),
        "venue": fixture.venue,
        "round": fixture.round_name,
        "odds_source": prediction.odds.source,
        "bookmaker": prediction.odds.bookmaker,
        "odds_1x2": prediction.odds.as_1x2_dict(),
        "odds_ou25": prediction.odds.as_ou25_dict(),
        "market_probs": prediction.market_probs,
        "lambda_home": prediction.lambda_home,
        "lambda_away": prediction.lambda_away,
        "tip": f"{prediction.tip_home}:{prediction.tip_away}",
        "expected_points": round(prediction.expected_points, 4),
        "most_likely_score": (
            f"{prediction.most_likely_score[0]}:{prediction.most_likely_score[1]}"
        ),
        "top_scores": [
            {"score": f"{h}:{a}", "probability": round(p, 4)}
            for (h, a), p in prediction.top_scores
        ],
        "top_alternatives": top_alternatives_to_json(prediction.top_alternatives),
    }
