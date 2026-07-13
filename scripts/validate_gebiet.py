#!/usr/bin/env python3
"""Validiert Entsorgungsgebiet-Dateien gegen den Standard — CI-Gate für
alles, was in data/v1/gebiete/ landet (PR, Harvester, Adapter).

    python3 scripts/validate_gebiet.py schema/beispiel-11000000.json [...]

Nutzt das Paket `jsonschema`, wenn vorhanden; die wichtigsten inhaltlichen
Invarianten (die ein JSON-Schema nicht ausdrücken kann) werden immer geprüft:
- jede Tour-Referenz in zuordnungen existiert
- Termine liegen im Gültigkeitszeitraum und sind sortiert/eindeutig
- jede Fraktion mit Status 'enthalten' hat mindestens eine Tour/Abholort
- gueltigBis nicht in der Vergangenheit (Warnung)
"""
import json
import pathlib
import sys
from datetime import date

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCHEMA = ROOT / "schema" / "entsorgungsgebiet.schema.json"


def check(path):
    errors, warnings = [], []
    doc = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))

    try:
        import jsonschema
        jsonschema.validate(doc, json.loads(SCHEMA.read_text(encoding="utf-8")))
    except ImportError:
        warnings.append("jsonschema nicht installiert – nur Invarianten-Prüfung")
    except Exception as error:  # noqa: BLE001 — Validierungsfehler sammeln
        errors.append(f"Schema: {error}")

    tour_ids = {tour["id"] for tour in doc.get("touren", [])}
    for zuordnung in doc.get("zuordnungen", []):
        for tour in zuordnung.get("touren", []):
            if tour not in tour_ids:
                errors.append(f"Zuordnung '{zuordnung.get('strasse')}' referenziert unbekannte Tour '{tour}'")

    von = date.fromisoformat(doc["gueltigVon"])
    bis = date.fromisoformat(doc["gueltigBis"])
    for tour in doc.get("touren", []):
        dates = [date.fromisoformat(t) for t in tour["termine"]]
        if dates != sorted(set(dates)):
            errors.append(f"Tour '{tour['id']}': Termine nicht sortiert/eindeutig")
        outside = [d for d in dates if not von <= d <= bis]
        if outside:
            errors.append(f"Tour '{tour['id']}': {len(outside)} Termine außerhalb {von}–{bis}")

    covered = {tour["fraktion"] for tour in doc.get("touren", [])}
    covered |= {ort["fraktion"] for ort in doc.get("abholorte", [])}
    for entry in doc.get("fraktionen", []):
        if entry["status"] == "enthalten" and entry["fraktion"] not in covered:
            errors.append(f"Fraktion '{entry['fraktion']}' als 'enthalten' deklariert, aber ohne Tour/Abholort")

    if bis < date.today():
        warnings.append(f"gueltigBis {bis} liegt in der Vergangenheit — Kalender abgelaufen")

    return errors, warnings


def main():
    paths = sys.argv[1:] or [str(ROOT / "schema" / "beispiel-11000000.json")]
    failed = False
    for path in paths:
        errors, warnings = check(path)
        for warning in warnings:
            print(f"⚠️  {path}: {warning}")
        for error in errors:
            print(f"❌ {path}: {error}")
            failed = True
        if not errors:
            print(f"✅ {path}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
