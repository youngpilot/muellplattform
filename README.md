# Müllplattform – Offene Abfuhrdaten für Deutschland

Statische, versionierte Datenplattform für Abfuhrkalender-Metadaten: welche
Entsorger gibt es, welche Orte decken sie ab, wo können Apps Termine
automatisch laden. Primärer Client ist die iOS-App
[Mülllotse](https://iosapps.de); die Daten stehen allen offen (CC BY).

**Architektur:** kein Server. Dieses Repo ist die Quelle der Wahrheit,
GitHub Actions baut nightly die Artefakte, ein CDN (Cloudflare Pages)
liefert `data/` aus. Details: `docs`-Abschnitt unten.

## Datenartefakte `data/v1/`

| Datei | Inhalt |
|---|---|
| `meta.json` | Version, Erzeugungszeit, SHA-256 je Datei — Clients prüfen NUR diese Datei auf Änderungen |
| `registry.json` | Vereinigte Liste aller Entsorger-Einträge (Quellsystem, ID, Titel) |
| `registry-<system>.json` | Quell-Registries im nativen Format der Adapter (abfallio, awido, jumomind, abfallnavi, ctrace, insertit, muellmax) |
| `places.json` | Ort (normalisiert) → Anbieter-IDs — Basis für Entsorger-Autoerkennung |
| `coverage.json` | Georeferenzierte Abdeckung (Ort, lat/lon, Anbieterzahl) für Karten-Layer |
| `health.json` | Letzter Probe-Status je Quellsystem (nightly) |

Versprechen: innerhalb von `/v1` nur additive Änderungen; Breaking Changes
bekommen `/v2`.

## Bauen

```bash
python3 scripts/build_artifacts.py            # erzeugt data/v1 aus sources/
python3 scripts/health_probe.py --sample 5    # Stichproben gegen die Quellsysteme
```

`sources/` enthält die gepflegten Quell-Registries (synchron mit der
Mülllotse-App; `build_artifacts.py --from-app` übernimmt sie von dort).

## Standard

`schema/abfuhrkalender.schema.json` definiert das Zielformat, in dem
Entsorger/Kommunen Abfuhrkalender liefern können (explizite Termine je
Fraktion, AGS-Gebietskennung, Gültigkeitszeitraum). Phase-4-Ziel: die
White-Label-Hersteller exportieren dieses Format direkt — ein Adapter pro
Hersteller deckt alle seine Kommunen ab.

## Lizenz

Code MIT, Daten CC BY 4.0 (Quellenangabe „Müllplattform / Mülllotse").
