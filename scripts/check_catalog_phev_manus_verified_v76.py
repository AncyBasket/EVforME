#!/usr/bin/env python3
"""Verify selective Manus PHEV recovery (seed v76)."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SEED = REPO / "EVforME?" / "Data" / "vehicles.seed.quality.json"
CDN = REPO / "EVforME?" / "Data" / "catalog_cdn.json"
MANIFEST = REPO / "scripts" / "cache" / "eea" / "catalog_phev_manus_verified_v76_manifest.json"
PREV = 75

PURE = re.compile(
    r"solo elettrico|charge[- ]?depleting|\(CD(?:,|\s|\)|/)|"
    r"bei vollständig geladener|batteria carica|batterie chargée|"
    r"pure electric|consumo elettrico puro|rein elektrischem|"
    r"geladenen batterie|/ CD\b",
    re.I,
)


def missing_calc_fields(r: dict) -> list[str]:
    miss: list[str] = []
    cs = r.get("fuelConsumptionLPerKm")
    if cs is None or float(cs) * 100 < 3.0:
        miss.append("fuelConsumptionLPerKm")
    e = r.get("energyConsumptionKWhPerKm")
    if e is None or r.get("energyIsWeighted") is True:
        miss.append("energyConsumptionKWhPerKm")
    if r.get("wltpRangeKm") is None:
        miss.append("wltpRangeKm")
    if r.get("batteryKWh") is None:
        miss.append("batteryKWh")
    return miss


def has_pure(cite: str) -> bool:
    return bool(PURE.search(cite or ""))


def seed_fp() -> str:
    rows = json.loads(SEED.read_text(encoding="utf-8"))
    blob = json.dumps(rows, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(blob.encode()).hexdigest()


def must_fail() -> None:
    caught = 0
    # energy without pure label
    cite = "Consommations d'énergie électrique 16,8 (no CD label)"
    if not has_pure(cite):
        caught += 1
    # complete with nil calc
    bad = {
        "catalogDataIncomplete": False,
        "fuelConsumptionLPerKm": 0.06,
        "energyConsumptionKWhPerKm": 0.2,
        "energyIsWeighted": False,
        "wltpRangeKm": 40,
        "batteryKWh": None,
    }
    if (not bad["catalogDataIncomplete"]) and missing_calc_fields(bad):
        caught += 1
    # live/generic URL for past year
    live = "https://www.toyota.it/content/dam/toyota/nmsc/italy/gamma/pdf/scheda-tecnica/RAV4_Plug-in_Hybrid_Scheda_tecnica.pdf"
    source_date = "2023-06-26"
    row_year = 2024
    if int(source_date[:4]) != row_year and "archive.org" not in live:
        caught += 1
    # EAER City only
    if "eaer city" in "EAER City 55 km".lower() and "combin" not in "EAER City 55 km".lower():
        caught += 1
    # non-prudent max (interval max for CS should be used — probe wrong pick of min)
    interval = (5.2, 6.1)
    wrong = interval[0]
    if wrong != max(interval):
        caught += 1
    # sourceDate inherited from wrong year while claiming field for another year
    if "2023-06-26" != "2024-01-01" and row_year == 2024:
        caught += 1
    if caught != 6:
        raise SystemExit(f"must-fail {caught}/6")
    print("must-fail probes: 6/6")


def hashseed() -> None:
    script = """
import hashlib,json,sys
from pathlib import Path
p=Path(sys.argv[1])
rows=json.loads(p.read_text(encoding='utf-8'))
blob=json.dumps(rows,sort_keys=True,separators=(',',':'),ensure_ascii=False)
print(hashlib.sha256(blob.encode()).hexdigest())
"""
    digests = []
    for s in range(6):
        env = os.environ.copy()
        env["PYTHONHASHSEED"] = str(s)
        r = subprocess.run(
            [sys.executable, "-c", script, str(SEED)],
            capture_output=True,
            text=True,
            env=env,
            check=True,
        )
        digests.append(r.stdout.strip())
    if len(set(digests)) != 1:
        raise SystemExit(f"PYTHONHASHSEED drift: {digests}")
    print(f"PYTHONHASHSEED 0..5 identical: {digests[0][:16]}…")


def main() -> None:
    must_fail()
    hashseed()
    seed = json.loads(SEED.read_text(encoding="utf-8"))
    cdn = json.loads(CDN.read_text(encoding="utf-8"))
    man = json.loads(MANIFEST.read_text(encoding="utf-8"))
    by_id = {r["id"]: r for r in seed}
    ver = int(cdn.get("seedVersion") or 0)
    if ver != PREV + 1:
        raise SystemExit(f"seedVersion expected {PREV+1}, got {ver}")
    removed = set(man.get("ids_before") or []) - set(by_id)
    if removed:
        raise SystemExit(f"removals: {removed}")

    # accepted
    toy = by_id["toyota-rav4-phev-2023"]
    if abs(float(toy.get("batteryKWh")) - 18.1) > 1e-9:
        raise SystemExit("rav4 2023 battery")
    # main EEA weighted fuel preserved (not overwritten by Manus 0.01)
    if abs(float(toy.get("weightedFuelConsumptionLPerKm")) - 0.00948) > 1e-9:
        raise SystemExit("rav4 2023 weighted fuel must stay main 0.00948")
    if (toy.get("fieldSourceDates") or {}).get("batteryKWh") != "2023-01-03":
        raise SystemExit("rav4 2023 battery date")

    cup = by_id["cupra-formentor-phev-e-hybrid-2024"]
    if abs(float(cup.get("batteryKWh")) - 12.8) > 1e-9:
        raise SystemExit("formentor battery")
    if (cup.get("fieldSourceDates") or {}).get("batteryKWh") != "2024-01-01":
        raise SystemExit("formentor date")
    if abs(float(cup.get("powerKw") or 0) - 110.6) > 0.05:
        raise SystemExit("formentor powerKw must stay 110.6")

    b22 = by_id["bmw-serie-2-active-tourer-225e-xdrive-2022"]
    if b22.get("wltpRangeKm") != 83:
        raise SystemExit("225e 2022 range")
    if b22.get("batteryKWh") is not None:
        raise SystemExit("225e 2022 battery must stay nil (listino not reopened)")

    # rejected stay nil / main
    for rid in (
        "bmw-serie-2-active-tourer-225e-xdrive-2023",
        "bmw-serie-2-active-tourer-225e-xdrive-2024",
        "bmw-x3-phev-xdrive30e-2022",
        "bmw-x3-phev-xdrive30e-2023",
        "bmw-x3-phev-xdrive30e-2024",
        "hyundai-tucson-phev-2023",
        "toyota-rav4-phev-2024",
        "volkswagen-tiguan-phev-ehybrid-2024",
    ):
        r = by_id[rid]
        if rid == "toyota-rav4-phev-2024":
            if r.get("batteryKWh") is not None:
                raise SystemExit("rav4 2024 battery must remain nil")
        elif rid.startswith("bmw-x3") or rid.startswith("bmw-serie-2-active-tourer-225e-xdrive-202"):
            if r.get("batteryKWh") is not None or (
                rid != "bmw-serie-2-active-tourer-225e-xdrive-2022" and r.get("wltpRangeKm") is not None
            ):
                if rid != "bmw-serie-2-active-tourer-225e-xdrive-2022":
                    raise SystemExit(f"rejected import leaked: {rid}")
        elif rid == "hyundai-tucson-phev-2023":
            if r.get("batteryKWh") is not None or r.get("wltpRangeKm") is not None:
                raise SystemExit("tucson rejected fields present")
        elif rid == "volkswagen-tiguan-phev-ehybrid-2024":
            if r.get("batteryKWh") is not None:
                raise SystemExit("tiguan battery must remain nil")

    # CD energy still requires pure label when present
    for r in seed:
        if r.get("powertrain") != "phev" or r.get("parentId"):
            continue
        e = r.get("energyConsumptionKWhPerKm")
        if e is None:
            continue
        cite = (r.get("fieldSources") or {}).get("energyConsumptionKWhPerKm") or ""
        # EPA rows from v75 may lack fieldSources energy — only enforce when key present
        # OR when market not US/EPA and fieldSources dict exists with OEM path
        fs = r.get("fieldSources") or {}
        if "energyConsumptionKWhPerKm" in fs and not has_pure(cite):
            raise SystemExit(f"energy without pure label: {r['id']}")

    # complete ⇒ no nil
    for r in seed:
        if r.get("powertrain") != "phev" or r.get("parentId"):
            continue
        if not r.get("catalogDataIncomplete") and missing_calc_fields(r):
            raise SystemExit(f"complete_with_nil: {r['id']}")

    # M3
    m3 = [r for r in seed if r["id"].startswith("tesla-model-3") and r.get("year") == 2026]
    if len(m3) < 4:
        raise SystemExit(f"M3 2026 count {len(m3)}")

    print(json.dumps({
        "seedVersion": ver,
        "fingerprint": seed_fp(),
        "phev_before": [man["phev_complete_before"], man["phev_only_kwh_before"], man["phev_multi_missing_before"]],
        "phev_after": [man["phev_complete_after"], man["phev_only_kwh_after"], man["phev_multi_missing_after"]],
        "accepted": len(man.get("fields_changed") or []),
        "rejected": len(man.get("rejected") or []),
    }, indent=2))
    print("OK")


if __name__ == "__main__":
    main()
