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
from src.sources.oddspapi import OddsPapiClient, parse_bookmaker_odds
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

    if not settings.has_oddspapi():
        print("\nODDSPAPI_API_KEY fehlt.")
        return 1

    client = OddsPapiClient(settings)
    raw = client.get_odds_by_tournament()
    print(f"\n=== OddsPapi Turnier {settings.oddspapi_tournament_id or 16} ===")
    print(f"Fixtures in API: {len(raw)}")

    odds_matches = [client.fixture_to_match(item) for item in raw]
    keywords = ("austral", "turk", "tür", "german", "cura")
    print("\nAPI-Spiele mit Stichwort (austral/turk/german/cura):")
    for item in raw:
        text = f"{item.get('participant1Name')} vs {item.get('participant2Name')}"
        blob = text.lower()
        if any(k in blob for k in keywords):
            market = parse_bookmaker_odds(item, settings.oddspapi_bookmaker)
            odds_txt = (
                f"1X2 {market.home}/{market.draw}/{market.away}"
                if market
                else "keine parsebaren Pinnacle-Märkte"
            )
            print(f"  {text} | start={item.get('startTime')} | {odds_txt}")

    if schedule_hits:
        links = link_fixtures(schedule_hits, odds_matches)
        provider = OddsProvider(settings)
        markets = provider.fetch_odds_for_schedule(schedule_hits)
        print("\n=== Linker-Ergebnis für Zielspiele ===")
        for game in schedule_hits:
            linked = links.get(game.fixture_id)
            market = markets.get(game.fixture_id)
            if linked:
                print(
                    f"  OK {game.home_team} vs {game.away_team} -> "
                    f"API: {linked.home_team} vs {linked.away_team} "
                    f"({linked.kickoff_berlin.isoformat()})"
                )
            else:
                print(f"  KEIN LINK: {game.home_team} vs {game.away_team}")
            if market:
                print(
                    f"    Quoten: {market.home}/{market.draw}/{market.away} "
                    f"O/U {market.over_25}/{market.under_25}"
                )
            else:
                print("    Keine Quoten im Provider")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
