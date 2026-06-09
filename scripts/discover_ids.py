#!/usr/bin/env python3
"""Hilfsskript: Tournament-IDs und Datenquellen prüfen."""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.sources.config import Settings
from src.sources.oddspapi import OddsPapiClient
from src.sources.openfootball import OpenFootballSchedule


def main() -> None:
    settings = Settings.load()
    print("WM 2026 — Datenquellen-Check")
    print("=" * 50)

    schedule = OpenFootballSchedule(settings)
    all_matches = schedule.load_all()
    print(f"Spielplan (openfootball): {len(all_matches)} Spiele")
    print(f"  Datei: {settings.schedule_path}")

    opening_day = date(2026, 6, 11)
    day_matches = schedule.get_fixtures_for_date(opening_day)
    print(f"  Eröffnungstag {opening_day}: {len(day_matches)} tippbare Spiele")
    for match in day_matches:
        print(
            f"    {match.fixture_id} {match.home_team} vs. {match.away_team} "
            f"({match.kickoff_berlin.strftime('%H:%M')} Berlin)"
        )

    print()

    if settings.has_oddspapi():
        client = OddsPapiClient(settings)
        tournaments = client.list_tournaments()
        print(f"OddsPapi Turniere (Soccer): {len(tournaments)}")
        wc_id = client.find_world_cup_tournament_id()
        if wc_id:
            print(f"Empfohlene WM-ID: ODDSPAPI_TOURNAMENT_ID={wc_id}")
            try:
                fixtures = client.get_odds_by_tournament(wc_id)
                sample = fixtures[0] if fixtures else {}
                print(
                    f"Verifiziert: {len(fixtures)} Spiele, Beispiel "
                    f"{sample.get('participant1Name')} vs. {sample.get('participant2Name')}"
                )
            except Exception as exc:
                print(f"Verifikation fehlgeschlagen: {exc}")
        else:
            print("Kein World-Cup-Turnier gefunden — ID manuell setzen.")
    else:
        print("ODDSPAPI_API_KEY fehlt (Pflicht für Live-Quoten)")

    print()
    if settings.has_the_odds_api():
        print(f"The Odds API Sport (Fallback): {settings.the_odds_api_sport}")
    else:
        print("THE_ODDS_API_KEY fehlt (optionaler Quoten-Fallback)")

    print()
    if settings.has_api_football():
        print("API_FOOTBALL_API_KEY gesetzt (optional, nicht mehr für Spielplan nötig)")
    else:
        print("API_FOOTBALL_API_KEY nicht gesetzt (OK — Spielplan kommt aus openfootball)")


if __name__ == "__main__":
    main()
