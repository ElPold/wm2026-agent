#!/usr/bin/env python3
"""Überträgt state/predictions.json (und optional bonus.json) an kicktipp-agent CLI.

kicktipp-agent (https://github.com/christianheidorn/kicktipp-agent) stellt dieselbe
Logik als CLI und als MCP-Server bereit. In GitHub Actions wird die CLI genutzt;
lokal kannst du alternativ kicktipp-mcp in Cursor anbinden.

Voraussetzungen:
  - KICKTIPP_EMAIL, KICKTIPP_PASSWORD (Umgebungsvariablen)
  - KICKTIPP_COMMUNITY (Community-Slug, z. B. meine-wm-runde)
  - kicktipp-Binary im PATH oder KICKTIPP_BIN=/pfad/zu/dist/index.js
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PREDICTIONS = ROOT / "state" / "predictions.json"
DEFAULT_BONUS = ROOT / "state" / "bonus.json"
DEFAULT_ALIASES = ROOT / "config" / "kicktipp_aliases.json"


def parse_matchday(round_name: str) -> int | None:
    match = re.search(r"matchday\s*(\d+)", round_name, re.IGNORECASE)
    return int(match.group(1)) if match else None


def load_aliases(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Aliases must be a JSON object: {path}")
    return {str(k): str(v) for k, v in data.items()}


def kicktipp_team(name: str, aliases: dict[str, str]) -> str:
    return aliases.get(name, name)


def match_bets_from_predictions(payload: dict, aliases: dict[str, str]) -> list[str]:
    bets: list[str] = []
    for item in payload.get("predictions", []):
        if item.get("pending"):
            continue
        tip = item.get("tip")
        if not tip:
            continue
        home = kicktipp_team(item["home_team"], aliases)
        away = kicktipp_team(item["away_team"], aliases)
        bets.append(f"{home} vs {away}={tip}")
    return bets


def bonus_bets_from_state(payload: dict, aliases: dict[str, str]) -> list[str]:
    bets: list[str] = []

    champion = payload.get("world_champion") or {}
    if champion.get("question") and champion.get("pick"):
        pick = kicktipp_team(champion["pick"], aliases)
        bets.append(f"{champion['question']}={pick}")

    scorer = payload.get("top_scorer_team") or {}
    if scorer.get("question") and scorer.get("pick"):
        pick = kicktipp_team(scorer["pick"], aliases)
        bets.append(f"{scorer['question']}={pick}")

    semi = payload.get("semi_finalists") or {}
    question = semi.get("question")
    for pick in semi.get("picks") or []:
        bets.append(f"{question}={kicktipp_team(pick, aliases)}")

    for group in payload.get("group_winners") or []:
        if group.get("question") and group.get("pick"):
            pick = kicktipp_team(group["pick"], aliases)
            bets.append(f"{group['question']}={pick}")

    return bets


def write_kicktipp_community(community: str) -> Path:
    config_dir = Path.home() / ".config" / "kicktipp-agent"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_file = config_dir / "config.ini"
    config_file.write_text(f"[community]\nname = {community}\n", encoding="utf-8")
    os.chmod(config_file, 0o600)
    return config_file


def kicktipp_command_prefix() -> list[str]:
    bin_path = os.environ.get("KICKTIPP_BIN", "kicktipp")
    if bin_path.endswith(".js"):
        return ["node", bin_path]
    return [bin_path]


def run_kicktipp(args: list[str], *, dry_run: bool) -> int:
    cmd = [*kicktipp_command_prefix(), *args]
    if dry_run:
        print("DRY RUN:", " ".join(cmd))
        return 0
    print("RUN:", " ".join(cmd[:3]), f"... ({len(args)} args)")
    result = subprocess.run(cmd, check=False)
    return result.returncode


def ensure_credentials() -> None:
    if os.environ.get("KICKTIPP_EMAIL") and os.environ.get("KICKTIPP_PASSWORD"):
        return
    print(
        "Fehler: KICKTIPP_EMAIL und KICKTIPP_PASSWORD müssen gesetzt sein.",
        file=sys.stderr,
    )
    sys.exit(1)


def ensure_community(community: str | None) -> str:
    if community:
        path = write_kicktipp_community(community)
        print(f"Community gesetzt: {community} ({path})")
        return community
    print(
        "Fehler: KICKTIPP_COMMUNITY fehlt (Kicktipp-Community-Slug).",
        file=sys.stderr,
    )
    sys.exit(1)


def ensure_kicktipp_available() -> None:
    prefix = kicktipp_command_prefix()
    executable = prefix[-1] if prefix[0] == "node" else prefix[0]
    if prefix[0] == "node":
        if not Path(executable).is_file():
            print(f"Fehler: KICKTIPP_BIN nicht gefunden: {executable}", file=sys.stderr)
            sys.exit(1)
        if not shutil.which("node"):
            print("Fehler: node nicht im PATH.", file=sys.stderr)
            sys.exit(1)
        return
    if not shutil.which(executable):
        print(
            "Fehler: kicktipp nicht im PATH. Installiere kicktipp-agent oder setze KICKTIPP_BIN.",
            file=sys.stderr,
        )
        sys.exit(1)


def main() -> int:
    parser = argparse.ArgumentParser(description="Tipps an kicktipp.com übertragen")
    parser.add_argument(
        "--predictions",
        type=Path,
        default=DEFAULT_PREDICTIONS,
        help="Pfad zu state/predictions.json",
    )
    parser.add_argument(
        "--bonus",
        type=Path,
        default=None,
        help="Pfad zu state/bonus.json (optional, sonst --no-bonus)",
    )
    parser.add_argument(
        "--no-bonus",
        action="store_true",
        help="Bonusfragen nicht übertragen",
    )
    parser.add_argument(
        "--aliases",
        type=Path,
        default=DEFAULT_ALIASES,
        help="Optionale Teamnamen-Map (openfootball → Kicktipp-Anzeigename)",
    )
    parser.add_argument(
        "--matchday",
        type=int,
        default=None,
        help="Spieltag-Nummer (Default: aus predictions.json round)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Nur Befehle ausgeben, nichts abgeben",
    )
    args = parser.parse_args()

    if not args.dry_run:
        ensure_credentials()
        ensure_kicktipp_available()

    aliases = load_aliases(args.aliases)
    community = ensure_community(os.environ.get("KICKTIPP_COMMUNITY")) if not args.dry_run else os.environ.get("KICKTIPP_COMMUNITY", "(dry-run)")

    predictions_payload = json.loads(args.predictions.read_text(encoding="utf-8"))
    match_bets = match_bets_from_predictions(predictions_payload, aliases)
    if not match_bets:
        print("Keine abzugebenden Spieltipps gefunden.")
    else:
        matchday = args.matchday or parse_matchday(predictions_payload.get("round", ""))
        cmd_args = ["bet", *match_bets]
        if matchday is not None:
            cmd_args.extend(["--matchday", str(matchday)])
        else:
            print("Hinweis: Kein Spieltag erkannt — kicktipp nutzt den aktuellen Tag.")
        print(f"Community: {community}")
        print(f"Spieltipps ({len(match_bets)}):")
        for bet in match_bets:
            print(f"  {bet}")
        code = run_kicktipp(cmd_args, dry_run=args.dry_run)
        if code != 0:
            return code

    bonus_path = None if args.no_bonus else (args.bonus or DEFAULT_BONUS)
    if bonus_path and bonus_path.exists():
        bonus_payload = json.loads(bonus_path.read_text(encoding="utf-8"))
        bonus_bets = bonus_bets_from_state(bonus_payload, aliases)
        if bonus_bets:
            print(f"Bonusfragen ({len(bonus_bets)}):")
            for bet in bonus_bets:
                print(f"  {bet}")
            code = run_kicktipp(["bet", "--bonus", *bonus_bets], dry_run=args.dry_run)
            if code != 0:
                return code
        else:
            print("Keine Bonusantworten in bonus.json.")
    elif not args.no_bonus:
        print("Keine bonus.json — Bonus übersprungen.")

    print("Kicktipp-Übertragung abgeschlossen.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
