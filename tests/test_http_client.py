from typing import Optional
from unittest.mock import MagicMock, patch

import pytest

from src.sources.http_client import ApiError, HttpClient


def _response(status_code: int, *, headers: Optional[dict] = None, text: str = ""):
    response = MagicMock()
    response.status_code = status_code
    response.headers = headers or {}
    response.text = text
    response.ok = 200 <= status_code < 300
    response.json.return_value = {"ok": True}
    return response


def test_get_json_retries_on_429_without_recursion():
    client = HttpClient(min_interval_sec=0, max_retries=2)
    responses = [
        _response(429, headers={"Retry-After": "0"}),
        _response(429, headers={"Retry-After": "0"}),
        _response(200),
    ]

    with patch.object(client._session, "get", side_effect=responses) as get_mock:
        with patch("src.sources.http_client.time.sleep"):
            payload = client.get_json("https://example.test/odds")

    assert payload == {"ok": True}
    assert get_mock.call_count == 3


def test_get_json_raises_after_max_429_retries():
    client = HttpClient(min_interval_sec=0, max_retries=2)
    responses = [_response(429)] * 3

    with patch.object(client._session, "get", side_effect=responses):
        with patch("src.sources.http_client.time.sleep"):
            with pytest.raises(ApiError, match="Rate limit"):
                client.get_json("https://example.test/odds")


def test_oddspapi_cache_fetches_tournament_odds_once():
    from src.sources.config import Settings
    from src.sources.models import MatchFixture
    from src.sources.odds_provider import OddsProvider
    from datetime import datetime
    from zoneinfo import ZoneInfo

    berlin = ZoneInfo("Europe/Berlin")
    kickoff = datetime(2026, 6, 20, 18, 0, tzinfo=berlin)

    settings = Settings(
        oddspapi_api_key="test-key",
        api_football_api_key=None,
        the_odds_api_key=None,
        oddspapi_tournament_id=16,
    )
    provider = OddsProvider(settings)
    provider._oddspapi.get_odds_by_tournament = MagicMock(return_value=[])

    fixture = MatchFixture(
        fixture_id="1",
        home_team="A",
        away_team="B",
        kickoff_utc=kickoff,
        kickoff_berlin=kickoff,
        source="openfootball",
    )

    provider.fetch_odds_for_schedule([fixture])
    provider.fetch_odds_for_schedule([fixture])

    assert provider._oddspapi.get_odds_by_tournament.call_count == 1


def test_oddspapi_api_error_falls_back_to_the_odds_api():
    from datetime import datetime
    from unittest.mock import MagicMock
    from zoneinfo import ZoneInfo

    from src.sources.config import Settings
    from src.sources.http_client import ApiError
    from src.sources.models import MatchFixture
    from src.sources.odds_provider import OddsProvider

    berlin = ZoneInfo("Europe/Berlin")
    kickoff = datetime(2026, 6, 20, 18, 0, tzinfo=berlin)
    settings = Settings(
        oddspapi_api_key="test-key",
        api_football_api_key=None,
        the_odds_api_key="fallback-key",
        oddspapi_tournament_id=16,
    )
    provider = OddsProvider(settings)
    provider._oddspapi.get_odds_by_tournament = MagicMock(
        side_effect=ApiError("Rate limit erreicht", status_code=429)
    )
    provider._the_odds.get_odds = MagicMock(return_value=[])

    fixture = MatchFixture(
        fixture_id="1",
        home_team="A",
        away_team="B",
        kickoff_utc=kickoff,
        kickoff_berlin=kickoff,
        source="openfootball",
    )

    provider.fetch_odds_for_schedule([fixture])

    provider._the_odds.get_odds.assert_called_once()
