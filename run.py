#!/usr/bin/env python3
"""Orchestrierung eines täglichen Laufs (Phase 0: Stub)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))


def main() -> None:
    parser = argparse.ArgumentParser(description="WM 2026 Kicktipp-Agent")
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Pipeline-Demo mit Beispielspiel ausführen",
    )
    args = parser.parse_args()

    if args.demo:
        from demo import main as demo_main

        demo_main()
        return

    print("Noch kein vollständiger Lauf implementiert. Nutze: python run.py --demo")


if __name__ == "__main__":
    main()
