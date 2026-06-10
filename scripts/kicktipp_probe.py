#!/usr/bin/env python3
"""Kicktipp-Spielnamen und Spieltage abfragen (Diagnose für submit_kicktipp)."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
URL_BASE = os.environ.get("KICKTIPP_BASE_URL", "https://www.kicktipp.de")
URL_LOGIN = f"{URL_BASE}/info/profil/login"


def predict_url(community: str, matchday: int | None = None) -> str:
    base = f"{URL_BASE}/{community}/tippabgabe"
    if matchday is None:
        return base
    return f"{base}?spieltagIndex={matchday}"


def dismiss_consent(page) -> None:
    try:
        page.wait_for_selector('iframe[src*="privacy-mgmt"]', timeout=2000)
        for frame in page.frames:
            btn = frame.query_selector('button:has-text("Accept and continue")')
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


def parse_matches(html: str) -> list[dict]:
    from html.parser import HTMLParser

    class Parser(HTMLParser):
        def __init__(self):
            super().__init__()
            self.rows: list[dict] = []
            self._in_tbody = False
            self._in_row = False
            self._cells: list[str] = []
            self._cell_text: list[str] = []
            self._in_td = False
            self._editable = False
            self._current: dict | None = None

        def handle_starttag(self, tag, attrs):
            attrs_d = dict(attrs)
            if tag == "tbody":
                self._in_tbody = True
            if self._in_tbody and tag == "tr":
                self._in_row = True
                self._cells = []
            if self._in_row and tag == "td":
                self._in_td = True
                self._cell_text = []
                classes = attrs_d.get("class", "")
                if "nichttippbar" in classes:
                    self._editable = False
            if self._in_td and tag == "input" and attrs_d.get("id", "").endswith("_heimTipp"):
                self._editable = True

        def handle_endtag(self, tag):
            if tag == "td" and self._in_td:
                self._cells.append(" ".join(self._cell_text).strip())
                self._in_td = False
            if tag == "tr" and self._in_row:
                if len(self._cells) >= 3 and self._editable:
                    self.rows.append(
                        {
                            "date": self._cells[0],
                            "home": self._cells[1],
                            "away": self._cells[2],
                            "editable": True,
                        }
                    )
                self._in_row = False
                self._editable = False
            if tag == "tbody":
                self._in_tbody = False

        def handle_data(self, data):
            if self._in_td:
                self._cell_text.append(data.strip())

    parser = Parser()
    parser.feed(html)
    return parser.rows


def fetch_matchdays(page, community: str, matchdays: range) -> dict[int, list[dict]]:
    result: dict[int, list[dict]] = {}
    for md in matchdays:
        page.goto(predict_url(community, md))
        page.wait_for_load_state("domcontentloaded")
        dismiss_consent(page)
        title = page.locator("#kicktipp-content div.pagetitle").inner_text(timeout=3000)
        matches = parse_matches(page.content())
        result[md] = matches
        print(f"Spieltag {md}: {title!r} — {len(matches)} tippbare Spiele")
        for m in matches:
            print(f"  {m['home']} vs {m['away']}")
    return result


def load_prediction_teams(path: Path) -> tuple[str, list[tuple[str, str]]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    teams = [
        (p["home_team"], p["away_team"])
        for p in payload.get("predictions", [])
        if not p.get("pending") and p.get("tip")
    ]
    return payload.get("round", ""), teams


def suggest_aliases(
    kicktipp_pairs: set[tuple[str, str]], agent_pairs: list[tuple[str, str]]
) -> dict[str, str]:
    aliases: dict[str, str] = {}

    def norm(s: str) -> str:
        return re.sub(r"[^a-z0-9]+", "", s.lower())

    kicktipp_names = {name for home, away in kicktipp_pairs for name in (home, away)}
    kicktipp_by_norm = {norm(name): name for name in kicktipp_names}

    agent_names = {name for home, away in agent_pairs for name in (home, away)}
    for name in sorted(agent_names):
        if name in kicktipp_names:
            continue
        if norm(name) in kicktipp_by_norm:
            aliases[name] = kicktipp_by_norm[norm(name)]
            continue
        for ktipp in kicktipp_names:
            n_name, n_ktipp = norm(name), norm(ktipp)
            if n_name in n_ktipp or n_ktipp in n_name:
                aliases[name] = ktipp
                break
    return aliases


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--community", default=os.environ.get("KICKTIPP_COMMUNITY"))
    parser.add_argument("--matchdays", default="1-8", help="z. B. 1-8 oder 5")
    parser.add_argument(
        "--predictions",
        type=Path,
        default=ROOT / "state" / "predictions.json",
    )
    parser.add_argument(
        "--write-aliases",
        type=Path,
        default=ROOT / "config" / "kicktipp_aliases.json",
    )
    args = parser.parse_args()

    load_dotenv(ROOT / ".env")
    email = os.environ.get("KICKTIPP_EMAIL", "")
    password = os.environ.get("KICKTIPP_PASSWORD", "")
    community = args.community or os.environ.get("KICKTIPP_COMMUNITY", "")
    if not email or not password or not community:
        print("KICKTIPP_EMAIL, KICKTIPP_PASSWORD, KICKTIPP_COMMUNITY in .env setzen.", file=sys.stderr)
        return 1

    if "-" in args.matchdays:
        start, end = args.matchdays.split("-", 1)
        days = range(int(start), int(end) + 1)
    else:
        days = range(int(args.matchdays), int(args.matchdays) + 1)

    round_name, agent_pairs = load_prediction_teams(args.predictions)
    print(f"Agent-Runde: {round_name}")
    for home, away in agent_pairs:
        print(f"  Agent: {home} vs {away}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        login(page, email, password)
        print(f"\nCommunity: {community}\n")
        by_day = fetch_matchdays(page, community, days)
        browser.close()

    kicktipp_pairs = {
        (m["home"], m["away"]) for matches in by_day.values() for m in matches
    }
    aliases = suggest_aliases(kicktipp_pairs, agent_pairs)
    if aliases:
        print("\nVorgeschlagene Aliases:")
        for k, v in sorted(aliases.items()):
            print(f"  {k!r} -> {v!r}")
        args.write_aliases.parent.mkdir(parents=True, exist_ok=True)
        existing = {}
        if args.write_aliases.exists():
            existing = json.loads(args.write_aliases.read_text(encoding="utf-8"))
        existing.update(aliases)
        args.write_aliases.write_text(
            json.dumps(existing, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(f"\nGeschrieben: {args.write_aliases}")
    else:
        print("\nKeine Aliases nötig (Namen stimmen überein oder keine Treffer).")

    md = None
    m = re.search(r"matchday\s*(\d+)", round_name, re.I)
    if m:
        md = int(m.group(1))
    if md and by_day.get(md):
        print(f"\nPassender Kicktipp-Spieltag für {round_name}: {md}")
    else:
        for day, matches in by_day.items():
            kt = {(m["home"], m["away"]) for m in matches}
            if any((aliases.get(h, h), aliases.get(a, a)) in kt or (h, a) in kt for h, a in agent_pairs):
                print(f"\nVermutlicher Kicktipp-Spieltag: {day}")
                break

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
