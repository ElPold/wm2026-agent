#!/usr/bin/env python3
"""Prüft, ob OddsPapi/The Odds API Quoten für konkrete Spiele liefert."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.sources.config import Settings
from src.sources.match_linker import link_fixtures
from src.sources.oddspapi import OddsPapiClient
from src.sources.openfootball import OpenFootballSchedule
from src.sources.odds_provider import OddsProvider
from src.sources.team_names import teams_match


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--home",
        action="append",
        default=[],
        help="Heimteam (mehrfach für mehrere Spiele)",
    )
    parser.add_argument(
        "--away",
        action="append",
        default=[],
        help="Auswärtsteam (paarweise zu --home)",
    )
    args = parser.parse_args()

    if len(args.home) != len(args.away):
        print("Fehler: gleiche Anzahl --home und --away nötig.", file=sys.stderr)
        return 1

    settings = Settings.load()
    schedule = OpenFootballSchedule(settings).load_all()
    targets = list(zip(args.home, args.away))

    print("=== Spielplan (openfootball) ===")
    schedule_hits = []
    for home, away in targets:
        for game in schedule:
            if teams_match(game.home_team, home) and teams_match(game.away_team, away):
                schedule_hits.append(game)
                print(
                    f"  {game.fixture_id}: {game.home_team} vs {game.away_team} "
                    f"@ {game.kickoff_berlin.isoformat()}"
                )
        else:
            if not any(
                teams_match(g.home_team, home) and teams_match(g.away_team, away)
                for g in schedule_hits
            ):
                print(f"  NICHT im Spielplan: {home} vs {away}")

    if not schedule_hits:
        return 1

    if not settings.has_oddspapi() and not settings.has_the_odds_api():
        print("\nWeder ODDSPAPI_API_KEY noch THE_ODDS_API_KEY gesetzt.", file=sys.stderr)
        return 1

    provider = OddsProvider(settings)
    markets = provider.fetch_odds_for_schedule(schedule_hits)
    print("\n=== Quoten (OddsPapi → The Odds API Fallback) ===")
    ok = 0
    for game in schedule_hits:
        market = markets.get(game.fixture_id)
        if market:
            ok += 1
            print(
                f"  OK {game.home_team} vs {game.away_team}: "
                f"1X2 {market.home}/{market.draw}/{market.away} "
                f"O/U {market.over_2_5}/{market.under_2_5} "
                f"({market.source}/{market.bookmaker})"
            )
        else:
            print(f"  FEHLT {game.home_team} vs {game.away_team}")

    if settings.has_oddspapi():
        try:
            client = OddsPapiClient(settings)
            raw = client.get_odds_by_tournament()
            odds_matches = [client.fixture_to_match(item) for item in raw]
            links = link_fixtures(schedule_hits, odds_matches)
            print(f"\n=== OddsPapi Diagnose (Turnier {settings.oddspapi_tournament_id or 16}) ===")
            print(f"Fixtures in API: {len(raw)}, Links: {len(links)}/{len(schedule_hits)}")
        except Exception as exc:
            print(f"\n=== OddsPapi Diagnose ===\n  nicht verfügbar: {exc}")

    return 0 if ok == len(schedule_hits) else 1


if __name__ == "__main__":
    raise SystemExit(main())
