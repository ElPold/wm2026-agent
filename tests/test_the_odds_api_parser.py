import json
from pathlib import Path

from src.sources.the_odds_api import parse_event_odds

FIXTURES = Path(__file__).resolve().parents[1] / "data" / "fixtures"


def test_parse_the_odds_api_event():
    with (FIXTURES / "the_odds_api_event.json").open(encoding="utf-8") as handle:
        event = json.load(handle)

    odds = parse_event_odds(event)
    assert odds is not None
    assert odds.home == 1.85
    assert odds.draw == 3.40
    assert odds.away == 4.50
    assert odds.over_2_5 == 2.10
    assert odds.under_2_5 == 1.75
    assert odds.source == "the_odds_api"
