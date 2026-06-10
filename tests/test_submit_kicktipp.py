import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "submit_kicktipp",
    Path(__file__).resolve().parents[1] / "scripts" / "submit_kicktipp.py",
)
_mod = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_mod)

bonus_bets_from_state = _mod.bonus_bets_from_state
match_bets_from_predictions = _mod.match_bets_from_predictions
parse_matchday = _mod.parse_matchday


def test_parse_matchday():
    assert parse_matchday("Matchday 5") == 5
    assert parse_matchday("matchday 12") == 12
    assert parse_matchday("Round of 16") is None


def test_match_bets_skips_pending():
    payload = {
        "predictions": [
            {
                "home_team": "Spain",
                "away_team": "Cape Verde",
                "tip": "1:0",
            },
            {
                "home_team": "Germany",
                "away_team": "France",
                "tip": "2:1",
                "pending": True,
            },
        ]
    }
    bets = match_bets_from_predictions(payload, {"Cape Verde": "Cabo Verde"})
    assert bets == ["Spain vs Cabo Verde=1:0"]


def test_bonus_bets_multi_select():
    payload = {
        "world_champion": {
            "question": "Who will be world champion?",
            "pick": "Argentina",
        },
        "semi_finalists": {
            "question": "Who reaches the semi-final?",
            "picks": ["Argentina", "France"],
        },
        "group_winners": [
            {"question": "Who wins Group A?", "pick": "Mexico"},
        ],
    }
    bets = bonus_bets_from_state(payload, {})
    assert bets[0] == "Who will be world champion?=Argentina"
    assert bets[1] == "Who reaches the semi-final?=Argentina"
    assert bets[2] == "Who reaches the semi-final?=France"
    assert bets[3] == "Who wins Group A?=Mexico"
