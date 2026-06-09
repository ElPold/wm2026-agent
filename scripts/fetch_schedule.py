#!/usr/bin/env python3
"""Lädt den WM-2026-Spielplan von openfootball herunter."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.sources.openfootball import OPENFOOTBALL_URL

OUTPUT = ROOT / "data" / "schedule" / "worldcup.json"


def main() -> None:
    print(f"Lade Spielplan von openfootball …")
    response = requests.get(OPENFOOTBALL_URL, timeout=30)
    response.raise_for_status()
    payload = response.json()

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)

    match_count = len(payload.get("matches", []))
    print(f"✓ {match_count} Spiele gespeichert → {OUTPUT}")


if __name__ == "__main__":
    main()
