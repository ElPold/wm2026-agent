"""Verknüpft Spielplan-Fixtures mit Quoten-Fixtures."""

from __future__ import annotations

from datetime import timedelta

from .models import MatchFixture
from .team_names import teams_match


def link_fixtures(
    schedule: list[MatchFixture],
    odds_fixtures: list[MatchFixture],
    *,
    max_time_delta_hours: float = 3.0,
) -> dict[str, MatchFixture]:
    """
    Ordnet Spielplan-Fixture-IDs OddsPapi/The-Odds-Fixtures zu.

    Returns: schedule_fixture_id -> odds_fixture
    """
    links: dict[str, MatchFixture] = {}
    max_delta = timedelta(hours=max_time_delta_hours)

    for game in schedule:
        for odds_game in odds_fixtures:
            if abs(game.kickoff_utc - odds_game.kickoff_utc) > max_delta:
                continue

            direct = teams_match(game.home_team, odds_game.home_team) and teams_match(
                game.away_team, odds_game.away_team
            )
            swapped = teams_match(game.home_team, odds_game.away_team) and teams_match(
                game.away_team, odds_game.home_team
            )
            if direct or swapped:
                links[game.fixture_id] = odds_game
                break

    return links
