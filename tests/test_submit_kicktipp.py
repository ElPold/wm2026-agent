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
match_bets_for_kicktipp_spieltag = _mod.match_bets_for_kicktipp_spieltag
kicktipp_pair_key = _mod.kicktipp_pair_key
parse_matchday = _mod.parse_agent_matchday
kicktipp_spieltag = _mod.kicktipp_spieltag
agent_rounds_for_kicktipp_spieltag = _mod.agent_rounds_for_kicktipp_spieltag
load_predictions_for_kicktipp_spieltag = _mod.load_predictions_for_kicktipp_spieltag
load_all_predictions_from_history = _mod.load_all_predictions_from_history
resolve_kicktipp_spieltag_by_probe = _mod.resolve_kicktipp_spieltag_by_probe
map_bonus_question = _mod.map_bonus_question
resolve_upcoming_kicktipp_spieltag = _mod.resolve_upcoming_kicktipp_spieltag


def test_parse_matchday():
    assert parse_matchday("Matchday 5") == 5
    assert parse_matchday("matchday 12") == 12
    assert parse_matchday("Round of 16") is None


def test_kicktipp_spieltag_mapping():
    assert kicktipp_spieltag(1) == 1
    assert kicktipp_spieltag(3) == 1
    assert kicktipp_spieltag(4) == 2
    assert kicktipp_spieltag(6) == 2
    assert kicktipp_spieltag(7) == 3


def test_agent_rounds_for_kicktipp_spieltag():
    assert agent_rounds_for_kicktipp_spieltag(1) == [1, 2, 3]
    assert agent_rounds_for_kicktipp_spieltag(2) == [4, 5, 6]


def test_load_all_predictions_from_history(tmp_path):
    history = tmp_path / "rounds"
    history.mkdir()
    (history / "matchday-1.json").write_text(
        '{"round": "Matchday 1", "predictions": [{"home_team": "A", "away_team": "B", "tip": "1:0"}]}',
        encoding="utf-8",
    )
    (history / "matchday-9.json").write_text(
        '{"round": "Matchday 9", "predictions": [{"home_team": "C", "away_team": "D", "tip": "2:1"}]}',
        encoding="utf-8",
    )
    payload = load_all_predictions_from_history(history_dir=history)
    assert len(payload["predictions"]) == 2
    assert payload["agent_rounds"] == ["Matchday 1", "Matchday 9"]


def test_resolve_kicktipp_spieltag_by_probe(monkeypatch):
    calls: list[int] = []

    def fake_fetch(spieltag: int):
        calls.append(spieltag)
        if spieltag == 4:
            return [{"home": "Tschechien", "away": "Südafrika"}]
        return []

    monkeypatch.setenv("KICKTIPP_COMMUNITY", "entertainment")
    monkeypatch.setattr(_mod, "fetch_kicktipp_tippabgabe_matches", fake_fetch)
    kt = resolve_kicktipp_spieltag_by_probe(
        "Czech Republic",
        "South Africa",
        {"Czech Republic": "Tschechien", "South Africa": "Südafrika"},
    )
    assert kt == 4
    assert calls == [1, 2, 3, 4]


def test_load_predictions_for_kicktipp_spieltag(tmp_path):
    history = tmp_path / "rounds"
    history.mkdir()
    (history / "matchday-1.json").write_text(
        '{"round": "Matchday 1", "predictions": [{"home_team": "A", "away_team": "B", "tip": "1:0"}]}',
        encoding="utf-8",
    )
    (history / "matchday-2.json").write_text(
        '{"round": "Matchday 2", "predictions": [{"home_team": "C", "away_team": "D", "tip": "2:1"}]}',
        encoding="utf-8",
    )
    payload = load_predictions_for_kicktipp_spieltag(1, history_dir=history)
    assert len(payload["predictions"]) == 2
    assert payload["agent_rounds"] == ["Matchday 1", "Matchday 2"]


def test_match_bets_filters_to_kicktipp_page():
    payload = {
        "predictions": [
            {"home_team": "Czech Republic", "away_team": "South Africa", "tip": "1:0"},
            {"home_team": "Portugal", "away_team": "DR Congo", "tip": "2:0"},
            {"home_team": "England", "away_team": "Croatia", "tip": "1:0"},
        ]
    }
    aliases = {"Czech Republic": "Tschechien", "South Africa": "Südafrika", "DR Congo": "DR Kongo"}
    kicktipp_matches = [
        {"home": "Tschechien", "away": "Südafrika"},
        {"home": "Portugal", "away": "DR Kongo"},
    ]
    bets, skipped = match_bets_for_kicktipp_spieltag(payload, aliases, kicktipp_matches)
    assert bets == [
        "Tschechien vs Südafrika=1:0",
        "Portugal vs DR Kongo=2:0",
    ]
    assert skipped == ["England vs Croatia (nicht auf Kicktipp-Spieltag)"]


def test_match_bets_without_kicktipp_page_falls_back_to_all():
    payload = {
        "predictions": [
            {"home_team": "Germany", "away_team": "France", "tip": "2:1"},
        ]
    }
    bets, skipped = match_bets_for_kicktipp_spieltag(payload, {"Germany": "Deutschland"}, [])
    assert bets == ["Deutschland vs France=2:1"]
    assert skipped == []


def test_kicktipp_pair_key_ignores_home_away_order():
    assert kicktipp_pair_key("A", "B") == kicktipp_pair_key("B", "A")


def test_match_bets_maps_curacao_alias():
    payload = {
        "predictions": [
            {
                "home_team": "Germany",
                "away_team": "Curaçao",
                "tip": "2:0",
            },
        ]
    }
    aliases = {"Germany": "Deutschland", "Curaçao": "Curaçao"}
    bets = match_bets_from_predictions(payload, aliases)
    assert bets == ["Deutschland vs Curaçao=2:0"]


def test_match_bets_maps_bosnia_alias():
    payload = {
        "predictions": [
            {
                "home_team": "Canada",
                "away_team": "Bosnia & Herzegovina",
                "tip": "1:0",
            },
        ]
    }
    aliases = {"Bosnia & Herzegovina": "Bosnien-Herzegowina"}
    bets = match_bets_from_predictions(payload, aliases)
    assert bets == ["Canada vs Bosnien-Herzegowina=1:0"]


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


def test_resolve_upcoming_kicktipp_spieltag_before_tournament():
    from datetime import datetime
    from zoneinfo import ZoneInfo

    before = datetime(2026, 6, 10, 12, 0, tzinfo=ZoneInfo("Europe/Berlin"))
    assert resolve_upcoming_kicktipp_spieltag(now=before) == 1


def test_resolve_upcoming_kicktipp_spieltag_after_group_stage():
    from datetime import datetime
    from zoneinfo import ZoneInfo

    after = datetime(2026, 7, 20, 12, 0, tzinfo=ZoneInfo("Europe/Berlin"))
    assert resolve_upcoming_kicktipp_spieltag(now=after) is None


def test_map_bonus_question_de():
    import os

    os.environ["KICKTIPP_LOCALE"] = "de"
    assert map_bonus_question("Who will be world champion?") == "Wer wird Weltmeister?"
    assert map_bonus_question("Who wins Group H?") == "Wer gewinnt die Gruppe H?"


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
    import os

    os.environ["KICKTIPP_LOCALE"] = "de"
    bets = bonus_bets_from_state(payload, {"Argentina": "Argentinien"})
    assert bets[0] == "Wer wird Weltmeister?=Argentinien"
    assert bets[1] == "Wer erreicht das Halbfinale?=Argentinien"
    assert bets[2] == "Wer erreicht das Halbfinale?=France"
    assert bets[3] == "Wer gewinnt die Gruppe A?=Mexico"
