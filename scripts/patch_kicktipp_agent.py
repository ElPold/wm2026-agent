#!/usr/bin/env python3
"""Patch kicktipp-agent für deutsche Kicktipp-Instanz (kicktipp.de)."""

from __future__ import annotations

import sys
from pathlib import Path


def patch_file(path: Path, replacements: list[tuple[str, str]]) -> None:
    text = path.read_text(encoding="utf-8")
    for old, new in replacements:
        if old not in text:
            raise SystemExit(f"Patch-Ziel nicht gefunden in {path}: {old[:60]!r}...")
        text = text.replace(old, new)
    path.write_text(text, encoding="utf-8")
    print(f"Gepatcht: {path}")


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".kicktipp-agent")

    patch_file(
        root / "src/url.ts",
        [
            ("https://www.kicktipp.com", "https://www.kicktipp.de"),
            ("/predict", "/tippabgabe"),
        ],
    )
    patch_file(
        root / "src/browser.ts",
        [
            ("height: 900", "height: 2400"),
            (
                'const btn = await frame.$(\'button:has-text("Accept and continue")\');',
                'let btn = await frame.$(\'button:has-text("Accept and continue")\');\n'
                '      if (!btn) btn = await frame.$(\'button:has-text("Akzeptieren und weiter")\');',
            ),
        ],
    )
    bet_ts = root / "src/commands/bet.ts"
    bet_text = bet_ts.read_text(encoding="utf-8")
    bet_text = bet_text.replace("/predict?bonus=true", "/tippabgabe?bonus=true")
    submit_old = (
        "await Promise.all([\n"
        "    page.waitForNavigation(),\n"
        "    page.click('button[name=\"submitbutton\"]'),\n"
        "  ]);"
    )
    submit_new = (
        "await dismissConsent(page);\n"
        "  await page.locator('button[name=\"submitbutton\"]').scrollIntoViewIfNeeded();\n"
        "  await Promise.all([\n"
        "    page.waitForNavigation(),\n"
        "    page.click('button[name=\"submitbutton\"]', { force: true }),\n"
        "  ]);"
    )
    if submit_old not in bet_text:
        raise SystemExit("Submit-Button-Patch in bet.ts nicht gefunden.")
    bet_text = bet_text.replace(submit_old, submit_new)
    bet_ts.write_text(bet_text, encoding="utf-8")
    print(f"Gepatcht: {bet_ts}")
    patch_file(
        root / "src/core.ts",
        [
            (
                "let url = `${URL_BASE}/${encodeURIComponent(community)}/schedule`;",
                "let url = `${URL_BASE}/${encodeURIComponent(community)}/tippuebersicht`;",
            ),
            (
                "  const table = content.find('table#spiele');\n"
                "  if (!table.length) return { title, matches: [] };\n"
                "  const tbody = table.find('tbody');\n"
                "  if (!tbody.length) return { title, matches: [] };\n"
                "\n"
                "  const matches: ScheduleMatch[] = [];\n"
                "  tbody.children('tr').each((_, tr) => {\n"
                "    const cols = $(tr).children('td');\n"
                "    if (cols.length < 5) return;\n"
                "    const date = $(cols[0]).text().trim();\n"
                "    const home = $(cols[2]).text().trim();\n"
                "    const away = $(cols[3]).text().trim();\n"
                "    const resultSpan = $(cols[4]).find('span.kicktipp-ergebnis');\n"
                "    let result: string;\n"
                "    if (resultSpan.length) {\n"
                "      const h = resultSpan.find('span.kicktipp-heim').text().trim();\n"
                "      const g = resultSpan.find('span.kicktipp-gast').text().trim();\n"
                "      result = `${h}:${g}`;\n"
                "    } else {\n"
                "      result = '-:-';\n"
                "    }\n"
                "    matches.push({ date, home, away, result });\n"
                "  });",
                "  const table = content.find('table#spielplanSpiele, table#spiele');\n"
                "  if (!table.length) return { title, matches: [] };\n"
                "  const tbody = table.find('tbody');\n"
                "  if (!tbody.length) return { title, matches: [] };\n"
                "  const german = table.is('#spielplanSpiele');\n"
                "\n"
                "  const matches: ScheduleMatch[] = [];\n"
                "  tbody.children('tr').each((_, tr) => {\n"
                "    const cols = $(tr).children('td');\n"
                "    if (german ? cols.length < 4 : cols.length < 5) return;\n"
                "    const date = $(cols[0]).text().trim();\n"
                "    const home = german ? $(cols[1]).text().trim() : $(cols[2]).text().trim();\n"
                "    const away = german ? $(cols[2]).text().trim() : $(cols[3]).text().trim();\n"
                "    const resultCell = german ? $(cols[cols.length >= 5 ? 4 : 3]) : $(cols[4]);\n"
                "    const resultSpan = resultCell.find('span.kicktipp-ergebnis');\n"
                "    let result: string;\n"
                "    if (resultSpan.length) {\n"
                "      const h = resultSpan.find('span.kicktipp-heim').text().trim();\n"
                "      const g = resultSpan.find('span.kicktipp-gast').text().trim();\n"
                "      result = `${h}:${g}`;\n"
                "    } else {\n"
                "      const text = resultCell.text().trim().replace(/\\s+/g, '');\n"
                "      result = text && text !== '-:-' ? text : '-:-';\n"
                "    }\n"
                "    matches.push({ date, home, away, result });\n"
                "  });",
            ),
        ],
    )
    schedule_cmd = root / "src/commands/schedule.ts"
    if schedule_cmd.exists():
        patch_file(
            schedule_cmd,
            [
                (
                    "let url = `${URL_BASE}/${community}/schedule`;",
                    "let url = `${URL_BASE}/${community}/tippuebersicht`;",
                ),
            ],
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
