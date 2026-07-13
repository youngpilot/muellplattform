#!/usr/bin/env python3
"""Baut die versionierten Plattform-Artefakte data/v1/ aus sources/.

    python3 scripts/build_artifacts.py             # aus sources/
    python3 scripts/build_artifacts.py --from-app  # sources/ vorher aus der
                                                   # Mülllotse-App übernehmen

Clients prüfen ausschließlich meta.json (Version + SHA-256 je Datei) und
laden nur geänderte Dateien nach — ein Request im Normalfall.
"""
import hashlib
import json
import pathlib
import shutil
import subprocess
import sys
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parent.parent
SOURCES = ROOT / "sources"
OUT = ROOT / "data" / "v1"
APP_RESOURCES = ROOT.parent / "apps" / "muelllotse" / "Muelllotse" / "Resources"

# Quell-Registries: (Dateiname in App/sources, Artefakt-Name, Quellsystem-Slug)
REGISTRIES = [
    ("AbfallIOProviders.json", "registry-abfallio.json", "abfallio"),
    ("AwidoProviders.json", "registry-awido.json", "awido"),
    ("JumomindProviders.json", "registry-jumomind.json", "jumomind"),
    ("AbfallnaviProviders.json", "registry-abfallnavi.json", "abfallnavi"),
    ("CTraceProviders.json", "registry-ctrace.json", "ctrace"),
    ("InsertITProviders.json", "registry-insertit.json", "insertit"),
    ("MuellmaxProviders.json", "registry-muellmax.json", "muellmax"),
]
DIRECT = [
    ("ProviderPlaceIndex.json", "places.json"),
    ("PlaceCoverage.json", "coverage.json"),
]


def sync_from_app():
    SOURCES.mkdir(exist_ok=True)
    for name, _, _ in REGISTRIES:
        shutil.copy2(APP_RESOURCES / name, SOURCES / name)
    for name, _ in DIRECT:
        shutil.copy2(APP_RESOURCES / name, SOURCES / name)
    print(f"sources/ aus App übernommen ({len(REGISTRIES) + len(DIRECT)} Dateien)")


def unified_registry():
    """Vereinigte Anbieter-Liste für Dritte (id, titel, system)."""
    entries = []
    for name, _, system in REGISTRIES:
        data = json.load(open(SOURCES / name, encoding="utf-8"))
        for item in data:
            title = item.get("title") or item.get("name") or item.get("id", "")
            ident = item.get("key") or item.get("id") or item.get("slug") or title
            entries.append({"system": system, "id": str(ident), "titel": title})
    # Feste Einzelquellen der App (kuratiert, keine Registry-Datei)
    entries += [
        {"system": "bsr", "id": "bsr-berlin", "titel": "Berliner Stadtreinigung (BSR)"},
        {"system": "srh", "id": "srh-hamburg", "titel": "Stadtreinigung Hamburg"},
        {"system": "awm", "id": "awm-muenchen", "titel": "AWM München"},
    ]
    return sorted(entries, key=lambda e: (e["system"], e["titel"]))


def main():
    if "--from-app" in sys.argv:
        sync_from_app()

    OUT.mkdir(parents=True, exist_ok=True)
    written = []

    for name, artifact, _ in REGISTRIES:
        shutil.copy2(SOURCES / name, OUT / artifact)
        written.append(artifact)
    for name, artifact in DIRECT:
        shutil.copy2(SOURCES / name, OUT / artifact)
        written.append(artifact)

    registry = unified_registry()
    (OUT / "registry.json").write_text(
        json.dumps(registry, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    written.append("registry.json")

    # health.json nicht überschreiben, falls die Probe schon lief.
    health = OUT / "health.json"
    if not health.exists():
        health.write_text(json.dumps({"status": "unknown", "checkedAt": None}), encoding="utf-8")
    written.append("health.json")

    def digest(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    commit = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=ROOT
    ).stdout.strip() or None
    meta = {
        "apiVersion": "v1",
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "commit": commit,
        "providerCount": len(registry),
        "files": {name: digest(OUT / name) for name in sorted(set(written))},
    }
    (OUT / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"data/v1: {len(written)} Artefakte, {len(registry)} Anbieter")


if __name__ == "__main__":
    main()
