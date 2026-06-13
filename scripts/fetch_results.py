#!/usr/bin/env python3
"""Lädt abgeschlossene Spielergebnisse von Kicktipp und schreibt state/results.json."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.pipeline.results import (  # noqa: E402
    fixture_index_for_schedule,
    kicktipp_rows_to_results,
    load_results,
    merge_results,
    save_results,
)

URL_BASE = os.environ.get("KICKTIPP_BASE_URL", "https://www.kicktipp.de")
URL_LOGIN = f"{URL_BASE}/info/profil/login"
DEFAULT_RESULTS = ROOT / "state" / "results.json"
DEFAULT_ALIASES = ROOT / "config" / "kicktipp_aliases.json"
DEFAULT_AGENT_ROOT = ROOT / ".kicktipp-agent"
SCHEDULE_JSON_SCRIPT = ROOT / "scripts" / "kicktipp_schedule_json.mjs"


def kicktipp_agent_root() -> Path | None:
    custom = os.environ.get("KICKTIPP_AGENT_ROOT")
    if custom:
        path = Path(custom)
        return path if (path / "dist" / "browser.js").exists() else None
    if (DEFAULT_AGENT_ROOT / "dist" / "browser.js").exists():
        return DEFAULT_AGENT_ROOT
    return None


def fetch_rows_via_kicktipp_agent(matchdays: str) -> list[dict[str, str]]:
    agent_root = kicktipp_agent_root()
    if not agent_root or not SCHEDULE_JSON_SCRIPT.exists():
        return []

    env = os.environ.copy()
    env["KICKTIPP_AGENT_ROOT"] = str(agent_root)
    result = subprocess.run(
        ["node", str(SCHEDULE_JSON_SCRIPT), matchdays],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )
    if result.returncode != 0:
        stderr = result.stderr.strip() or result.stdout.strip()
        print(f"kicktipp-agent schedule dump fehlgeschlagen: {stderr}", file=sys.stderr)
        return []

    payload = json.loads(result.stdout)
    return [
        {
            "date": row.get("date", ""),
            "home": row["home"],
            "away": row["away"],
            "result": row["result"],
        }
        for row in payload
    ]


def dismiss_consent(page) -> None:
    try:
        page.wait_for_selector('iframe[src*="privacy-mgmt"]', timeout=2000)
        for frame in page.frames:
            for label in ("Accept and continue", "Akzeptieren und weiter"):
                btn = frame.query_selector(f'button:has-text("{label}")')
                if btn:
                    btn.click()
                    page.wait_for_selector(
                        'iframe[src*="privacy-mgmt"]', state="hidden", timeout=3000
                    )
                    return
    except Exception:
        pass


def login(page, email: str, password: str) -> None:
    page.goto(URL_LOGIN)
    page.wait_for_load_state("domcontentloaded")
    dismiss_consent(page)
    page.fill('input[name="kennung"]', email)
    page.fill('input[name="passwort"]', password)
    with page.expect_navigation():
        page.click('button[type="submit"]')
    if "/login" in page.url:
        raise RuntimeError("Kicktipp-Login fehlgeschlagen.")


def schedule_overview_segment() -> str:
    """kicktipp.de nutzt /tippuebersicht, kicktipp.com /schedule."""
    if "kicktipp.de" in URL_BASE:
        return "tippuebersicht"
    return "schedule"


def schedule_table_selector(page) -> str | None:
    for selector in ("table#spielplanSpiele", "table#spiele"):
        if page.locator(selector).count():
            return selector
    return None


def _result_from_cell(result_cell) -> str:
    home_goals = ""
    away_goals = ""
    if result_cell.locator("span.kicktipp-heim").count():
        home_goals = result_cell.locator("span.kicktipp-heim").inner_text().strip()
    if result_cell.locator("span.kicktipp-gast").count():
        away_goals = result_cell.locator("span.kicktipp-gast").inner_text().strip()
    if home_goals and away_goals:
        return f"{home_goals}:{away_goals}"
    text = result_cell.inner_text().strip().replace(" ", "")
    if text and text not in {"-:-", "–:–"}:
        return text
    return "-:-"


def parse_schedule_page(page, table_selector: str) -> list[dict[str, str]]:
    german = table_selector == "table#spielplanSpiele"
    rows: list[dict[str, str]] = []
    table = page.locator(f"{table_selector} tbody tr")
    for index in range(table.count()):
        cells = table.nth(index).locator("td")
        if german:
            if cells.count() < 4:
                continue
            date = cells.nth(0).inner_text().strip()
            home = cells.nth(1).inner_text().strip()
            away = cells.nth(2).inner_text().strip()
            result_cell = cells.nth(4) if cells.count() >= 5 else cells.nth(3)
        else:
            if cells.count() < 5:
                continue
            date = cells.nth(0).inner_text().strip()
            home = cells.nth(2).inner_text().strip()
            away = cells.nth(3).inner_text().strip()
            result_cell = cells.nth(4)
        rows.append(
            {
                "date": date,
                "home": home,
                "away": away,
                "result": _result_from_cell(result_cell),
            }
        )
    return rows


def fetch_schedule_matchdays_playwright(
    community: str,
    matchdays: range,
    *,
    no_login: bool,
) -> list[dict[str, str]]:
    from playwright.sync_api import sync_playwright

    email = os.environ.get("KICKTIPP_EMAIL", "")
    password = os.environ.get("KICKTIPP_PASSWORD", "")
    rows: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 2400})
        if not no_login:
            login(page, email, password)
        overview = schedule_overview_segment()
        for md in matchdays:
            url = f"{URL_BASE}/{community}/{overview}?spieltagIndex={md}"
            page.goto(url)
            page.wait_for_load_state("domcontentloaded")
            dismiss_consent(page)
            try:
                page.wait_for_selector(
                    "table#spielplanSpiele, table#spiele",
                    timeout=5000,
                )
            except Exception:
                continue
            table_selector = schedule_table_selector(page)
            if not table_selector:
                continue
            for row in parse_schedule_page(page, table_selector):
                key = (row["date"], row["home"], row["away"])
                if key in seen:
                    continue
                seen.add(key)
                rows.append(row)
        browser.close()
    return rows


def parse_matchday_range(value: str) -> range:
    if "-" in value:
        start, end = value.split("-", 1)
        return range(int(start), int(end) + 1)
    day = int(value)
    return range(day, day + 1)


def fetch_schedule_rows(matchdays: str, community: str, *, no_login: bool) -> list[dict[str, str]]:
    rows = fetch_rows_via_kicktipp_agent(matchdays)
    if rows:
        print(f"Quelle: kicktipp-agent ({len(rows)} Zeilen)")
        return rows

    print("Quelle: Playwright-Fallback", file=sys.stderr)
    try:
        return fetch_schedule_matchdays_playwright(
            community,
            parse_matchday_range(matchdays),
            no_login=no_login,
        )
    except ImportError:
        print(
            "Weder kicktipp-agent noch Playwright verfügbar. "
            "kicktipp-agent bauen oder: pip install playwright",
            file=sys.stderr,
        )
        return []


def main() -> int:
    parser = argparse.ArgumentParser(description="Kicktipp-Ergebnisse nach state/results.json")
    parser.add_argument("--community", default=os.environ.get("KICKTIPP_COMMUNITY"))
    parser.add_argument(
        "--matchdays",
        default="1-18",
        help="Kicktipp-Spieltage zum Abfragen, z. B. 1-18 oder 5",
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_RESULTS)
    parser.add_argument("--aliases", type=Path, default=DEFAULT_ALIASES)
    parser.add_argument(
        "--no-login",
        action="store_true",
        help="Nur für Playwright-Fallback ohne Login",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Nur anzeigen, results.json nicht schreiben",
    )
    args = parser.parse_args()

    load_dotenv(ROOT / ".env")
    community = args.community or os.environ.get("KICKTIPP_COMMUNITY", "")
    if not community:
        print("KICKTIPP_COMMUNITY in .env setzen oder --community nutzen.", file=sys.stderr)
        return 1

    if not args.no_login and not (
        os.environ.get("KICKTIPP_EMAIL") and os.environ.get("KICKTIPP_PASSWORD")
    ):
        print(
            "Hinweis: Ohne KICKTIPP_EMAIL/PASSWORD nur öffentlicher Playwright-Fallback.",
            file=sys.stderr,
        )
        args.no_login = True

    fixture_index = fixture_index_for_schedule(aliases_path=args.aliases)
    rows = fetch_schedule_rows(args.matchdays, community, no_login=args.no_login)

    if not rows:
        print(
            f"Warnung: Keine Spiele auf Kicktipp-Schedule gefunden "
            f"(Community {community!r}, Spieltage {args.matchdays}). "
            "KICKTIPP_COMMUNITY prüfen oder kicktipp-agent installieren.",
            file=sys.stderr,
        )

    incoming = kicktipp_rows_to_results(rows, fixture_index)
    existing = load_results(args.output)
    merged = merge_results(existing, incoming)

    new_count = len(incoming)
    total_known = len(merged)
    print(f"Kicktipp-Zeilen: {len(rows)}")
    print(f"Neue/zugeordnete Ergebnisse: {new_count}")
    print(f"Ergebnisse gesamt in {args.output.name}: {total_known}")

    for fixture_id in sorted(merged):
        entry = merged[fixture_id]
        if fixture_id in incoming:
            print(f"  {fixture_id}: {entry['score']}")

    if args.dry_run:
        return 0

    save_results(args.output, merged)
    print(f"Geschrieben → {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
