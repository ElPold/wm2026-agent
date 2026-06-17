# WM 2026 Kicktipp-Agent — Konzept & Umsetzungsstatus

**Projekt:** Automatisierter Tippgeber für die FIFA-Weltmeisterschaft 2026  
**Repo:** https://github.com/ElPold/wm2026-agent  
**Stand:** 17.06.2026 — WM läuft  
**Abgabe:** automatisch via GitHub Actions Cron (10:00 + 16:00 MESZ) + optional manuell vom Dashboard

---

## 1. Leitidee

Ein Agent zieht öffentlich verfügbare Wettquoten, wandelt sie in eine **Wahrscheinlichkeitsverteilung über alle möglichen Ergebnisse** je Spiel um, wählt daraus den **punkteoptimalen Tipp** für das Kicktipp-Punktesystem (2/3/4-Schema) und veröffentlicht die Empfehlung mit zugrundeliegenden Daten auf einer Website.

### Wo der echte Mehrwert liegt

| Vorteil | Beschreibung |
|---------|--------------|
| **EV-optimale Ergebnistipps** | Nicht das wahrscheinlichste Ergebnis tippen, sondern das mit dem höchsten Erwartungswert im Kicktipp-Schema |
| **Marktbasierte Wahrscheinlichkeiten** | Pinnacle-Quoten als ehrlichstes Signal (nach Marge bereinigt) |
| **Transparenz** | Jeder Tipp mit Quoten, Modell-Wahrscheinlichkeiten und EV nachvollziehbar |
| **Reproduzierbarkeit** | Deterministisches Modell, versionierte Vorhersagen im Repo |

Den Wettmarkt bei den reinen Wahrscheinlichkeiten zu schlagen, ist praktisch unmöglich — der Markt preist Form, Verletzungen und Stimmung bereits ein. Der Agent holt seinen Vorteil durch **systematische Punkteoptimierung**, nicht durch „bessere Orakel-Prognosen“.

---

## 2. Architektur (Soll → Ist)

```
  QUELLEN                    VERARBEITUNG                    AUSGABE
 ┌──────────────┐
 │ openfootball │── Spielplan (104 Spiele, Berlin-Zeit) ──┐
 │ (lokal JSON) │                                          │
 └──────────────┘                                          ▼
 ┌──────────────┐     ┌─────────────────────────┐    ┌──────────────┐
 │ OddsPapi     │────►│ Poisson-Kalibrierung    │───►│ EV-Optimierer│──┐
 │ (Pinnacle)   │     │ an 1X2 + O/U 2.5        │    │ (Kicktipp)   │  │
 └──────────────┘     └─────────────────────────┘    └──────────────┘  │
 ┌──────────────┐                                                        ▼
 │ The Odds API │── Fallback-Quoten                              state/predictions.json
 │ (optional)   │                                                        │
 └──────────────┘                                                        ▼
                                                                  docs/ (GitHub Pages)
                                                                  track.html (Punkte)
                                                                  sync_status.json

  UMGESETZT (Phase 0, erweitert):
  · Automatische Kicktipp-Abgabe (Cron, alle Gruppenspieltage 1–6)
  · Track record mit Punktesumme
  · Sync-Status auf dem Dashboard

  NOCH NICHT UMGESETZT (Phase 1+):
  · Monte-Carlo-Turniersim (Bonusfragen)
  · Bayes-Update nach echten Ergebnissen
  · Claude-Begründungstexte
  · Kalibrierungs-Dashboard (Brier-Score)
```

**Grundprinzip:** Die *Zahlen* erzeugt ein deterministisches, testbares Modell. Ein LLM ist für Phase 2 (News, Sprache) vorgesehen — **nicht** als Ergebnis-Orakel.

---

## 3. Punktesystem & Strategie

### Kicktipp-Regeln (2/3/4-Schema)

| Ergebnis | Punkte |
|----------|--------|
| Richtige Tendenz (Sieg/Niederlage bzw. Remis) | 2 |
| Richtige Tordifferenz (nur bei Sieg/Niederlage) | 3 |
| Exaktes Ergebnis | 4 |

### Zentrale Strategie: Erwartungswert maximieren

Für jeden möglichen Tipp `(th, ta)` wird berechnet:

```
EV(th, ta) = Σ  P(h, a) × Punkte(Tipp, Ergebnis)
```

über alle realistischen Ergebnisse (0:0 bis 6:6). Der Tipp mit dem höchsten EV wird gewählt — nicht das wahrscheinlichste Ergebnis.

**Beispiel Eröffnungsspiel (09.06.2026):** Mexiko vs. Südafrika → Tipp **1:0**, EV **1,79** (Pinnacle: Mexiko ~68 % Favorit, torarmes Profil).

---

## 4. Datenquellen

| Rolle | Quelle | Status | API-Key |
|-------|--------|--------|---------|
| **Spielplan** | [openfootball/worldcup.json](https://github.com/openfootball/worldcup.json) | ✅ umgesetzt | nein |
| **Quoten 1X2 + O/U 2.5** | [OddsPapi](https://oddspapi.io) (Pinnacle) | ✅ umgesetzt | ja |
| **Quoten-Fallback** | [The Odds API](https://the-odds-api.com) | ✅ vorbereitet | optional |
| **Ergebnisse / Track record** | Kicktipp (`/tippuebersicht`) | ✅ umgesetzt | Kicktipp-Login |
| **Elo-Ratings** | eloratings.net | ⏳ Phase 1 | nein |
| **Begründungen** | Claude API | ⏳ Phase 2 | ja |
| ~~API-Football~~ | ~~api-football.com~~ | ❌ bewusst verworfen (zu teuer) | — |

### OddsPapi-Konfiguration (verifiziert)

```
ODDSPAPI_TOURNAMENT_ID=16    # „World Cup“ (Nationalmannschaften, nicht Club-WM!)
ODDSPAPI_BOOKMAKER=pinnacle
```

Tournament-ID 357 = FIFA **Club** World Cup (falsch). ID 24660/38785 liefern keine Fixtures.

---

## 5. Täglicher Ablauf

### Zeitzonen

- Spielplan-Anstoßzeiten werden aus Venue-Zeitzonen (`UTC-6` etc.) nach **Europe/Berlin** umgerechnet.
- **Tagesgrenze:** „Erstes Spiel des Tages“ = frühestes Spiel am Berliner Kalenderdatum (späte US-Spiele können auf den Folgetag in Berlin fallen).

### Automatischer Workflow (Cron + manuell)

**Cron** (`Update predictions`): täglich **10:00** und **16:00 MESZ**

1. Tipps für alle Vorrunden aktualisieren (`run.py --all-rounds`)
2. Ergebnisse von Kicktipp laden (`fetch_results.py`)
3. Tipps an Kicktipp übertragen (`submit_kicktipp.py --all-group-spieltage`)
4. Website neu bauen und nach `main` pushen

**Manuell** (Dashboard-Buttons oder `workflow_dispatch`):

```bash
# Tipps für heutigen Spieltag erzeugen (+ Website bauen)
python run.py --date 2026-06-11

# Alle Gruppenspieltage an Kicktipp senden
python scripts/submit_kicktipp.py --all-group-spieltage --no-bonus

# Veröffentlichen (falls lokal)
git add docs/ state/
git commit -m "Tipps 11.06."
git push
```

Die Website unter **https://elpold.github.io/wm2026-agent/** aktualisiert sich nach dem Push (GitHub Pages aus `/docs`).

---

## 6. Umsetzungsstatus nach Phasen

### Phase 0 — MVP ✅ (fertig)

| Komponente | Datei / Modul | Status |
|------------|---------------|--------|
| Quoten → Wahrscheinlichkeiten (Marge bereinigen) | `src/model/odds.py` | ✅ |
| Poisson-Modell, kalibriert an 1X2 + O/U 2.5 | `src/model/poisson.py`, `calibration.py` | ✅ |
| EV-Optimierer Kicktipp 2/3/4 | `src/optimizer/ev.py`, `scoring.py` | ✅ |
| OddsPapi-Anbindung | `src/sources/oddspapi.py` | ✅ |
| The Odds API (Fallback) | `src/sources/the_odds_api.py` | ✅ |
| Spielplan openfootball + Berlin-Zeit | `src/sources/openfootball.py` | ✅ |
| Team-Matching (Aliase USA, DR Congo …) | `src/sources/team_names.py`, `match_linker.py` | ✅ |
| Tages-Pipeline | `src/pipeline/day_tips.py` | ✅ |
| Vorhersagen protokollieren | `state/predictions.json`, `state/history/` | ✅ |
| Statische Website (17 Vorrunden-Tabs, Sync-Status) | `src/site/generator.py` → `docs/` | ✅ |
| Track record + Punktesumme | `track.html`, `state/results.json` | ✅ |
| Kicktipp-Abgabe automatisch | `scripts/submit_kicktipp.py`, GitHub Actions Cron | ✅ |
| Tests (89 Stück) | `tests/` | ✅ |
| Live-Nachweis | Mexiko–Südafrika 1:0, EV 1,79; Kicktipp-Submit Spieltage 1–6 | ✅ |

### Phase 1 — Turniertage ⏳

| Komponente | Status |
|------------|--------|
| Monte-Carlo-Turniersim (8 beste Dritte, Bracket) | offen |
| Bayes-Update Team-Stärken nach Spielen | offen |
| Ergebnisse von worldcup26.ir | offen |
| Kalibrierungs-Dashboard (Brier / Log-Loss) | offen |
| Bonus-Tipps (Weltmeister, Halbfinalisten …) | offen |

### Phase 2 — Komfort & Challenge-Argument ⏳

| Komponente | Status |
|------------|--------|
| News-Schicht (Claude API, kleine Korrekturen) | offen |
| Begründungstexte pro Tipp | offen |
| Schönere Website (Kalibrierungskurve) | offen |
| Elfmeter-Konvention K.-o.-Phase verifizieren | offen |

---

## 7. Projektstruktur

```
wm2026-agent/
├── data/
│   ├── schedule/worldcup.json   # 104 Spiele (openfootball)
│   └── fixtures/                # Test-Fixtures für Parser
├── docs/                        # Generierte GitHub-Pages-Website
├── site/
│   ├── templates/index.html     # Jinja2-Template
│   └── static/style.css
├── scripts/
│   ├── submit_kicktipp.py       # Kicktipp-Abgabe (Cron + manuell)
│   ├── fetch_results.py         # Ergebnisse von Kicktipp
│   ├── patch_kicktipp_agent.py  # kicktipp.de-Patch
│   └── fetch_schedule.py        # Spielplan aktualisieren
├── src/
│   ├── sources/                 # Datenquellen
│   ├── model/                   # Poisson, Kalibrierung
│   ├── optimizer/               # EV, Kicktipp-Punkte
│   ├── pipeline/                # Tages-Tipps
│   └── site/                    # Website-Generator
├── state/
│   ├── predictions.json         # Letzter Lauf
│   ├── results.json             # Kicktipp-Ergebnisse (Track record)
│   ├── sync_status.json         # Letztes Update + Kicktipp-Sync
│   └── history/rounds/          # Archiv pro Matchday
├── demo.py                      # Pipeline ohne API
├── run.py                       # Orchestrierung
└── tests/
```

---

## 8. Kalibrierung (Konzept — noch nicht live)

Für die Abteilungs-Challenge „beste KI-Bewertung“ ist vorgesehen:

1. Bei **jeder** Vorhersage volle Wahrscheinlichkeiten mitloggen (bereits in `predictions.json`).
2. Nach Spielende Brier-Score und Log-Loss berechnen.
3. Auf der Website: laufender Score vs. Baselines (Buchmacher-Favorit, Zufall) + Kalibrierungskurve.

**Grundidee:** Ein Modell ist *kalibriert*, wenn von allen „70 %-Spielen“ tatsächlich ~70 % so ausgehen — nicht wenn es zufällig ein paar Tipps trifft.

---

## 9. Offene Punkte

1. ~~API-Keys besorgen~~ — OddsPapi ✅
2. ~~Spielplan-Quelle~~ — openfootball ✅ (statt teurem API-Football)
3. ~~Website~~ — GitHub Pages ✅
4. Bonusfragen-Deadlines der Kicktipp-Runde klären
5. Elfmeter-Konvention K.-o.-Phase (vor Ende Gruppenphase)
6. ~~GitHub Actions Cron~~ — ✅ umgesetzt (10:00 + 16:00 MESZ, Kicktipp automatisch)

---

## 10. Befehlsübersicht

| Befehl | Zweck |
|--------|-------|
| `python demo.py` | Pipeline-Demo ohne API |
| `python run.py --discover` | Datenquellen + Turnier-ID prüfen |
| `python run.py --date YYYY-MM-DD` | Tipps + Website + History |
| `python run.py --build-site` | Nur Website neu generieren |
| `python run.py --all-rounds` | Alle Vorrunden-Tipps + Archive |
| `python scripts/submit_kicktipp.py --all-group-spieltage` | Alle Kicktipp-Gruppenspieltage abgeben |
| `python scripts/fetch_results.py` | Ergebnisse von Kicktipp laden |
| `python scripts/fetch_schedule.py` | Spielplan von GitHub aktualisieren |
| `pytest` | 89 Tests |

---

*Dieses Dokument beschreibt Konzept und aktuellen Implementierungsstand des Projekts. Es wird bei größeren Meilensteinen aktualisiert.*
