# WM 2026 Kicktipp-Agent

Automatisierter, EV-optimaler Tippgeber für die FIFA-Weltmeisterschaft 2026.

## Status: Phase 0 (MVP)

Funktionsnachweis der Kern-Pipeline:

```
Wettquoten (1X2 + O/U 2.5) → margenbereinigte Wahrscheinlichkeiten
  → Poisson-Kalibrierung → Ergebnisverteilung → EV-optimaler Kicktipp-Tipp
```

## Schnellstart

```bash
cd wm2026-agent
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env    # API-Keys eintragen

python demo.py              # Pipeline-Demo (ohne API)
python run.py --discover    # IDs & API-Verfügbarkeit prüfen
python run.py --date 2026-06-11   # Live-Tipps + Website bauen
python run.py --build-site        # nur Website neu generieren
pytest                      # Tests
```

## Website (GitHub Pages)

Nach jedem Tipp-Lauf wird `docs/` neu generiert. GitHub Pages einrichten:

1. Repo **Settings → Pages → Build and deployment**
2. Source: **Deploy from a branch**
3. Branch: **main**, Folder: **/docs**
4. URL: `https://<user>.github.io/wm2026-agent/`

### GitHub Actions („Update matchday“)

Unter **Settings → Secrets and variables → Actions** müssen mindestens diese Secrets hinterlegt sein:

| Secret | Pflicht? | Beschreibung |
|--------|----------|--------------|
| `ODDSPAPI_API_KEY` | ja | OddsPapi API-Key |
| `ODDSPAPI_TOURNAMENT_ID` | empfohlen | WM-ID (`16` für Nationalmannschaften) |
| `THE_ODDS_API_KEY` | optional | Fallback-Quotenquelle |
| `KICKTIPP_EMAIL` | nur bei Abgabe | Kicktipp-Login |
| `KICKTIPP_PASSWORD` | nur bei Abgabe | Kicktipp-Passwort |
| `KICKTIPP_COMMUNITY` | nur bei Abgabe | Community-Slug (URL-Teil auf kicktipp.com) |

Workflow **Update predictions** hat die Option **Submit to Kicktipp** (`submit_kicktipp: true`).
Dann wird nach der Tipp-Generierung [kicktipp-agent](https://github.com/christianheidorn/kicktipp-agent) als CLI installiert und `scripts/submit_kicktipp.py` liest `state/predictions.json` (+ optional `state/bonus.json`) und ruft `kicktipp bet` auf. Das ist dieselbe Engine wie der MCP-Server `kicktipp-mcp` — in CI braucht man die CLI, nicht den MCP-Protokoll-Client.

Lokal testen (ohne Abgabe):

```bash
python scripts/submit_kicktipp.py --dry-run
```

Teamnamen auf Kicktipp können abweichen — optional `config/kicktipp_aliases.json` anlegen (Vorlage: `config/kicktipp_aliases.example.json`).

Lokal aus `.env` setzen:

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
| Ergebnisse (Phase 1) | worldcup26.ir o.ä. | nein |

Spielplan aktualisieren: `python scripts/fetch_schedule.py`

## Projektstruktur

```
wm2026-agent/
├── data/                 # Spielplan, Quoten-Cache, Beispieldaten
├── state/                # Team-Stärken, Vorhersagen (später)
├── src/
│   ├── sources/          # openfootball, OddsPapi, The Odds API
│   ├── pipeline/         # Tages-Tipps erzeugen
│   ├── model/            # Quoten, Poisson, Kalibrierung
│   └── optimizer/        # Kicktipp-Punkte, EV-Optimierer
├── tests/
├── demo.py               # Funktionsnachweis einzelnes Spiel
└── run.py                # Täglicher Lauf (Stub)
```

## Nächste Schritte (Phase 0)

- [x] OddsPapi-Anbindung (+ The Odds API Fallback)
- [x] Spielplan via openfootball (lokal, Berlin-Zeitzone)
- [x] Statische Website (GitHub Pages, `docs/`)
- [ ] GitHub Actions Cron
