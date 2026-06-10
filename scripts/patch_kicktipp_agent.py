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
    patch_file(
        root / "src/commands/bet.ts",
        [
            (
                "await Promise.all([\n"
                "    page.waitForNavigation(),\n"
                "    page.click('button[name=\"submitbutton\"]'),\n"
                "  ]);",
                "await dismissConsent(page);\n"
                "  await page.locator('button[name=\"submitbutton\"]').scrollIntoViewIfNeeded();\n"
                "  await Promise.all([\n"
                "    page.waitForNavigation(),\n"
                "    page.click('button[name=\"submitbutton\"]', { force: true }),\n"
                "  ]);",
            ),
        ],
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
