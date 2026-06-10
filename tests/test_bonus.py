import json
from pathlib import Path

from src.bonus.groups import load_group_teams
from src.bonus.tips import compute_bonus_tips, save_bonus_payload
from src.site.generator import build_site

ROOT = Path(__file__).resolve().parents[1]


def test_load_group_teams_has_twelve_groups():
    groups = load_group_teams(ROOT / "data" / "schedule" / "worldcup.json")
    assert len(groups) == 12
    assert groups["Group A"] == [
        "Czech Republic",
        "Mexico",
        "South Africa",
        "South Korea",
    ]


def test_compute_bonus_tips_from_archived_predictions(tmp_path):
    state = tmp_path / "state"
    history = state / "history"
    rounds = history / "rounds"
    rounds.mkdir(parents=True)

    payload = {
        "round": "Matchday 1",
        "generated_at": "2026-06-09T18:00:00+02:00",
        "match_count": 1,
        "predictions": [
            {
                "fixture_id": "wc26-001",
                "home_team": "Mexico",
                "away_team": "South Africa",
                "market_probs": {"home": 0.68, "draw": 0.21, "away": 0.11},
                "lambda_home": 1.8,
                "lambda_away": 0.7,
            }
        ],
    }
    with (rounds / "matchday-1.json").open("w", encoding="utf-8") as handle:
        json.dump(payload, handle)

    result = compute_bonus_tips(
        predictions_path=state / "predictions.json",
        history_dir=history,
    )

    assert result["world_champion"]["pick"]
    assert len(result["semi_finalists"]["picks"]) == 4
    assert len(result["group_winners"]) == 12
    assert result["group_winners"][0]["group"] == "Group A"
    assert result["top_scorer_team"]["reasoning"]


def test_build_site_includes_bonus_page(tmp_path):
    state = tmp_path / "state"
    history = state / "history"
    docs = tmp_path / "docs"
    history.mkdir(parents=True)

    predictions_path = state / "predictions.json"
    with predictions_path.open("w", encoding="utf-8") as handle:
        json.dump({"generated_at": "2026-06-09T18:00:00+02:00", "predictions": []}, handle)

    build_site(
        predictions_path=predictions_path,
        history_dir=history,
        output_dir=docs,
    )

    html = (docs / "bonus.html").read_text(encoding="utf-8")
    assert "Bonus questions" in html
    assert "Group winners" in html
    assert "Semi-finalists" in html
    assert 'href="bonus.html"' in (docs / "index.html").read_text(encoding="utf-8")
