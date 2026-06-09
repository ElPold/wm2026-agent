#!/usr/bin/env python3
"""Orchestrierung eines täglichen Laufs."""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from src.pipeline.day_tips import archive_predictions, generate_day_tips, save_predictions
from src.site.generator import build_site
from src.sources.config import Settings

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def _run_script(name: str) -> None:
    import importlib.util

    script = ROOT / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, script)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    module.main()


def main() -> None:
    parser = argparse.ArgumentParser(description="WM 2026 Kicktipp-Agent")
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Pipeline-Demo mit lokalen Beispielquoten",
    )
    parser.add_argument(
        "--discover",
        action="store_true",
        help="Datenquellen und OddsPapi-Turnier-ID prüfen",
    )
    parser.add_argument(
        "--fetch-schedule",
        action="store_true",
        help="Spielplan von openfootball aktualisieren",
    )
    parser.add_argument(
        "--build-site",
        action="store_true",
        help="Statische Website nach docs/ generieren",
    )
    parser.add_argument(
        "--date",
        type=str,
        default=None,
        help="Berliner Kalenderdatum (YYYY-MM-DD), Standard: heute",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="state/predictions.json",
        help="Ausgabepfad für Tipps (JSON)",
    )
    parser.add_argument(
        "--no-site",
        action="store_true",
        help="Website nach Tipp-Lauf nicht neu bauen",
    )
    args = parser.parse_args()

    if args.demo:
        from demo import main as demo_main

        demo_main()
        return

    if args.fetch_schedule:
        _run_script("fetch_schedule")
        return

    if args.discover:
        _run_script("discover_ids")
        return

    if args.build_site:
        site_path = build_site()
        print(f"Website generiert → {site_path}")
        return

    settings = Settings.load()
    day = date.fromisoformat(args.date) if args.date else date.today()
    logger.info("Generiere Tipps für %s (Berlin)", day.isoformat())

    predictions = generate_day_tips(day, settings=settings)
    if not predictions:
        print(f"Keine Tipps für {day.isoformat()} — keine Spiele oder keine Quoten.")
        return

    output_path = save_predictions(predictions, ROOT / args.output)
    history_path = archive_predictions(
        output_path,
        ROOT / "state" / "history",
        day=day,
    )
    print(f"{len(predictions)} Tipps gespeichert → {output_path}")
    if history_path:
        print(f"Archiviert → {history_path}")

    for item in predictions:
        print(
            f"  {item.fixture.home_team} vs. {item.fixture.away_team}: "
            f"{item.tip_home}:{item.tip_away} "
            f"(EV {item.expected_points:.3f}, Quelle: {item.odds.source})"
        )

    if not args.no_site:
        site_path = build_site()
        print(f"Website generiert → {site_path}")


if __name__ == "__main__":
    main()
