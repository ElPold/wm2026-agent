from src.site.flags import team_flag_code, team_flag_url


def test_team_flag_for_mexico():
    assert team_flag_code("Mexico") == "mx"
    assert team_flag_url("Mexico") == "https://flagcdn.com/w40/mx.png"


def test_placeholder_team_has_no_flag():
    assert team_flag_code("1A") is None
    assert team_flag_url("W101") is None
