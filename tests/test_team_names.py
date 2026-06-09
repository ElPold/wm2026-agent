from src.sources.team_names import (
    canonical_team_key,
    is_placeholder_team,
    is_tippable_match,
    teams_match,
)


def test_usa_alias():
    assert teams_match("USA", "United States")
    assert canonical_team_key("United States") == "usa"


def test_dr_congo_alias():
    assert teams_match(
        "DR Congo",
        "Democratic Republic of the Congo",
    )


def test_placeholder_detection():
    assert is_placeholder_team("2A")
    assert is_placeholder_team("W101")
    assert is_placeholder_team("3A/B/C/D/F")
    assert not is_placeholder_team("Mexico")


def test_tippable_match():
    assert is_tippable_match("Mexico", "South Africa")
    assert not is_tippable_match("2A", "2B")
