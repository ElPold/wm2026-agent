# WM 2026 Kicktipp-Agent

Automatisierter, EV-optimaler Tippgeber für die FIFA-Weltmeisterschaft 2026.

## Status: Phase 0 (MVP, live)

Funktionsnachweis der Kern-Pipeline:

```
Wettquoten (1X2 + O/U 2.5) → margenbereinigte Wahrscheinlichkeiten
  → Poisson-Kalibrierung → Ergebnisverteilung → EV-optimaler Kicktipp-Tipp
  → GitHub Pages Dashboard → automatische Kicktipp-Abgabe (kicktipp.de)
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
python run.py --all-rounds        # Alle Vorrunden-Tipps aktualisieren
python run.py --date 2026-06-11   # Live-Tipps nach Kalenderdatum
python run.py --build-site        # nur Website neu generieren
pytest                            # Tests (89)
```

## Website (GitHub Pages)

Nach jedem Tipp-Lauf wird `docs/` neu generiert. GitHub Pages einrichten:

1. Repo **Settings → Pages → Build and deployment**
2. Source: **Deploy from a branch**
3. Branch: **main**, Folder: **/docs**
4. URL: `https://elpold.github.io/wm2026-agent/`

### Seiten

| Seite | Inhalt |
|-------|--------|
| **Dashboard** | Alle 17 Vorrunden-Tabs, EV-Tipps, Sync-Status, Kicktipp-Buttons |
| **Track record** | Alle Spiele mit Agent-Tipp, Ergebnis, Punkten (2/3/4) + **Punktesumme** in der Tabelle |
| **Bonus tips** | Langzeit-Bonusfragen (Weltmeister, Gruppensieger …) |
| **How it works** | Pipeline-Erklärung |

### Dashboard-Aktionen

| Button | Zweck |
|--------|-------|
| **↻ Update matchday** | Workflow **Update predictions** — Tipps neu generieren, Ergebnisse laden, Site bauen |
| **→ Transfer to Kicktipp** (pro Matchday-Tab) | Workflow **Kicktipp Spieltag N** — manuelle Abgabe für einen Spieltag |

Beide Buttons sind passwortgeschützt (Zugangstor für GitHub Actions, kein echtes Secret).

### Sync-Status (Dashboard)

Zeigt letztes Tipps-Update und letzte Kicktipp-Übertragung aus `state/sync_status.json` (Zeitstempel, Spieltag, Anzahl Tipps, Status `ok` / `partial` / `failed` / `skipped`).

### Kicktipp-Spieltag-Mapping

Kicktipp bündelt die **k-te Gruppenspielrunde** (8 Spiele pro Seite), nicht chronologische Kalendertage.

| Agent Matchdays | Kicktipp Spieltag |
|-----------------|-------------------|
| 1, 2, 3 | 1 |
| 4, 5, 6 | 2 |
| 7, 8, 9 | 3 |
| … | `(matchday + 2) // 3` |

**Wichtig:** Die Spiele auf einem Kicktipp-Spieltag entsprechen nicht exakt den Agent-Matchdays 1–3. Der Submit liest die **tatsächlich tippbaren Spiele** von kicktipp.de und matched sie gegen alle archivierten Agent-Tipps.

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
| **Update predictions** | **Cron 10:00 + 16:00 MESZ** + manuell | Tipps (`--all-rounds`), Ergebnisse, **Kicktipp-Abgabe aller Gruppenspieltage 1–6**, Site-Build + Push |
| **Kicktipp Spieltag** | manuell (Dashboard-Button) | Nur Kicktipp-Abgabe für einen Spieltag |
| **Update track record** | täglich 05:00/23:00 UTC + manuell | Ergebnisse von Kicktipp → `state/results.json` + Site |
| **Check fixture odds** | manuell | Quoten-Diagnose für einzelne Spiele |

### Kicktipp-Abgabe (automatisch + manuell)

Deutsche Runden laufen auf **kicktipp.de** mit `/tippabgabe`. Der Workflow patcht [kicktipp-agent](https://github.com/christianheidorn/kicktipp-agent) automatisch (`scripts/patch_kicktipp_agent.py`). Teamnamen werden über `config/kicktipp_aliases.json` gemappt.

**Cron-Ablauf** (`scripts/submit_kicktipp.py --all-group-spieltage`):

1. Alle archivierten Tipps aus `state/history/rounds/` laden
2. Für jeden Kicktipp-Spieltag 1–6: tippbare Spiele von der Kicktipp-Seite lesen
3. Nur passende Tipps **einzeln** übertragen (ein Fehler stoppt nicht den ganzen Lauf)
4. Status in `state/sync_status.json` protokollieren

```bash
# Alle Gruppenspieltage (wie Cron)
python scripts/submit_kicktipp.py --all-group-spieltage --no-bonus

# Einzelnen Kicktipp-Spieltag
python scripts/submit_kicktipp.py --kicktipp-spieltag 3 --no-bonus

# Dry-run (keine Abgabe)
python scripts/submit_kicktipp.py --kicktipp-spieltag 3 --dry-run
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
| Ergebnisse (Track record) | Kicktipp (`/tippuebersicht`) | Kicktipp-Login + `KICKTIPP_COMMUNITY` |

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
├── scripts/              # submit_kicktipp, fetch_results, patch_kicktipp_agent, …
├── site/templates/       # Jinja2-Templates für das Dashboard
├── state/                # predictions.json, results.json, sync_status.json, history/rounds/
├── src/
│   ├── sources/          # openfootball, OddsPapi, The Odds API
│   ├── pipeline/         # Tages-Tipps, Sync-Status
│   ├── model/            # Quoten, Poisson, Kalibrierung
│   ├── optimizer/        # Kicktipp-Punkte, EV-Optimierer
│   └── site/             # Static-Site-Generator
├── tests/                # pytest (89 Tests)
├── demo.py
└── run.py                # CLI: --round, --all-rounds, --date, --build-site
```

## Nächste Schritte (Phase 0)

- [x] OddsPapi-Anbindung (+ The Odds API Fallback)
- [x] Spielplan via openfootball (lokal, Berlin-Zeitzone)
- [x] Statische Website (GitHub Pages, `docs/`)
- [x] GitHub Actions (Tipps + Kicktipp-Abgabe)
- [x] CI-Tests (`test.yml`)
- [x] GitHub Actions Cron (10:00 + 16:00 MESZ, Kicktipp automatisch)
- [x] Track record mit Punktesumme
- [x] Sync-Status auf dem Dashboard
