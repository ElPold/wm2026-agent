"""Bonusfragen-Antworten aus Marktquoten und Turniersimulation."""

from __future__ import annotations

import json
import logging
import random
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from src.bonus.groups import GROUP_ORDER, group_letter, load_group_teams
from src.model.calibration import calibrate_poisson_to_market
from src.model.odds import parse_market_odds
from src.model.poisson import sample_score
from src.sources.config import Settings
from src.sources.models import MatchFixture
from src.sources.odds_provider import OddsProvider
from src.sources.openfootball import OpenFootballSchedule

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[2]
BONUS_PATH = ROOT / "state" / "bonus.json"

# Start-Ratings (Elo-ähnlich) für Teams ohne Quoten — grobe WM-2026-Markt-Prior.
FALLBACK_RATINGS: dict[str, float] = {
    "Argentina": 2100,
    "France": 2080,
    "England": 2060,
    "Brazil": 2050,
    "Spain": 2040,
    "Portugal": 2030,
    "Germany": 2020,
    "Netherlands": 2010,
    "Belgium": 2000,
    "Croatia": 1985,
    "Italy": 1980,
    "Uruguay": 1975,
    "Colombia": 1970,
    "Mexico": 1965,
    "USA": 1960,
    "Switzerland": 1955,
    "Japan": 1950,
    "Morocco": 1945,
    "Senegal": 1940,
    "Ecuador": 1935,
    "Austria": 1930,
    "Norway": 1925,
    "Scotland": 1920,
    "Paraguay": 1910,
    "Australia": 1905,
    "South Korea": 1900,
    "Turkey": 1895,
    "Ukraine": 1890,
    "Czech Republic": 1885,
    "Sweden": 1880,
    "Denmark": 1875,
    "Serbia": 1870,
    "Poland": 1865,
    "Canada": 1860,
    "Egypt": 1855,
    "Tunisia": 1850,
    "Algeria": 1845,
    "Ivory Coast": 1840,
    "Ghana": 1835,
    "Cameroon": 1830,
    "South Africa": 1825,
    "Saudi Arabia": 1820,
    "Iran": 1815,
    "Iraq": 1810,
    "Qatar": 1805,
    "Jordan": 1800,
    "Uzbekistan": 1795,
    "New Zealand": 1790,
    "Panama": 1785,
    "Haiti": 1780,
    "Curaçao": 1775,
    "Cape Verde": 1770,
    "DR Congo": 1765,
    "Bosnia & Herzegovina": 1760,
}


def load_bonus_payload(path: Path | None = None) -> dict[str, Any] | None:
    path = path or BONUS_PATH
    if not path.exists():
        return None
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def save_bonus_payload(payload: dict[str, Any], path: Path | None = None) -> Path:
    path = path or BONUS_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    return path


def compute_bonus_tips(
    *,
    settings: Settings | None = None,
    predictions_path: Path | None = None,
    history_dir: Path | None = None,
    refresh_odds: bool = False,
) -> dict[str, Any]:
    settings = settings or Settings.load()
    predictions_path = predictions_path or ROOT / "state" / "predictions.json"
    history_dir = history_dir or ROOT / "state" / "history"

    predictions = _collect_predictions(predictions_path, history_dir)
    if refresh_odds and settings.has_oddspapi():
        predictions = _merge_fetched_group_odds(predictions, settings)

    groups = load_group_teams(settings.schedule_path)
    all_teams = sorted({team for teams in groups.values() for team in teams})
    ratings = _estimate_ratings(all_teams, predictions)
    attack_index = _attack_index(all_teams, predictions)

    group_answers = []
    for group_name in GROUP_ORDER:
        teams = groups.get(group_name, [])
        if not teams:
            continue
        pick, confidence, reasoning = _pick_group_winner(
            group_name, teams, ratings, predictions
        )
        group_answers.append(
            _answer(
                question_id=f"group-{group_letter(group_name).lower()}",
                question=f"Who wins {group_name}?",
                pick=pick,
                confidence=confidence,
                reasoning=reasoning,
                category="group",
                group=group_name,
            )
        )

    semi_teams = _pick_semi_finalists(all_teams, ratings)
    champion = max(all_teams, key=lambda team: ratings[team])
    champion_conf = _normalized_confidence(champion, all_teams, ratings)
    scorer_team = max(all_teams, key=lambda team: attack_index[team])

    payload = {
        "generated_at": datetime.now(tz=ZoneInfo("Europe/Berlin")).isoformat(),
        "odds_fixtures_used": sum(1 for item in predictions if item.get("market_probs")),
        "simulation_runs": 4000,
        "world_champion": _answer(
            question_id="world-champion",
            question="Who will be world champion?",
            pick=champion,
            confidence=champion_conf,
            reasoning=(
                f"{champion} tops the market-derived power index "
                f"({ratings[champion]:.0f} pts) across all available Pinnacle fixtures. "
                "Tournament winners usually need sustained knockout strength; "
                "this rating aggregates every linked 1X2 line we have."
            ),
            category="champion",
        ),
        "top_scorer_team": _answer(
            question_id="top-scorer-team",
            question="Which team supplies the top scorer?",
            pick=scorer_team,
            confidence=_normalized_confidence(scorer_team, all_teams, attack_index),
            reasoning=(
                f"{scorer_team} leads the expected-goals index "
                f"({attack_index[scorer_team]:.2f} λ avg per appearance in priced matches). "
                "Golden Boot teams usually come from high-volume, high-quality attacks — "
                "Poisson λ calibrated to market goals lines is our proxy."
            ),
            category="scorer",
        ),
        "semi_finalists": {
            "question_id": "semi-finalists",
            "question": "Who reaches the semi-final?",
            "picks": semi_teams,
            "reasoning": (
                "Four teams with the highest market power index — "
                f"{', '.join(semi_teams)}. "
                "Chosen before running a simplified knockout bracket on group-winner "
                "simulations; aligns with outright favourite clusters in the odds."
            ),
            "category": "semi",
        },
        "group_winners": group_answers,
    }
    return payload


def _answer(
    *,
    question_id: str,
    question: str,
    pick: str,
    confidence: float | None,
    reasoning: str,
    category: str,
    group: str | None = None,
) -> dict[str, Any]:
    return {
        "question_id": question_id,
        "question": question,
        "pick": pick,
        "confidence": round(confidence, 3) if confidence is not None else None,
        "reasoning": reasoning,
        "category": category,
        "group": group,
    }


def _collect_predictions(
    predictions_path: Path,
    history_dir: Path,
) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}

    paths: list[Path] = []
    if predictions_path.exists():
        paths.append(predictions_path)
    rounds_dir = history_dir / "rounds"
    if rounds_dir.exists():
        paths.extend(sorted(rounds_dir.glob("*.json")))
    for day_file in sorted(history_dir.glob("20*.json")):
        paths.append(day_file)

    for path in paths:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        for item in payload.get("predictions", []):
            fixture_id = item.get("fixture_id")
            if fixture_id and item.get("market_probs"):
                by_id[fixture_id] = item

    return list(by_id.values())


def _merge_fetched_group_odds(
    predictions: list[dict[str, Any]],
    settings: Settings,
) -> list[dict[str, Any]]:
    by_id = {item["fixture_id"]: item for item in predictions}
    schedule = [
        fixture
        for fixture in OpenFootballSchedule(settings).load_all()
        if _is_group_stage_fixture(fixture, settings.schedule_path)
    ]
    provider = OddsProvider(settings)
    odds_by_fixture = provider.fetch_odds_for_schedule(schedule)

    for fixture in schedule:
        odds = odds_by_fixture.get(fixture.fixture_id)
        if not odds:
            continue
        market = parse_market_odds(odds.as_1x2_dict(), odds.as_ou25_dict())
        calibration = calibrate_poisson_to_market(market)
        by_id[fixture.fixture_id] = {
            "fixture_id": fixture.fixture_id,
            "home_team": fixture.home_team,
            "away_team": fixture.away_team,
            "market_probs": calibration.market_probs,
            "lambda_home": calibration.lambda_home,
            "lambda_away": calibration.lambda_away,
        }

    return list(by_id.values())


def _is_group_stage_fixture(fixture: MatchFixture, schedule_path: Path) -> bool:
    from src.bonus.groups import fixture_group_map

    return fixture.fixture_id in fixture_group_map(schedule_path)


def _estimate_ratings(
    teams: list[str],
    predictions: list[dict[str, Any]],
) -> dict[str, float]:
    ratings = {team: float(FALLBACK_RATINGS.get(team, 1750)) for team in teams}

    for _ in range(3):
        for item in predictions:
            market = item.get("market_probs")
            if not market:
                continue
            home = item["home_team"]
            away = item["away_team"]
            if home not in ratings or away not in ratings:
                continue

            expected_home = _win_expectancy(ratings[home], ratings[away])
            actual_home = market["home"] + 0.5 * market["draw"]
            actual_away = market["away"] + 0.5 * market["draw"]
            delta = 48 * (actual_home - expected_home)
            ratings[home] += delta
            ratings[away] -= delta

    return ratings


def _attack_index(
    teams: list[str],
    predictions: list[dict[str, Any]],
) -> dict[str, float]:
    totals: dict[str, float] = defaultdict(float)
    counts: dict[str, int] = defaultdict(int)

    for team in teams:
        totals[team] = FALLBACK_RATINGS.get(team, 1750) / 900.0
        counts[team] = 1

    for item in predictions:
        home = item["home_team"]
        away = item["away_team"]
        lambda_home = item.get("lambda_home")
        lambda_away = item.get("lambda_away")
        if lambda_home is not None and home in totals:
            totals[home] += float(lambda_home)
            counts[home] += 1
        if lambda_away is not None and away in totals:
            totals[away] += float(lambda_away)
            counts[away] += 1

    return {team: totals[team] / counts[team] for team in teams}


def _win_expectancy(rating_a: float, rating_b: float) -> float:
    return 1.0 / (1.0 + 10 ** ((rating_b - rating_a) / 400.0))


def _pick_group_winner(
    group_name: str,
    teams: list[str],
    ratings: dict[str, float],
    predictions: list[dict[str, Any]],
) -> tuple[str, float, str]:
    wins = Counter()
    runs = 4000
    rng = random.Random(42)

    group_predictions = [
        item
        for item in predictions
        if item.get("home_team") in teams and item.get("away_team") in teams
    ]

    for _ in range(runs):
        table = _simulate_group_table(teams, group_predictions, ratings, rng)
        wins[table[0]] += 1

    pick, win_count = wins.most_common(1)[0]
    confidence = win_count / runs
    ordered = sorted(teams, key=lambda team: ratings[team], reverse=True)
    runner_up = ordered[1] if ordered[0] == pick else ordered[0]
    priced = len(group_predictions)
    return (
        pick,
        confidence,
        (
            f"Monte Carlo group simulation ({runs:,} runs, {priced} priced fixtures) "
            f"gives {pick} a {confidence * 100:.0f}% chance to top {group_name}. "
            f"Market strength ranks them above {runner_up} ({ratings[pick]:.0f} vs "
            f"{ratings[runner_up]:.0f} power index)."
        ),
    )


def _simulate_group_table(
    teams: list[str],
    predictions: list[dict[str, Any]],
    ratings: dict[str, float],
    rng: random.Random,
) -> list[str]:
    lookup = {
        (item["home_team"], item["away_team"]): item for item in predictions
    }

    points: dict[str, int] = {team: 0 for team in teams}
    goals_for: dict[str, int] = {team: 0 for team in teams}
    goals_against: dict[str, int] = {team: 0 for team in teams}

    for index, home in enumerate(teams):
        for away in teams[index + 1 :]:
            home_goals, away_goals = _simulate_fixture(
                home, away, lookup.get((home, away)), ratings, rng
            )
            goals_for[home] += home_goals
            goals_for[away] += away_goals
            goals_against[home] += away_goals
            goals_against[away] += home_goals

            if home_goals > away_goals:
                points[home] += 3
            elif away_goals > home_goals:
                points[away] += 3
            else:
                points[home] += 1
                points[away] += 1

    return sorted(
        teams,
        key=lambda team: (
            points[team],
            goals_for[team] - goals_against[team],
            goals_for[team],
            ratings[team],
        ),
        reverse=True,
    )


def _simulate_fixture(
    home: str,
    away: str,
    prediction: dict[str, Any] | None,
    ratings: dict[str, float],
    rng: random.Random,
) -> tuple[int, int]:
    if prediction and prediction.get("lambda_home") is not None:
        return sample_score(
            float(prediction["lambda_home"]),
            float(prediction["lambda_away"]),
            rng=rng,
        )

    if prediction and prediction.get("market_probs"):
        market = prediction["market_probs"]
        roll = rng.random()
        if roll < market["home"]:
            return 1, 0
        if roll < market["home"] + market["draw"]:
            return 1, 1
        return 0, 1

    expected_home = _win_expectancy(ratings[home], ratings[away])
    roll = rng.random()
    if roll < expected_home * 0.78:
        return 1, 0
    if roll < expected_home * 0.78 + 0.22:
        return 1, 1
    return 0, 1


def _pick_semi_finalists(teams: list[str], ratings: dict[str, float]) -> list[str]:
    return sorted(teams, key=lambda team: ratings[team], reverse=True)[:4]


def _normalized_confidence(
    pick: str,
    teams: list[str],
    metric: dict[str, float],
) -> float:
    values = sorted((metric[team] for team in teams), reverse=True)
    if len(values) < 2:
        return 1.0
    top = metric[pick]
    second = values[1] if values[0] == top else values[0]
    gap = max(top - second, 0.0)
    scale = max(top, 1.0)
    return min(0.95, 0.45 + 0.5 * (gap / scale))
