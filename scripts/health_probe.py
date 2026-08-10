#!/usr/bin/env python3
"""Nightly-Gesundheitsprobe: prüft je Quellsystem mit einer leichten,
read-only Stichprobe, ob die API noch antwortet — Ergebnis in
data/v1/health.json. Clients können tote Systeme ausblenden, wir bekommen
Alerts, bevor Nutzer leere Kalender sehen.

    python3 scripts/health_probe.py            # alle Systeme

Ein System gilt als gesund, sobald IRGENDEIN Anbieter antwortet. Registry-
basierte Systeme werden deshalb über eine kleine Stichprobe geprüft (die
ersten `SAMPLE` Anbieter, Abbruch beim ersten Treffer): ein einzelner
weggewanderter Anbieter (z. B. abfall.io liefert dann 401) darf nicht das
ganze System als tot melden. Erst wenn ALLE Stichproben-Anbieter scheitern,
ist das System wirklich unten — nur dann schlägt der Job rot an.

Höflich gegenüber fremden Systemen: Abbruch beim ersten Erfolg (meist
1 Request/System), sleep zwischen Requests, ehrlicher User-Agent.
"""
import json
import pathlib
import sys
import time
import urllib.request
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "v1" / "health.json"
UA = "Muellplattform-Health/1.0 (+https://github.com/youngpilot/muellplattform)"
# Wie viele Anbieter je Registry angetippt werden, bevor ein System als tot
# gilt. 4 deckt vereinzelte tote Einträge ab, ohne die Quelle zu belasten.
SAMPLE = 4
# Öffentlicher Widget-Modus-Schlüssel von abfall.io (steht in jeder
# Entsorger-Website, identisch für alle Anbieter).
ABFALLIO_MODUS = "d6c5855a62cf32a4dadbc2831f0f295f"


def get(url, timeout=25):
    request = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def registry(name):
    return json.load(open(ROOT / "sources" / name, encoding="utf-8"))


def sample_providers(entries, check, sample=SAMPLE):
    """Tippt bis zu `sample` Anbieter an und gibt beim ERSTEN Treffer zurück.
    Ein System ist gesund, sobald ein Anbieter antwortet; erst wenn alle
    Stichproben scheitern, gilt es als tot (mit dem letzten Fehler als Grund).
    """
    tried = 0
    last_error = "keine Anbieter in der Registry"
    for entry in entries[:sample]:
        tried += 1
        try:
            if check(entry):
                title = entry.get("title", "?")
                return {"ok": True, "checkedProviders": tried, "via": title}
        except Exception as error:  # noqa: BLE001 — Status sammeln, nicht crashen
            last_error = f"{entry.get('title', '?')}: {str(error)[:120]}"
        time.sleep(1)
    return {"ok": False, "checkedProviders": tried, "error": last_error}


# --- Registry-basierte Systeme: Prüffunktion je Anbieter -------------------

def check_awido(entry):
    customer = entry.get("customer") or entry.get("id")
    data = get(f"https://awido.cubefour.de/WebServices/Awido.Service.svc/getPlaces/client={customer}")
    return data.startswith(b"[") or data.startswith(b"{")


def check_abfallio(entry):
    url = f"https://api.abfall.io/?key={entry['key']}&modus={ABFALLIO_MODUS}&waction=init"
    request = urllib.request.Request(
        url, data=b"",
        headers={"User-Agent": UA, "Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(request, timeout=25) as response:
        return response.status == 200


def check_jumomind(entry):
    service = entry["service"]
    data = get(f"https://{service}.jumomind.com/mmapp/api.php?r=cities")
    return data.startswith(b"[") or data.startswith(b"{")


def check_abfallnavi(entry):
    """Zwei Hosting-Muster: historischer Per-Service-Host und ein zentraler
    Host, auf den einzelne Anbieter migriert sind. Die App probiert in
    ScheduleConnectorsPlus ebenfalls beide durch.
    """
    service = entry.get("service") or entry.get("id")
    for base in (f"https://{service}-abfallapp.regioit.de/abfall-app-{service}/rest",
                 f"https://abfallapp.regioit.de/abfall-app-{service}/rest"):
        try:
            if get(f"{base}/orte").startswith(b"["):
                return True
        except Exception:  # noqa: BLE001 — nächsten Host probieren
            continue
    return False


# --- Systeme mit festem, anbieterunabhängigem Endpunkt ---------------------

def probe_bsr():
    data = get("https://umnewforms.bsr.de/p/de.bsr.adressen.app/streetNames?searchQuery=Dolgensee")
    return b"Dolgensee" in data


def probe_ctrace():
    data = get("https://web.c-trace.de/bremenabfallkalender/Abfallkalender")
    return b"html" in data[:200].lower()


def probe_insertit():
    data = get("https://www.insert-it.de/BmsAbfallkalenderMannheim/Main/GetStreets?text=A")
    return data.startswith(b"[")


def probe_muellmax():
    data = get("https://www.muellmax.de/abfallkalender/aws/res/AwsStart.php")
    return len(data) > 0


def single(fn):
    """Fester-Endpunkt-Probe in dasselbe Ergebnis-Format bringen."""
    def run():
        return {"ok": bool(fn()), "checkedProviders": 1}
    return run


PROBES = {
    "bsr": single(probe_bsr),
    "awido": lambda: sample_providers(registry("AwidoProviders.json"), check_awido),
    "abfallio": lambda: sample_providers(registry("AbfallIOProviders.json"), check_abfallio),
    "jumomind": lambda: sample_providers(registry("JumomindProviders.json"), check_jumomind),
    "abfallnavi": lambda: sample_providers(registry("AbfallnaviProviders.json"), check_abfallnavi),
    "ctrace": single(probe_ctrace),
    "insertit": single(probe_insertit),
    "muellmax": single(probe_muellmax),
}


def main():
    results = {}
    for system, probe in PROBES.items():
        try:
            results[system] = probe()
        except Exception as error:  # noqa: BLE001 — Status, kein Crash
            results[system] = {"ok": False, "error": str(error)[:200]}
        r = results[system]
        detail = r.get("via") or r.get("error", "")
        print(f"{'✅' if r['ok'] else '❌'} {system} {detail}")
        time.sleep(2)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "checkedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "systems": results,
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    failed = [s for s, r in results.items() if not r["ok"]]
    print(f"→ {OUT.relative_to(ROOT)} ({len(PROBES) - len(failed)}/{len(PROBES)} ok)")
    if failed:
        print(f"❌ Tote Systeme (alle Stichproben scheiterten): {', '.join(failed)}")
    # Exit != 0 nur bei ECHT toten Systemen → GitHub Actions schickt die
    # Alert-Mail. Ein einzelner weggewanderter Anbieter reicht nicht mehr.
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
