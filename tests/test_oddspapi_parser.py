import json
from pathlib import Path

from src.sources.oddspapi import parse_bookmaker_odds

FIXTURES = Path(__file__).resolve().parents[1] / "data" / "fixtures"


def test_parse_oddspapi_odds():
    with (FIXTURES / "oddspapi_fixture.json").open(encoding="utf-8") as handle:
        fixture = json.load(handle)

    odds = parse_bookmaker_odds(fixture)
    assert odds is not None
    assert odds.home == 1.85
    assert odds.draw == 3.40
    assert odds.away == 4.50
    assert odds.over_2_5 == 2.10
    assert odds.under_2_5 == 1.75
    assert odds.source == "oddspapi"
