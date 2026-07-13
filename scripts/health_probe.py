#!/usr/bin/env python3
"""Nightly-Gesundheitsprobe: prüft je Quellsystem mit einer leichten,
read-only Stichprobe, ob die API noch antwortet — Ergebnis in
data/v1/health.json. Clients können tote Systeme ausblenden, wir bekommen
Alerts, bevor Nutzer leere Kalender sehen.

    python3 scripts/health_probe.py            # alle Systeme
    python3 scripts/health_probe.py --sample 5 # zusätzlich N Zufalls-Anbieter
                                               # je Registry (gestaffelt für
                                               # den Wochenzyklus)

Höflich gegenüber fremden Systemen: 1 Request/System im Standardlauf,
sleep zwischen Requests, ehrlicher User-Agent.
"""
import json
import pathlib
import random
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "v1" / "health.json"
UA = "Muellplattform-Health/1.0 (+https://github.com/youngpilot/muellplattform)"


def get(url, timeout=25):
    request = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def probe_bsr():
    data = get("https://umnewforms.bsr.de/p/de.bsr.adressen.app/streetNames?searchQuery=Dolgensee")
    return b"Dolgensee" in data


def probe_awido():
    registry = json.load(open(ROOT / "sources" / "AwidoProviders.json", encoding="utf-8"))
    customer = registry[0]["customer"] if "customer" in registry[0] else registry[0].get("id")
    data = get(f"https://awido.cubefour.de/WebServices/Awido.Service.svc/getPlaces/client={customer}")
    return data.startswith(b"[") or data.startswith(b"{")


def probe_abfallio():
    registry = json.load(open(ROOT / "sources" / "AbfallIOProviders.json", encoding="utf-8"))
    key = registry[0]["key"]
    request = urllib.request.Request(
        f"https://api.abfall.io/?key={key}&modus=d6c5855a62cf32a4dadbc2831f0f295f&waction=init",
        data=b"", headers={"User-Agent": UA})
    with urllib.request.urlopen(request, timeout=25) as response:
        return response.status == 200


def probe_jumomind():
    registry = json.load(open(ROOT / "sources" / "JumomindProviders.json", encoding="utf-8"))
    service = registry[0]["service"]
    data = get(f"https://{service}.jumomind.com/mmapp/api.php?r=cities")
    return data.startswith(b"[") or data.startswith(b"{")


def probe_abfallnavi():
    registry = json.load(open(ROOT / "sources" / "AbfallnaviProviders.json", encoding="utf-8"))
    service = registry[0].get("service") or registry[0].get("id")
    data = get(f"https://{service}-abfallapp.regioit.de/abfall-app-{service}/rest/orte")
    return data.startswith(b"[")


def probe_ctrace():
    data = get("https://web.c-trace.de/bremenabfallkalender/Abfallkalender")
    return b"html" in data[:200].lower()


def probe_insertit():
    data = get("https://www.insert-it.de/BmsAbfallkalenderMannheim/Main/GetStreets?text=A")
    return data.startswith(b"[")


def probe_muellmax():
    data = get("https://www.muellmax.de/abfallkalender/aws/res/AwsStart.php")
    return len(data) > 0


PROBES = {
    "bsr": probe_bsr,
    "awido": probe_awido,
    "abfallio": probe_abfallio,
    "jumomind": probe_jumomind,
    "abfallnavi": probe_abfallnavi,
    "ctrace": probe_ctrace,
    "insertit": probe_insertit,
    "muellmax": probe_muellmax,
}


def main():
    results = {}
    for system, probe in PROBES.items():
        try:
            ok = bool(probe())
        except Exception as error:  # noqa: BLE001 — Status, kein Crash
            ok = False
            results[system] = {"ok": False, "error": str(error)[:200]}
        if system not in results:
            results[system] = {"ok": ok}
        print(f"{'✅' if results[system]['ok'] else '❌'} {system}")
        time.sleep(2)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "checkedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "systems": results,
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    failed = [s for s, r in results.items() if not r["ok"]]
    print(f"→ {OUT.relative_to(ROOT)} ({len(PROBES) - len(failed)}/{len(PROBES)} ok)")
    # Exit != 0 bei Ausfällen → GitHub Actions schickt die Alert-Mail.
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
