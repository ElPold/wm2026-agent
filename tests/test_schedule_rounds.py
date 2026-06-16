import re

from src.sources.schedule_rounds import round_sort_key, schedule_round_names


def test_round_sort_key_orders_matchdays_before_knockout():
    keys = [round_sort_key(name) for name in schedule_round_names()]
    assert keys == sorted(keys)
    assert round_sort_key("Matchday 1") < round_sort_key("Matchday 17")
    assert round_sort_key("Matchday 17") < round_sort_key("Round of 32")
    assert round_sort_key("Semi-final") < round_sort_key("Final")


def test_schedule_round_names_includes_group_and_knockout():
    names = schedule_round_names()
    assert len(names) >= 17
    assert any(re.fullmatch(r"Matchday \d+", name) for name in names)
    assert "Round of 32" in names
    assert "Final" in names
