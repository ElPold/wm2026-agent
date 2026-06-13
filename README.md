# WM 2026 Kicktipp-Agent

Automatisierter, EV-optimaler Tippgeber für die FIFA-Weltmeisterschaft 2026.

## Status: Phase 0 (MVP)

Funktionsnachweis der Kern-Pipeline:

```
Wettquoten (1X2 + O/U 2.5) → margenbereinigte Wahrscheinlichkeiten
  → Poisson-Kalibrierung → Ergebnisverteilung → EV-optimaler Kicktipp-Tipp
  → GitHub Pages Dashboard → optional Kicktipp-Abgabe (kicktipp.de)
```

## Schnellstart

```bash
cd wm2026-agent
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env    # API-Keys eintragen

python demo.py                    # Pipeline-Demo (ohne API)
python run.py --discover          # IDs & API-Verfügbarkeit prüfen
python run.py --round "Matchday 1"   # Tipps für einen Spieltag + Website
python run.py --date 2026-06-11   # Live-Tipps nach Kalenderdatum
python run.py --build-site        # nur Website neu generieren
pytest                            # Tests (52+)
```

## Website (GitHub Pages)

Nach jedem Tipp-Lauf wird `docs/` neu generiert. GitHub Pages einrichten:

1. Repo **Settings → Pages → Build and deployment**
2. Source: **Deploy from a branch**
3. Branch: **main**, Folder: **/docs**
4. URL: `https://elpold.github.io/wm2026-agent/`

### Dashboard-Aktionen

| Button | Zweck |
|--------|-------|
| **↻ Update matchday** | Öffnet Workflow **Update predictions** — Tipps neu generieren, Ergebnisse von Kicktipp laden, Site bauen |
| **→ Transfer to Kicktipp** (pro Matchday-Tab) | Öffnet Workflow **Kicktipp Spieltag N** — alle Agent-Tipps dieser Kicktipp-Runde abgeben |

Beide Buttons sind passwortgeschützt (Zugangstor für GitHub Actions, kein echtes Secret).

### Kicktipp-Spieltag-Mapping

Kicktipp bündelt die **k-te Gruppenspielrunde** (8 Spiele pro Seite), nicht chronologische Kalendertage.

| Agent Matchdays | Kicktipp Spieltag |
|-----------------|-------------------|
| 1, 2, 3 | 1 |
| 4, 5, 6 | 2 |
| 7, 8, 9 | 3 |
| … | `(matchday + 2) // 3` |

Der Button **Transfer to Kicktipp** überträgt immer den **gesamten** Kicktipp-Spieltag (merged aus `state/history/rounds/matchday-*.json`), nicht nur die Spiele des aktuellen Tabs.

## GitHub Actions

Unter **Settings → Secrets and variables → Actions**:

| Secret | Pflicht? | Beschreibung |
|--------|----------|--------------|
| `ODDSPAPI_API_KEY` | ja (für Tipps) | OddsPapi API-Key |
| `ODDSPAPI_TOURNAMENT_ID` | empfohlen | WM-ID (`16` für Nationalmannschaften) |
| `THE_ODDS_API_KEY` | optional | Fallback-Quotenquelle |
| `KICKTIPP_EMAIL` | nur bei Abgabe | Kicktipp-Login |
| `KICKTIPP_PASSWORD` | nur bei Abgabe | Kicktipp-Passwort |
| `KICKTIPP_COMMUNITY` | nur bei Abgabe | Community-Slug (z. B. `entertainment`) |

### Workflows

| Workflow | Auslöser | Zweck |
|----------|----------|-------|
| **Tests** | Push/PR auf `main` | `pytest` |
| **Update predictions** | manuell | Tipps generieren, Track record von Kicktipp aktualisieren; optional `submit_kicktipp` + `kicktipp_spieltag` |
| **Kicktipp Spieltag 1/2** | manuell (vom Dashboard-Button) | Nur Kicktipp-Abgabe, ohne Tipp-Neugenerierung |
| **Update track record** | täglich 05:00/23:00 UTC + manuell | Ergebnisse von Kicktipp → `state/results.json` + Site |
| **Check fixture odds** | manuell | Quoten-Diagnose für einzelne Spiele |

### Kicktipp-Abgabe

Deutsche Runden laufen auf **kicktipp.de** mit `/tippabgabe` (nicht kicktipp.com/predict). Der Workflow patcht [kicktipp-agent](https://github.com/christianheidorn/kicktipp-agent) automatisch (`scripts/patch_kicktipp_agent.py`). Teamnamen werden über `config/kicktipp_aliases.json` gemappt.

```bash
# Vollständigen Kicktipp-Spieltag 1 abgeben (MD 1+2+3 aus History)
python scripts/submit_kicktipp.py --kicktipp-spieltag 1 --no-bonus

# Dry-run (keine Abgabe)
python scripts/submit_kicktipp.py --kicktipp-spieltag 1 --dry-run
```

**Bonusfragen** sind einmalig — CI nutzt `--no-bonus`; manuell nur noch mit `--bonus-only`.

Quoten-Check: `python scripts/check_fixture_odds.py --home Australia --away Turkey`

Secrets aus `.env` setzen:

```bash
gh secret set ODDSPAPI_API_KEY --repo ElPold/wm2026-agent < <(grep '^ODDSPAPI_API_KEY=' .env | cut -d= -f2-)
gh secret set ODDSPAPI_TOURNAMENT_ID --repo ElPold/wm2026-agent < <(grep '^ODDSPAPI_TOURNAMENT_ID=' .env | cut -d= -f2-)
```

## Datenquellen

| Was | Quelle | Key nötig? |
|-----|--------|------------|
| **Spielplan** (104 Spiele) | [openfootball/worldcup.json](https://github.com/openfootball/worldcup.json) | nein — liegt in `data/schedule/` |
| **Quoten** (1X2 + O/U 2.5) | [OddsPapi](https://oddspapi.io) | ja — `ODDSPAPI_API_KEY` |
| **Quoten-Fallback** | [The Odds API](https://the-odds-api.com) | optional |
| Ergebnisse (Track record) | Kicktipp-Spielplan (`/schedule`) | Kicktipp-Login + `KICKTIPP_COMMUNITY` |

Spielplan aktualisieren: `python scripts/fetch_schedule.py`

Track record (Ergebnisse + Punkte auf `track.html`):

```bash
python scripts/fetch_results.py          # schreibt state/results.json
python run.py --fetch-results            # fetch + Site neu bauen
```

## Projektstruktur

```
wm2026-agent/
├── config/               # kicktipp_aliases.json, kicktipp_spieltag.json
├── data/schedule/        # openfootball Spielplan
├── docs/                 # generierte GitHub Pages (nicht von Hand editieren)
├── scripts/              # submit_kicktipp, patch_kicktipp_agent, check_fixture_odds
├── site/templates/       # Jinja2-Templates für das Dashboard
├── state/                # predictions.json, results.json, history/rounds/, bonus.json
├── src/
│   ├── sources/          # openfootball, OddsPapi, The Odds API
│   ├── pipeline/         # Tages-Tipps erzeugen
│   ├── model/            # Quoten, Poisson, Kalibrierung
│   ├── optimizer/        # Kicktipp-Punkte, EV-Optimierer
│   └── site/             # Static-Site-Generator
├── tests/                # pytest (52 Tests)
├── demo.py
└── run.py                # CLI: --round, --date, --build-site
```

## Nächste Schritte (Phase 0)

- [x] OddsPapi-Anbindung (+ The Odds API Fallback)
- [x] Spielplan via openfootball (lokal, Berlin-Zeitzone)
- [x] Statische Website (GitHub Pages, `docs/`)
- [x] GitHub Actions (Tipps + Kicktipp-Abgabe)
- [x] CI-Tests (`test.yml`)
- [ ] GitHub Actions Cron (automatischer Tipp-Lauf)
