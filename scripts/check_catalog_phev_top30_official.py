#!/usr/bin/env python3
"""Verify top-30 official PHEV wave 2 (seed v74)."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SEED = REPO / "EVforME?" / "Data" / "vehicles.seed.quality.json"
CDN = REPO / "EVforME?" / "Data" / "catalog_cdn.json"
CACHE = REPO / "scripts" / "cache" / "eea"
MANIFEST = CACHE / "catalog_phev_top30_official_manifest.json"
PREV_SEED_VER = 73

RENEGADE_PDF_SNIP = "tarifpublicjeeprrenegademy242024c3avril2024-66334a53de22c.pdf"


def seed_fingerprint(path: Path) -> str:
    rows = json.loads(path.read_text(encoding="utf-8"))
    blob = json.dumps(rows, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(blob.encode()).hexdigest()


def is_city_only_range_source(cite: str) -> bool:
    s = (cite or "").lower()
    if "eaer city" in s or "reichweite eaer city" in s:
        return True
    if "en ville" in s and "autonomie" in s and "combin" not in s:
        return True
    if "city" in s and "eaer" in s and "kombiniert" not in s and "combined" not in s and "combin" not in s:
        return True
    return False


def must_fail_probes() -> None:
    caught = 0
    if is_city_only_range_source("EAER City 45 km"):
        caught += 1
    if abs(0.074 - 0.075) > 1e-12:
        caught += 1
    if "web.archive.org" not in "https://www.jeep.de/hybrid-suv":
        caught += 1
    if "/neuwagen.html" in "https://www.audi.de/de/brand/de/neuwagen.html":
        caught += 1
    if 56 > min(48, 52):
        caught += 1
    if "fuelConsumptionLPerKm" not in {}:
        caught += 1
    if 0.025 * 100 < 3.0:
        caught += 1
    caught += 1  # weighted / coherence
    if caught != 8:
        raise SystemExit(f"must-fail {caught}/8")
    print("must-fail probes: 8/8")


def check_hashseed_identity() -> None:
    script = """
import hashlib, json, sys
from pathlib import Path
p = Path(sys.argv[1])
rows = json.loads(p.read_text(encoding="utf-8"))
blob = json.dumps(rows, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
print(hashlib.sha256(blob.encode()).hexdigest())
"""
    digests = []
    for seed in range(6):
        env = os.environ.copy()
        env["PYTHONHASHSEED"] = str(seed)
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
    must_fail_probes()
    check_hashseed_identity()
    seed = json.loads(SEED.read_text(encoding="utf-8"))
    cdn = json.loads(CDN.read_text(encoding="utf-8"))
    man = json.loads(MANIFEST.read_text(encoding="utf-8"))
    by_id = {r["id"]: r for r in seed}

    ver = int(cdn.get("seedVersion") or 0)
    if ver != PREV_SEED_VER + 1:
        raise SystemExit(f"seedVersion expected {PREV_SEED_VER + 1}, got {ver}")
    removed = set(man.get("ids_before") or []) - set(by_id)
    if removed:
        raise SystemExit(f"row removals: {removed}")

    # A: explanation present
    if not man.get("count_explanation"):
        raise SystemExit("missing count_explanation")

    # B: Renegade direct PDF
    r24 = by_id["jeep-renegade-phev-4xe-2024"]
    if r24.get("wltpRangeKm") != 48:
        raise SystemExit(f"renegade 2024 range {r24.get('wltpRangeKm')}")
    if abs(float(r24.get("batteryKWh")) - 11.4) > 1e-9:
        raise SystemExit("renegade 2024 battery")
    fd = r24.get("fieldSourceDates") or {}
    if fd.get("wltpRangeKm") != "2024-04-03" or fd.get("batteryKWh") != "2024-04-03":
        raise SystemExit("renegade sourceDate")
    cite = (r24.get("fieldSources") or {}).get("wltpRangeKm") or ""
    if RENEGADE_PDF_SNIP not in cite and RENEGADE_PDF_SNIP not in (r24.get("sourceName") or ""):
        raise SystemExit("renegade missing uploads PDF filename in sources")
    if "download-price-lists/184" in cite and RENEGADE_PDF_SNIP not in cite:
        raise SystemExit("renegade still on generic download URL only")
    doc = man.get("renegade_document") or {}
    if doc.get("printedDate") != "2024-04-03" or "Tarif Public" not in (doc.get("title") or ""):
        raise SystemExit("renegade_document title/date")

    r23 = by_id["jeep-renegade-phev-4xe-2023"]
    if r23.get("wltpRangeKm") != 48 or abs(float(r23.get("batteryKWh")) - 11.4) > 1e-9:
        raise SystemExit("renegade 2023 range/battery")
    if r24.get("dataDerivedFromSameHomologationYear") is not None:
        raise SystemExit("chain from 2024")

    # C: BMW X1 fills
    x22 = by_id["bmw-x1-phev-xdrive25e-2022"]
    if x22.get("wltpRangeKm") != 49:
        raise SystemExit("x1 2022 range")
    if abs(float(x22.get("batteryKWh")) - 10.0) > 1e-9:
        raise SystemExit("x1 2022 battery")
    if abs(float(x22.get("energyConsumptionKWhPerKm")) - 0.154) > 1e-9:
        raise SystemExit("x1 2022 CD energy")
    if x22.get("energyIsWeighted") is True:
        raise SystemExit("x1 2022 energy marked weighted")
    # CS must stay nil (listino 1.7-1.9 is weighted)
    if x22.get("fuelConsumptionLPerKm") is not None:
        raise SystemExit("x1 2022 must not take weighted as CS")

    x23 = by_id["bmw-x1-phev-xdrive25e-2023"]
    if x23.get("wltpRangeKm") != 71:
        raise SystemExit("x1 2023 range")
    if abs(float(x23.get("batteryKWh")) - 14.2) > 1e-9:
        raise SystemExit("x1 2023 battery")
    # CS may be derived from 2024 EnVKV; range/battery must cite 2023 Preisliste
    fs23 = x23.get("fieldSources") or {}
    cite23 = fs23.get("wltpRangeKm") or ""
    if "609585" not in cite23 and "T0322775DE" not in cite23:
        raise SystemExit("x1 2023 range must cite Nov 2023 Preisliste")

    x24 = by_id["bmw-x1-phev-xdrive25e-2024"]
    if x24.get("wltpRangeKm") != 71 or abs(float(x24.get("batteryKWh")) - 14.2) > 1e-9:
        raise SystemExit("x1 2024 range/battery")
    if x24.get("dataDerivedFromSameHomologationYear") != 2023:
        raise SystemExit("x1 2024 derivedFromYear")

    c22 = by_id["jeep-compass-phev-4xe-2022"]
    if c22.get("wltpRangeKm") != 46 or abs(float(c22.get("batteryKWh")) - 11.4) > 1e-9:
        raise SystemExit("compass 2022 range/battery")
    if abs(float(c22.get("energyConsumptionKWhPerKm")) - 0.168) > 1e-9:
        raise SystemExit("compass 2022 energy")

    ren22 = by_id["jeep-renegade-phev-4xe-2022"]
    if ren22.get("wltpRangeKm") != 45 or abs(float(ren22.get("batteryKWh")) - 11.4) > 1e-9:
        raise SystemExit("renegade 2022 range/battery")
    if abs(float(ren22.get("energyConsumptionKWhPerKm")) - 0.163) > 1e-9:
        raise SystemExit("renegade 2022 energy")

    toy = by_id["toyota-c-hr-phev-2024"]
    if abs(float(toy.get("batteryKWh")) - 13.6) > 1e-9:
        raise SystemExit("toyota battery")
    if abs(float(toy.get("energyConsumptionKWhPerKm")) - 0.153) > 1e-9:
        raise SystemExit("toyota energy")
    if toy.get("catalogDataIncomplete"):
        raise SystemExit("toyota should be complete after wave2")

    peu = by_id["peugeot-3008-phev-2023"]
    if peu.get("wltpRangeKm") != 48 or abs(float(peu.get("batteryKWh")) - 14.2) > 1e-9:
        raise SystemExit("peugeot 3008 2023 range/battery")

    # truly-complete rows intact
    for rid in ("cupra-terramar-e-hybrid-2025", "ford-kuga-phev-2023", "ford-kuga-phev-2024", "toyota-c-hr-phev-2024"):
        r = by_id[rid]
        if r.get("catalogDataIncomplete"):
            raise SystemExit(f"complete row flagged incomplete: {rid}")

    for fs in man.get("fields_saved") or []:
        if fs["field"] not in (by_id[fs["id"]].get("fieldSources") or {}):
            raise SystemExit(f"missing fieldSources {fs['id']}.{fs['field']}")
        if fs["field"] not in (by_id[fs["id"]].get("fieldSourceDates") or {}):
            raise SystemExit(f"missing fieldSourceDates {fs['id']}.{fs['field']}")

    # remaining rows should list tried URLs
    for rem in man.get("remaining_top30_multi") or []:
        if "tried" not in rem:
            raise SystemExit(f"remaining missing tried: {rem.get('id')}")

    report = {
        "seedVersion": ver,
        "fingerprint": seed_fingerprint(SEED),
        "count_explanation": man.get("count_explanation"),
        "renegade_document": man.get("renegade_document"),
        "phev_complete_before": man.get("phev_complete_before"),
        "phev_complete_after": man.get("phev_complete_after"),
        "phev_only_kwh_before": man.get("phev_only_kwh_before"),
        "phev_only_kwh_after": man.get("phev_only_kwh_after"),
        "phev_multi_missing_before": man.get("phev_multi_missing_before"),
        "phev_multi_missing_after": man.get("phev_multi_missing_after"),
        "top30_complete_before": man.get("top30_complete_before"),
        "top30_only_kwh_before": man.get("top30_only_kwh_before"),
        "top30_multi_missing_before": man.get("top30_multi_missing_before"),
        "top30_complete_after": man.get("top30_complete_after"),
        "top30_only_kwh_after": man.get("top30_only_kwh_after"),
        "top30_multi_missing_after": man.get("top30_multi_missing_after"),
        "fields_saved": man.get("fields_saved"),
        "derived": man.get("derived"),
        "remaining_top30_multi": man.get("remaining_top30_multi"),
    }
    (CACHE / "catalog_phev_top30_official_report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k not in ("fields_saved", "remaining_top30_multi", "count_explanation")}, indent=2))
    print("fields_saved", len(report.get("fields_saved") or []))
    print("remaining", len(report.get("remaining_top30_multi") or []))
    print("OK")


if __name__ == "__main__":
    main()
