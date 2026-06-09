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
