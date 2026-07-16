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

## Standard: Entsorgungsgebiet (formatVersion 1.1)

`schema/entsorgungsgebiet.schema.json` definiert das Lieferformat je Gebiet
(Beispiel: `schema/beispiel-11000000.json`, Validator:
`scripts/validate_gebiet.py` — läuft als CI-Gate). Design-Entscheidungen:

1. **Touren statt Straßen-Termine (GTFS-Prinzip):** Termine hängen an einer
   Tour mit stabiler ID; `zuordnungen` mappen Straße + Hausnummern-Bereich
   auf Touren. Eine Terminverschiebung ist EIN Update, und die Datei bleibt
   klein (eine Stadt hat Dutzende Touren, nicht tausende Straßen-Kalender).
2. **Straße+Hausnummer ist die Wahrheit, Geometrie ist Beiwerk:** Entsorger
   planen adressgenau (gerade/ungerade Seiten in verschiedenen Touren!) —
   das können Polygone nicht sauber abbilden, und viele Entsorger haben gar
   keine GIS-Daten. Bezirks-Polygone (`geometrie`) sind deshalb optional
   fürs Karten-Rendering; fehlen sie, leitet die Plattform sie aus
   geocodierten Straßen ab (`geometrieAbgeleitet: true`).
3. **Explizite Termine, nie Regeln:** Feiertagsverschiebungen und
   Saisonrhythmen stecken nur in expliziten Daten.
4. **Negative Abdeckung ist Pflicht-Information:** `fraktionen[]` deklariert
   auch `andererAnbieter`/`aufAbruf`/`nichtImGebiet` (Berlin: Papier liegt
   bei privaten Anbietern, nicht im BSR-Kalender) — Clients unterscheiden
   damit Lücke von Fehler.
5. **Frische-Metadaten für den Betrieb:** `stand`, `gueltigVon/Bis`
   (Ablauf-Radar am Jahreswechsel), `quelle.typ`
   (geliefert/harvested/adapter/community als Vertrauens-Stufen),
   `herausgeber.kontakt` als Pflege-Kanal.
6. **AGS/ARS als Gebietsanker:** amtlich, stabil, joinbar — Ablage als
   `data/v1/gebiete/{ags}.json`, CDN-freundlich shardbar (Clients laden nur
   ihr Gebiet).

**v1.2 (additiv):** `fraktionen[].verwertung` — Entsorger hinterlegen den
lokalen Verwertungsweg je Fraktion (recycling/verbrennung/vergaerung/…,
Anlage, Recyclingquote, Info-URL). Ziel: Transparenz darüber, was mit dem
Müll tatsächlich passiert — angezeigt z. B. im Tonnen-Wissen der
Mülllotse-App, das bis dahin bundesweit übliche Verwertungswege nennt.

Phase-4-Ziel: die ~10 White-Label-Hersteller exportieren dieses Format
direkt — ein Adapter pro Hersteller deckt alle seine Kommunen ab.

## Lizenz

Code MIT, Daten CC BY 4.0 (Quellenangabe „Müllplattform / Mülllotse").
