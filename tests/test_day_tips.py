def test_day_tips_module_has_openfootball_schedule():
    from src.pipeline import day_tips

    assert day_tips.OpenFootballSchedule is not None
