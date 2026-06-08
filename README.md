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

python demo.py          # Pipeline-Demo
python run.py --demo    # gleiches über run.py
pytest                  # Tests
```

## Projektstruktur

```
wm2026-agent/
├── data/                 # Spielplan, Quoten-Cache, Beispieldaten
├── state/                # Team-Stärken, Vorhersagen (später)
├── src/
│   ├── model/            # Quoten, Poisson, Kalibrierung
│   └── optimizer/        # Kicktipp-Punkte, EV-Optimierer
├── tests/
├── demo.py               # Funktionsnachweis einzelnes Spiel
└── run.py                # Täglicher Lauf (Stub)
```

## Nächste Schritte (Phase 0)

- [ ] OddsPapi-Anbindung
- [ ] API-Football Spielplan + Zeitzonen
- [ ] Statische Website (GitHub Pages)
- [ ] GitHub Actions Cron
