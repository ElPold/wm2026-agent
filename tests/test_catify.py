"""Regression tests: Catify copy must stay hidden in normal mode."""

from __future__ import annotations

import json
import re
from html.parser import HTMLParser
from pathlib import Path

import pytest

from src.site.generator import build_site

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "site" / "templates"
STATIC_CSS = ROOT / "site" / "static" / "style.css"
SCRIPTS = TEMPLATES / "_scripts.html"
CAT_HEAD = TEMPLATES / "_cat_head.html"

TCAT_SPAN_RE = re.compile(
    r"<span\b(?P<attrs>[^>]*\bt-cat\b[^>]*)>",
    re.IGNORECASE,
)
HIDDEN_ATTR_RE = re.compile(r"\bhidden\b", re.IGNORECASE)
INLINE_FLEX_RULE_RE = re.compile(
    r"([^{}]+)\{[^}]*display\s*:\s*inline-flex",
    re.IGNORECASE | re.DOTALL,
)


class TCatSpanParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.spans: list[dict[str, str | None]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "span":
            return
        attr_map = dict(attrs)
        classes = attr_map.get("class", "") or ""
        if "t-cat" not in classes.split():
            return
        self.spans.append(attr_map)


def _find_t_cat_spans(html: str) -> list[dict[str, str | None]]:
    parser = TCatSpanParser()
    parser.feed(html)
    return parser.spans


def _template_html_files() -> list[Path]:
    return sorted(path for path in TEMPLATES.glob("*.html") if not path.name.startswith("_"))


@pytest.mark.parametrize("template_path", _template_html_files(), ids=lambda p: p.name)
def test_templates_mark_every_t_cat_hidden(template_path: Path) -> None:
    html = template_path.read_text(encoding="utf-8")
    matches = list(TCAT_SPAN_RE.finditer(html))
    assert matches, f"{template_path.name} should define Catify spans"

    missing = [match.group(0) for match in matches if not HIDDEN_ATTR_RE.search(match.group("attrs"))]
    assert not missing, (
        f"{template_path.name}: .t-cat spans must ship with hidden in normal mode:\n"
        + "\n".join(missing[:5])
    )


def test_partial_templates_mark_t_cat_hidden() -> None:
    for partial in ("_topbar.html", "_cat_head.html"):
        path = TEMPLATES / partial
        html = path.read_text(encoding="utf-8")
        for match in TCAT_SPAN_RE.finditer(html):
            assert HIDDEN_ATTR_RE.search(match.group("attrs")), f"{partial}: {match.group(0)}"


def test_css_keeps_global_hidden_rule() -> None:
    css = STATIC_CSS.read_text(encoding="utf-8")
    assert re.search(r"\[hidden\]\s*\{[^}]*display\s*:\s*none\s*!important", css, re.DOTALL)


def test_css_hides_t_cat_outside_cat_mode() -> None:
    css = STATIC_CSS.read_text(encoding="utf-8")
    assert re.search(
        r":not\(\.cat-mode\)\s+\.t-cat\s*\{[^}]*display\s*:\s*none\s*!important",
        css,
        re.DOTALL,
    )
    assert re.search(
        r"\.cat-mode\s+\.t-normal\s*\{[^}]*display\s*:\s*none\s*!important",
        css,
        re.DOTALL,
    )


def test_css_cat_label_flex_only_in_cat_mode() -> None:
    css = STATIC_CSS.read_text(encoding="utf-8")
    assert ".cat-mode .t-cat.cat-label-with-icon" in css
    for match in INLINE_FLEX_RULE_RE.finditer(css):
        selector = match.group(1).strip()
        if "cat-label-with-icon" in selector:
            assert ".cat-mode" in selector, f"Unscoped cat-label flex rule: {selector}"


def test_cat_head_includes_critical_hide_rules() -> None:
    head = CAT_HEAD.read_text(encoding="utf-8")
    assert ":not(.cat-mode) .t-cat" in head
    assert "wm2026-cat-mode" in head


def test_scripts_toggle_cat_mode_classes() -> None:
    scripts = SCRIPTS.read_text(encoding="utf-8")
    assert 'classList.toggle("cat-mode"' in scripts
    assert 'querySelectorAll(".t-cat")' in scripts
    assert 'querySelectorAll(".t-normal")' in scripts


def test_generated_site_catify_contract(tmp_path: Path) -> None:
    state = tmp_path / "state"
    history = state / "history"
    docs = tmp_path / "docs"
    history.mkdir(parents=True)

    payload = {
        "generated_at": "2026-06-09T18:29:46+02:00",
        "match_count": 1,
        "predictions": [
            {
                "fixture_id": "wc26-001",
                "home_team": "Mexico",
                "away_team": "South Africa",
                "kickoff_berlin": "2026-06-11T21:00:00+02:00",
                "venue": "Mexico City",
                "round": "Matchday 1",
                "bookmaker": "pinnacle",
                "tip": "1:0",
                "expected_points": 1.79,
                "most_likely_score": "1:0",
                "market_probs": {"home": 0.68, "draw": 0.21, "away": 0.11},
                "top_scores": [{"score": "1:0", "probability": 0.16}],
            }
        ],
    }
    predictions_path = state / "predictions.json"
    with predictions_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle)

    build_site(predictions_path=predictions_path, history_dir=history, output_dir=docs)

    for page in ("index.html", "track.html", "pipeline.html"):
        html = (docs / page).read_text(encoding="utf-8")
        assert "_cat_head.html" not in html
        assert ":not(.cat-mode) .t-cat" in html

        spans = _find_t_cat_spans(html)
        assert spans, f"{page} should contain .t-cat spans"
        visible = [span for span in spans if "hidden" not in span]
        assert not visible, f"{page}: every .t-cat must keep hidden in generated HTML"

        assert "WM 2026 Agent" in html
        assert "WM 2026 Cat Agent" in html

    css = (docs / "static" / "style.css").read_text(encoding="utf-8")
    assert ":not(.cat-mode) .t-cat" in css
