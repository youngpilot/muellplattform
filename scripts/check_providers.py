#!/usr/bin/env python3
"""Anbieter-Registries gegen die echten Quellsysteme prüfen.

    python3 scripts/check_providers.py abfallio          # ein System
    python3 scripts/check_providers.py --all             # alle Registries
    python3 scripts/check_providers.py abfallio --delay 3

Anders als die nächtliche Health-Probe (Stichprobe, "lebt das SYSTEM?")
geht dieses Werkzeug JEDEN Eintrag durch und beantwortet "welche ANBIETER
sind tot?". Das ist Datenpflege, kein Monitoring — entsprechend selten
laufen lassen.

Zwei Dinge, die hier weh tun, wenn man sie ignoriert:

1. Rate-Limits. abfall.io sperrt nach einer schnellen Serie und antwortet
   dann für ALLE Keys mit 403 — auch für gesunde. Wer dann misst, hält
   funktionierende Anbieter für tot. Darum läuft vor und nach dem Lauf
   eine Positivkontrolle gegen einen bekannt lebenden Key: schlägt sie
   fehl, ist das Ergebnis wertlos und das Skript bricht ab (exit 2),
   statt eine Liste falscher Leichen zu drucken.
2. Ein fehlgeschlagener Abruf ist kein Befund. Timeouts/Netzfehler landen
   als "ungeklärt", nicht als "tot".
"""
import argparse
import json
import pathlib
import sys
import time
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
UA = "Muellplattform-Registry-Check/1.0 (+https://github.com/youngpilot/muellplattform)"
ABFALLIO_MODUS = "d6c5855a62cf32a4dadbc2831f0f295f"


def get(url, timeout=25, data=None, headers=None):
    request = urllib.request.Request(
        url, data=data, headers={"User-Agent": UA, **(headers or {})})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.status, response.read()


def check_abfallio(entry):
    status, _ = get(
        f"https://api.abfall.io/?key={entry['key']}&modus={ABFALLIO_MODUS}&waction=init",
        data=b"", headers={"Content-Type": "application/x-www-form-urlencoded"})
    return status == 200


def check_awido(entry):
    customer = entry.get("customer") or entry.get("id")
    _, data = get(f"https://awido.cubefour.de/WebServices/Awido.Service.svc/getPlaces/client={customer}")
    return data.startswith(b"[") or data.startswith(b"{")


def check_jumomind(entry):
    _, data = get(f"https://{entry['service']}.jumomind.com/mmapp/api.php?r=cities")
    return data.startswith(b"[") or data.startswith(b"{")


def check_abfallnavi(entry):
    """Abfallnavi hat ZWEI Hosting-Muster: den historischen Per-Service-Host
    und einen zentralen Host, auf den einzelne Anbieter migriert sind
    (z. B. Lippe, Unna, Kranenburg, Frankenthal). Die App probiert in
    ScheduleConnectorsPlus beide durch — die Prüfung muss das auch tun,
    sonst meldet sie migrierte Anbieter fälschlich als tot.
    """
    service = entry.get("service") or entry.get("id")
    for base in (f"https://{service}-abfallapp.regioit.de/abfall-app-{service}/rest",
                 f"https://abfallapp.regioit.de/abfall-app-{service}/rest"):
        try:
            _, data = get(f"{base}/orte")
            if data.startswith(b"["):
                return True
        except Exception:  # noqa: BLE001 — nächsten Host probieren
            continue
    return False


SYSTEMS = {
    "abfallio": ("AbfallIOProviders.json", check_abfallio),
    "awido": ("AwidoProviders.json", check_awido),
    "jumomind": ("JumomindProviders.json", check_jumomind),
    "abfallnavi": ("AbfallnaviProviders.json", check_abfallnavi),
}


def load(filename):
    return json.load(open(ROOT / "sources" / filename, encoding="utf-8"))


def canary(entries, check, label):
    """Positivkontrolle: Antwortet ein bekannt lebender Anbieter? Ohne diese
    Zusicherung ist jedes 'tot' im Ergebnis wertlos (Rate-Limit-Fallstrick).
    """
    for entry in entries:
        try:
            if check(entry):
                return True, entry.get("title", "?")
        except Exception:  # noqa: BLE001 — nächsten Kandidaten probieren
            continue
    return False, label


def run(system, delay):
    filename, check = SYSTEMS[system]
    entries = load(filename)
    print(f"\n=== {system}: {len(entries)} Anbieter ===")

    ok, via = canary(entries[:5], check, system)
    if not ok:
        print(f"❌ Positivkontrolle fehlgeschlagen — kein Anbieter der ersten 5 antwortet.")
        print(f"   Vermutlich Rate-Limit oder Netzproblem: Messung abgebrochen,")
        print(f"   damit keine gesunden Anbieter fälschlich als tot gelten.")
        return None
    print(f"✅ Positivkontrolle ok (via {via}) — Leitung ist frei\n")

    dead, unclear = [], []
    for i, entry in enumerate(entries, 1):
        title = entry.get("title", "?")
        try:
            alive = check(entry)
            if alive:
                print(f"  [{i:>3}/{len(entries)}] ok    {title[:55]}")
            else:
                dead.append(title)
                print(f"  [{i:>3}/{len(entries)}] TOT   {title[:55]}")
        except urllib.error.HTTPError as error:
            dead.append(f"{title} (HTTP {error.code})")
            print(f"  [{i:>3}/{len(entries)}] TOT   {title[:55]} — HTTP {error.code}")
        except Exception as error:  # noqa: BLE001 — kein Befund, nur ungeklärt
            unclear.append(f"{title}: {str(error)[:60]}")
            print(f"  [{i:>3}/{len(entries)}] ?     {title[:55]} — {str(error)[:40]}")
        time.sleep(delay)

    ok, _ = canary(entries[:5], check, system)
    if not ok:
        print("\n❌ Nach-Kontrolle fehlgeschlagen — die Leitung wurde WÄHREND des")
        print("   Laufs dicht gemacht. Ergebnis unbrauchbar, später wiederholen.")
        return None

    print(f"\n{len(entries) - len(dead) - len(unclear)}/{len(entries)} leben")
    if dead:
        print("Tot:")
        for d in dead:
            print(f"  - {d}")
    if unclear:
        print("Ungeklärt (Netzfehler, kein Befund):")
        for u in unclear:
            print(f"  - {u}")
    return {"dead": dead, "unclear": unclear}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("system", nargs="?", choices=sorted(SYSTEMS))
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--delay", type=float, default=2.0,
                        help="Sekunden zwischen Requests (Default 2)")
    args = parser.parse_args()

    if not args.system and not args.all:
        parser.error("System angeben oder --all")

    targets = sorted(SYSTEMS) if args.all else [args.system]
    aborted = []
    for system in targets:
        if run(system, args.delay) is None:
            aborted.append(system)
        if system != targets[-1]:
            time.sleep(10)

    if aborted:
        print(f"\n⚠️  Abgebrochen (Leitung dicht): {', '.join(aborted)}")
        sys.exit(2)


if __name__ == "__main__":
    main()
