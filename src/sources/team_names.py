"""Teamnamen-Normalisierung für Quoten-Matching."""

from __future__ import annotations

import re
import unicodedata

# Kanonischer Name → bekannte Varianten (OddsPapi, The Odds API, openfootball)
TEAM_ALIASES: dict[str, list[str]] = {
    "usa": ["united states", "u s a", "us"],
    "south korea": ["korea republic", "korea rep", "republic of korea"],
    "dr congo": [
        "democratic republic of the congo",
        "democratic republic of congo",
        "congo dr",
        "drc",
    ],
    "ivory coast": ["cote d ivoire", "cote divoire", "côte d'ivoire"],
    "bosnia herzegovina": ["bosnia & herzegovina", "bosnia and herzegovina"],
    "cape verde": ["cabo verde"],
    "curacao": ["curaçao"],
    "turkey": ["turkiye", "türkiye"],
    "czech republic": ["czechia"],
    "bosnia herzegovina": ["bosnia and herzegovina"],
}


def normalize_team_name(name: str) -> str:
    normalized = unicodedata.normalize("NFKD", name.lower())
    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def canonical_team_key(name: str) -> str:
    """Reduziert Teamnamen auf einen kanonischen Schlüssel."""
    base = normalize_team_name(name)

    for canonical, aliases in TEAM_ALIASES.items():
        if base == canonical or base in aliases:
            return canonical

    return base


def teams_match(left: str, right: str) -> bool:
    a = canonical_team_key(left)
    b = canonical_team_key(right)
    if not a or not b:
        return False
    return a == b or a in b or b in a


def is_placeholder_team(name: str) -> bool:
    """K.-o.-Platzhalter wie 2A, W101, 3rd Group A/B/…"""
    cleaned = name.strip()
    if re.match(r"^[WL]\d+", cleaned, re.IGNORECASE):
        return True
    if re.match(r"^\d", cleaned):
        return True
    lowered = cleaned.lower()
    if "3rd" in lowered or "runner" in lowered:
        return True
    return False


def is_tippable_match(home_team: str, away_team: str) -> bool:
    return not is_placeholder_team(home_team) and not is_placeholder_team(away_team)
