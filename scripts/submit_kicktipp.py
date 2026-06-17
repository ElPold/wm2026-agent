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
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PREDICTIONS = ROOT / "state" / "predictions.json"
DEFAULT_BONUS = ROOT / "state" / "bonus.json"
DEFAULT_ALIASES = ROOT / "config" / "kicktipp_aliases.json"
DEFAULT_SPIELTAG_MAP = ROOT / "config" / "kicktipp_spieltag.json"
DEFAULT_HISTORY = ROOT / "state" / "history" / "rounds"
DEFAULT_TIPPABGABE_JSON = ROOT / "scripts" / "kicktipp_tippabgabe_json.mjs"
DEFAULT_AGENT_ROOT = ROOT / ".kicktipp-agent"

BONUS_QUESTION_DE: dict[str, str] = {
    "Who will be world champion?": "Wer wird Weltmeister?",
    "Which team supplies the top scorer?": (
        "Welche Mannschaft stellt den Spieler mit den meisten Toren?"
    ),
    "Who reaches the semi-final?": "Wer erreicht das Halbfinale?",
}


def resolve_upcoming_kicktipp_spieltag(
    *,
    now: datetime | None = None,
    aliases: dict[str, str] | None = None,
) -> int | None:
    """Kicktipp-Spieltag für das nächste anstehende Gruppenspiel."""
    sys.path.insert(0, str(ROOT))
    from src.sources.config import Settings
    from src.sources.openfootball import OpenFootballSchedule
    from src.sources.team_names import is_tippable_match

    settings = Settings.load()
    now = now or datetime.now(tz=ZoneInfo("Europe/Berlin"))
    upcoming = [
        fixture
        for fixture in OpenFootballSchedule(settings).load_all()
        if fixture.round_name
        and is_tippable_match(fixture.home_team, fixture.away_team)
        and fixture.kickoff_berlin > now
    ]
    if not upcoming:
        return None

    earliest = min(upcoming, key=lambda item: item.kickoff_berlin)
    agent_md = parse_agent_matchday(earliest.round_name or "")
    if agent_md is None:
        return None

    if aliases is not None:
        probed = resolve_kicktipp_spieltag_by_probe(
            earliest.home_team,
            earliest.away_team,
            aliases,
        )
        if probed is not None:
            return probed

    return kicktipp_spieltag(agent_md)


def resolve_kicktipp_spieltag_by_probe(
    home: str,
    away: str,
    aliases: dict[str, str],
    *,
    max_spieltag: int = 6,
) -> int | None:
    """Findet den Kicktipp-Spieltag, auf dem ein Team-Paar tippbar ist."""
    if not os.environ.get("KICKTIPP_COMMUNITY"):
        return None

    kh = kicktipp_team(home, aliases)
    ka = kicktipp_team(away, aliases)
    key = kicktipp_pair_key(kh, ka)
    for kt in range(1, max_spieltag + 1):
        matches = fetch_kicktipp_tippabgabe_matches(kt)
        if not matches:
            continue
        indexed = {kicktipp_pair_key(str(row["home"]), str(row["away"])) for row in matches}
        if key in indexed:
            return kt
    return None


def record_kicktipp_sync(
    *,
    status: str,
    spieltag: int | None,
    tips_count: int,
    agent_rounds: list[str] | None = None,
    error: str | None = None,
) -> None:
    sync_path = ROOT / "state" / "sync_status.json"
    payload: dict = {}
    if sync_path.exists():
        try:
            loaded = json.loads(sync_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                payload = loaded
        except (json.JSONDecodeError, OSError):
            payload = {}
    payload["kicktipp"] = {
        "synced_at": datetime.now(tz=ZoneInfo("Europe/Berlin")).isoformat(),
        "status": status,
        "spieltag": spieltag,
        "tips_count": tips_count,
        "agent_rounds": agent_rounds or [],
        "mode": "auto" if os.environ.get("GITHUB_EVENT_NAME") == "schedule" else "manual",
        "error": error,
    }
    sync_path.parent.mkdir(parents=True, exist_ok=True)
    sync_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def parse_agent_matchday(round_name: str) -> int | None:
    match = re.search(r"matchday\s*(\d+)", round_name, re.IGNORECASE)
    return int(match.group(1)) if match else None


def agent_rounds_for_kicktipp_spieltag(kt: int) -> list[int]:
    """Kicktipp Spieltag k = k-te Gruppenspielrunde (je 3 chronologische Agent-Tage)."""
    return [3 * kt - 2, 3 * kt - 1, 3 * kt]


def kicktipp_spieltag(agent_matchday: int, mapping_path: Path = DEFAULT_SPIELTAG_MAP) -> int:
    """
    Mappt chronologischen Agent-Matchday N auf Kicktipp spieltagIndex.

    Kicktipp bündelt die k-te Gruppenspielrunde (8 Spiele), nicht den chronologischen Tag.
    Agent-Matchdays 1–3 → Kicktipp 1, 4–6 → 2, usw.
    """
    if mapping_path.exists():
        data = json.loads(mapping_path.read_text(encoding="utf-8"))
        explicit = data.get("matchdays") or {}
        key = str(agent_matchday)
        if key in explicit:
            return int(explicit[key])
    return (agent_matchday + 2) // 3


def load_all_predictions_from_history(
    history_dir: Path = DEFAULT_HISTORY,
) -> dict:
    """Alle archivierten Spieltipps für Kicktipp-Seitenfilterung zusammenführen."""
    predictions: list[dict] = []
    agent_rounds: list[str] = []
    for path in sorted(
        history_dir.glob("matchday-*.json"),
        key=lambda item: int(item.stem.rsplit("-", 1)[-1]),
    ):
        payload = json.loads(path.read_text(encoding="utf-8"))
        agent_rounds.append(payload.get("round", path.stem))
        predictions.extend(payload.get("predictions", []))
    return {
        "round": "All archived matchdays",
        "agent_rounds": agent_rounds,
        "predictions": predictions,
    }


def load_predictions_for_kicktipp_spieltag(
    kt: int,
    history_dir: Path = DEFAULT_HISTORY,
) -> dict:
    """Spieltipps aus Agent-Matchday-Archiven für einen Kicktipp-Spieltag zusammenführen."""
    predictions: list[dict] = []
    agent_rounds: list[str] = []
    for agent_md in agent_rounds_for_kicktipp_spieltag(kt):
        path = history_dir / f"matchday-{agent_md}.json"
        if not path.exists():
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        agent_rounds.append(payload.get("round", f"Matchday {agent_md}"))
        predictions.extend(payload.get("predictions", []))
    return {
        "round": f"Kicktipp Spieltag {kt}",
        "agent_rounds": agent_rounds,
        "predictions": predictions,
    }


def load_aliases(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Aliases must be a JSON object: {path}")
    return {str(k): str(v) for k, v in data.items()}


def kicktipp_team(name: str, aliases: dict[str, str]) -> str:
    return aliases.get(name, name)


def map_bonus_question(question: str) -> str:
    locale = os.environ.get("KICKTIPP_LOCALE", "de").lower()
    if locale != "de":
        return question
    if question in BONUS_QUESTION_DE:
        return BONUS_QUESTION_DE[question]
    group_match = re.match(r"Who wins Group ([A-L])\?", question, re.IGNORECASE)
    if group_match:
        return f"Wer gewinnt die Gruppe {group_match.group(1).upper()}?"
    return question


def kicktipp_pair_key(home: str, away: str) -> tuple[str, str]:
    return tuple(sorted([home, away]))


def align_bet_string(
    home: str,
    away: str,
    tip: str,
    kicktipp_home: str,
    kicktipp_away: str,
) -> str:
    if home == kicktipp_home and away == kicktipp_away:
        return f"{kicktipp_home} vs {kicktipp_away}={tip}"
    if home == kicktipp_away and away == kicktipp_home:
        return f"{kicktipp_home} vs {kicktipp_away}={tip}"
    return f"{kicktipp_home} vs {kicktipp_away}={tip}"


def fetch_kicktipp_tippabgabe_matches(spieltag: int) -> list[dict[str, str]]:
    script = DEFAULT_TIPPABGABE_JSON
    if not script.exists():
        print(f"Hinweis: {script} fehlt — keine Kicktipp-Seitenfilterung.", file=sys.stderr)
        return []

    agent_root = os.environ.get("KICKTIPP_AGENT_ROOT")
    if not agent_root:
        if (DEFAULT_AGENT_ROOT / "dist" / "browser.js").exists():
            agent_root = str(DEFAULT_AGENT_ROOT)
    env = os.environ.copy()
    if agent_root:
        env["KICKTIPP_AGENT_ROOT"] = agent_root

    result = subprocess.run(
        ["node", str(script), str(spieltag)],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )
    if result.returncode != 0:
        stderr = result.stderr.strip() or result.stdout.strip()
        print(f"Kicktipp-Tippabgabe-Abfrage fehlgeschlagen: {stderr}", file=sys.stderr)
        return []

    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        print("Kicktipp-Tippabgabe lieferte kein gültiges JSON.", file=sys.stderr)
        return []
    if not isinstance(payload, list):
        return []
    return [row for row in payload if row.get("home") and row.get("away")]


def match_bets_for_kicktipp_spieltag(
    payload: dict,
    aliases: dict[str, str],
    kicktipp_matches: list[dict[str, str]],
) -> tuple[list[str], list[str]]:
    """Baut Wetten nur für Spiele, die auf der Kicktipp-Tippabgabe-Seite stehen."""
    if not kicktipp_matches:
        return match_bets_from_predictions(payload, aliases), []

    indexed: dict[tuple[str, str], tuple[str, str]] = {}
    for row in kicktipp_matches:
        home = str(row["home"])
        away = str(row["away"])
        indexed[kicktipp_pair_key(home, away)] = (home, away)

    bets: list[str] = []
    skipped: list[str] = []
    for item in payload.get("predictions", []):
        if item.get("pending"):
            continue
        tip = item.get("tip")
        if not tip:
            continue
        home = kicktipp_team(item["home_team"], aliases)
        away = kicktipp_team(item["away_team"], aliases)
        key = kicktipp_pair_key(home, away)
        if key not in indexed:
            skipped.append(f"{home} vs {away} (nicht auf Kicktipp-Spieltag)")
            continue
        kt_home, kt_away = indexed[key]
        bets.append(align_bet_string(home, away, tip, kt_home, kt_away))
    return bets, skipped


def submit_match_bets(
    match_bets: list[str],
    *,
    spieltag: int | None,
    dry_run: bool,
) -> tuple[int, list[str]]:
    """Einzelne Wetten übertragen; ein Fehler stoppt nicht den ganzen Lauf."""
    submitted = 0
    failures: list[str] = []
    for bet in match_bets:
        cmd_args = ["bet", bet]
        if spieltag is not None:
            cmd_args.extend(["--matchday", str(spieltag)])
        code = run_kicktipp(cmd_args, dry_run=dry_run)
        if code != 0:
            failures.append(bet)
            continue
        submitted += 1
    return submitted, failures


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
        question = map_bonus_question(champion["question"])
        bets.append(f"{question}={pick}")

    scorer = payload.get("top_scorer_team") or {}
    if scorer.get("question") and scorer.get("pick"):
        pick = kicktipp_team(scorer["pick"], aliases)
        question = map_bonus_question(scorer["question"])
        bets.append(f"{question}={pick}")

    semi = payload.get("semi_finalists") or {}
    question = map_bonus_question(semi.get("question", ""))
    for pick in semi.get("picks") or []:
        bets.append(f"{question}={kicktipp_team(pick, aliases)}")

    for group in payload.get("group_winners") or []:
        if group.get("question") and group.get("pick"):
            pick = kicktipp_team(group["pick"], aliases)
            question = map_bonus_question(group["question"])
            bets.append(f"{question}={pick}")

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


def submit_spieltag_tips(
    kt_md: int,
    predictions_payload: dict,
    aliases: dict[str, str],
    *,
    community: str,
    dry_run: bool,
    bonus_only: bool,
) -> tuple[int, list[str], list[str], list[str]]:
    """Tipps für einen Kicktipp-Spieltag vorbereiten und übertragen."""
    if bonus_only:
        return 0, [], [], []

    kicktipp_matches: list[dict[str, str]] = []
    if not dry_run:
        kicktipp_matches = fetch_kicktipp_tippabgabe_matches(kt_md)
        if kicktipp_matches:
            print(f"Kicktipp-Seite Spieltag {kt_md}: {len(kicktipp_matches)} tippbare Spiele")
            for row in kicktipp_matches:
                print(f"  {row['home']} vs {row['away']}")

    match_bets, skipped_bets = match_bets_for_kicktipp_spieltag(
        predictions_payload,
        aliases,
        kicktipp_matches,
    )
    if skipped_bets:
        print(f"Übersprungen ({len(skipped_bets)}) — nicht auf Kicktipp-Spieltag {kt_md}:")
        for line in skipped_bets:
            print(f"  {line}")

    if not match_bets:
        print(f"Spieltag {kt_md}: keine abzugebenden Spieltipps.")
        return 0, [], [], skipped_bets

    print(f"Community: {community}")
    print(f"Spieltag {kt_md} — Spieltipps ({len(match_bets)}):")
    for bet in match_bets:
        print(f"  {bet}")

    tips_submitted, submit_failures = submit_match_bets(
        match_bets,
        spieltag=kt_md,
        dry_run=dry_run,
    )
    if submit_failures:
        print(f"Spieltag {kt_md} fehlgeschlagen ({len(submit_failures)}):")
        for bet in submit_failures:
            print(f"  {bet}")
    return tips_submitted, submit_failures, match_bets, skipped_bets


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
        help="Bonusfragen nicht übertragen (Standard in GitHub Actions)",
    )
    parser.add_argument(
        "--bonus-only",
        action="store_true",
        help="Nur Bonusfragen übertragen (Spieltipps überspringen)",
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
        help="Agent-Matchday-Nummer (Default: aus predictions.json round)",
    )
    parser.add_argument(
        "--kicktipp-spieltag",
        type=int,
        default=None,
        metavar="N",
        help="Kicktipp-Spieltag direkt (lädt Agent-Matchdays 3N-2 … 3N aus state/history)",
    )
    parser.add_argument(
        "--print-upcoming-spieltag",
        action="store_true",
        help="Nächsten Kicktipp-Spieltag (aus Spielplan) ausgeben und beenden",
    )
    parser.add_argument(
        "--record-kicktipp-skipped",
        action="store_true",
        help="Kicktipp-Überspringen in sync_status.json protokollieren und beenden",
    )
    parser.add_argument(
        "--skip-reason",
        type=str,
        default="Kein anstehender Kicktipp-Spieltag",
        help="Grund für --record-kicktipp-skipped",
    )
    parser.add_argument(
        "--all-group-spieltage",
        action="store_true",
        help="Alle Gruppenspieltage 1–6 übertragen (Standard für Cron)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Nur Befehle ausgeben, nichts abgeben",
    )
    args = parser.parse_args()

    if args.print_upcoming_spieltag:
        aliases = load_aliases(DEFAULT_ALIASES)
        kt = resolve_upcoming_kicktipp_spieltag(aliases=aliases)
        if kt is None:
            print("", end="")
            return 0
        print(kt)
        return 0

    if args.record_kicktipp_skipped:
        record_kicktipp_sync(
            status="skipped",
            spieltag=None,
            tips_count=0,
            error=args.skip_reason,
        )
        print(f"Kicktipp-Sync protokolliert: skipped ({args.skip_reason})")
        return 0

    if not args.dry_run:
        ensure_credentials()
        ensure_kicktipp_available()

    aliases = load_aliases(args.aliases)
    community = ensure_community(os.environ.get("KICKTIPP_COMMUNITY")) if not args.dry_run else os.environ.get("KICKTIPP_COMMUNITY", "(dry-run)")

    if args.bonus_only:
        args.no_bonus = False

    predictions_payload = load_all_predictions_from_history()
    agent_rounds = predictions_payload.get("agent_rounds") or []

    if args.all_group_spieltage:
        spieltage = list(range(1, 7))
        print(f"Kicktipp Gruppenspieltage 1–6 ({len(agent_rounds)} Agent-Archive)")
    elif args.kicktipp_spieltag:
        spieltage = [args.kicktipp_spieltag]
        print(
            f"Kicktipp-Spieltag {args.kicktipp_spieltag}: alle Agent-Archive ({len(agent_rounds)} Runden)"
        )
    elif args.matchday:
        spieltage = [kicktipp_spieltag(args.matchday)]
        print(
            f"Kicktipp-Spieltag {spieltage[0]}: Agent Matchday {args.matchday} "
            f"({len(agent_rounds)} Archive)"
        )
    else:
        kt_md = resolve_upcoming_kicktipp_spieltag(aliases=aliases)
        if kt_md is not None:
            spieltage = [kt_md]
            print(
                f"Kicktipp-Spieltag {kt_md} (nächstes Spiel): "
                f"{len(agent_rounds)} Agent-Archive"
            )
        else:
            spieltage = []
            predictions_payload = json.loads(args.predictions.read_text(encoding="utf-8"))
            agent_rounds = []
            print("Hinweis: Kein anstehender Spieltag — Fallback predictions.json")

    tips_submitted = 0
    submit_failures: list[str] = []
    spieltage_with_tips: list[int] = []

    for kt_md in spieltage:
        if kt_md != spieltage[0]:
            print()
        submitted, failures, match_bets, _skipped = submit_spieltag_tips(
            kt_md,
            predictions_payload,
            aliases,
            community=community,
            dry_run=args.dry_run,
            bonus_only=args.bonus_only,
        )
        tips_submitted += submitted
        submit_failures.extend(failures)
        if match_bets:
            spieltage_with_tips.append(kt_md)

    if not args.bonus_only and spieltage and tips_submitted == 0 and not submit_failures:
        if not args.dry_run:
            record_kicktipp_sync(
                status="skipped",
                spieltag=spieltage[0] if len(spieltage) == 1 else None,
                tips_count=0,
                agent_rounds=agent_rounds,
                error="Keine abzugebenden Spieltipps auf den gewählten Spieltagen",
            )
    elif not args.bonus_only and submit_failures and tips_submitted == 0:
        if not args.dry_run:
            record_kicktipp_sync(
                status="failed",
                spieltag=spieltage[0] if len(spieltage) == 1 else None,
                tips_count=0,
                agent_rounds=agent_rounds,
                error=f"{len(submit_failures)} Tipps fehlgeschlagen",
            )
        return 1
    elif not args.bonus_only and submit_failures:
        if not args.dry_run:
            record_kicktipp_sync(
                status="partial",
                spieltag=spieltage[0] if len(spieltage) == 1 else None,
                tips_count=tips_submitted,
                agent_rounds=agent_rounds,
                error=f"{len(submit_failures)} Tipps fehlgeschlagen",
            )

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
                if not args.dry_run:
                    record_kicktipp_sync(
                        status="failed",
                        spieltag=spieltage[0] if spieltage else None,
                        tips_count=tips_submitted,
                        agent_rounds=agent_rounds,
                        error=f"Bonus-Übertragung exit code {code}",
                    )
                return code
        else:
            print("Keine Bonusantworten in bonus.json.")
    elif not args.no_bonus:
        print("Keine bonus.json — Bonus übersprungen.")

    if not args.dry_run and (tips_submitted > 0 or args.bonus_only) and not submit_failures:
        record_kicktipp_sync(
            status="ok",
            spieltag=spieltage_with_tips[0] if len(spieltage_with_tips) == 1 else None,
            tips_count=tips_submitted,
            agent_rounds=agent_rounds,
        )

    if args.bonus_only and not spieltage:
        print("Nur Bonusfragen — Spieltipps übersprungen.")

    print("Kicktipp-Übertragung abgeschlossen.")
    return 1 if submit_failures and tips_submitted == 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
