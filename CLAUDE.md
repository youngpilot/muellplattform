# Müllplattform

Statische offene Abfuhrdaten-Plattform (Repo = Quelle, GitHub Actions nightly, Cloudflare Pages liefert `data/` aus). Primärer Client: Mülllotse-App (`../apps/muelllotse`, PlatformData.swift). Konzept: Obsidian jstone/Mülllotse/„Plattform Bauplan & Betrieb".

## Regeln
- `data/v1/` NIE von Hand editieren — immer `python3 scripts/build_artifacts.py` (Quellen in `sources/`, App-Sync via `--from-app`)
- Innerhalb v1 nur additive Änderungen; Breaking → v2
- Proben (health_probe.py) read-only, mit sleep + ehrlichem User-Agent
- Daten CC BY 4.0, Code MIT
