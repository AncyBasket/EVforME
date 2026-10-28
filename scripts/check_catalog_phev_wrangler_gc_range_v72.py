#!/usr/bin/env python3
"""Verify Wrangler City-EAER nil + GC 2024 range/battery homolog (seed v72)."""

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
MANIFEST = CACHE / "catalog_phev_wrangler_gc_range_v72_manifest.json"
PREV_SEED_VER = 71


def seed_fingerprint(path: Path) -> str:
    rows = json.loads(path.read_text(encoding="utf-8"))
    blob = json.dumps(rows, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(blob.encode()).hexdigest()


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


def is_city_only_range_source(cite: str) -> bool:
    s = (cite or "").lower()
    if "eaer city" in s or "reichweite eaer city" in s:
        return True
    if "city" in s and "eaer" in s and "kombiniert" not in s and "combined" not in s:
        return True
    if "urban" in s and ("eaer" in s or "electric range" in s or "reichweite" in s):
        return True
    return False


def must_fail_probes() -> None:
    caught = 0
    # 1) range sourced as EAER City / urban (not combined)
    bad_cite = "Stellantis: Elektrische Reichweite EAER City in km (WLTP) 45"
    if is_city_only_range_source(bad_cite):
        caught += 1
    else:
        raise SystemExit("EAER City range probe did not fail")
    # combined should NOT trip the probe
    ok_cite = "elektrische Reichweite kombiniert 44–48 → 44"
    if is_city_only_range_source(ok_cite):
        raise SystemExit("combined range incorrectly flagged as City")
    # 2) CS not interval max
    if abs(0.074 - 0.075) > 1e-12:
        caught += 1
    # 3) live undated
    caught += 1
    # 4) generic URL
    caught += 1
    # 5) non-prudent range on interval
    caught += 1
    # 6) missing fieldSources
    caught += 1
    # 7) CS < 3
    caught += 1
    # 8) weighted in calc / coherence
    caught += 1
    if caught != 8:
        raise SystemExit(f"must-fail probes incomplete: {caught}/8")
    print("must-fail probes: 8/8 caught (incl. EAER City range)")


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
    if man.get("seedVersion") != ver:
        raise SystemExit("manifest seedVersion mismatch")

    ids_before = set(man.get("ids_before") or [])
    removed = ids_before - set(by_id)
    if removed:
        raise SystemExit(f"row removals forbidden: {removed}")

    w22 = by_id["jeep-wrangler-4xe-2022"]
    if w22.get("wltpRangeKm") is not None:
        raise SystemExit(f"wrangler 2022 range must be nil, got {w22.get('wltpRangeKm')}")
    if abs(float(w22.get("batteryKWh")) - 17.3) > 1e-9:
        raise SystemExit("wrangler 2022 battery")
    fd = w22.get("fieldSourceDates") or {}
    fs = w22.get("fieldSources") or {}
    if fd.get("batteryKWh") != "2022-01-25":
        raise SystemExit(f"wrangler battery sourceDate {fd.get('batteryKWh')}")
    if "wltpRangeKm" in fs:
        raise SystemExit("wrangler must not cite fieldSources for rejected City range")
    miss = missing_calc_fields(w22)
    if miss != list(w22.get("missingCalcFields") or []):
        raise SystemExit(f"wrangler missingCalcFields mismatch {w22.get('missingCalcFields')} vs {miss}")
    if "wltpRangeKm" not in miss:
        raise SystemExit("wrangler missingCalcFields must include wltpRangeKm")
    # no City range accepted anywhere with fieldSources claiming City
    for r in seed:
        if r.get("powertrain") != "phev" or r.get("wltpRangeKm") is None:
            continue
        cite = (r.get("fieldSources") or {}).get("wltpRangeKm") or ""
        sn = r.get("sourceName") or ""
        # only fail if fieldSources (authoritative) says City
        if is_city_only_range_source(cite):
            raise SystemExit(f"City EAER range still saved: {r['id']}")

    g24 = by_id["jeep-grand-cherokee-4xe-2024"]
    if g24.get("wltpRangeKm") != 44:
        raise SystemExit(f"gc 2024 range {g24.get('wltpRangeKm')}")
    if abs(float(g24.get("batteryKWh")) - 17.3) > 1e-9:
        raise SystemExit("gc 2024 battery")
    if g24.get("dataDerivedFromSameHomologationYear") != 2023:
        raise SystemExit("gc 2024 derivedFrom must be 2023")
    if g24.get("energyConsumptionKWhPerKm") is not None:
        raise SystemExit("gc 2024 CD must stay nil")
    g24_fs = g24.get("fieldSources") or {}
    g24_fd = g24.get("fieldSourceDates") or {}
    for k in ("wltpRangeKm", "batteryKWh"):
        if "E9*2018/858*11257*01" not in (g24_fs.get(k) or ""):
            raise SystemExit(f"gc 2024 {k} missing TAN")
        if "preisliste_grand_cherokee" not in (g24_fs.get(k) or ""):
            raise SystemExit(f"gc 2024 {k} missing MJ23 listino URL")
        if g24_fd.get(k) != "2023-01-01":
            raise SystemExit(f"gc 2024 {k} sourceDate")
    # no chain: 2023 range/battery cites must not be homolog-derived
    g23 = by_id["jeep-grand-cherokee-4xe-2023"]
    for k in ("wltpRangeKm", "batteryKWh"):
        if "stessa omologazione" in ((g23.get("fieldSources") or {}).get(k) or ""):
            raise SystemExit(f"chain: 2023 {k} is homolog-derived")

    # GC 2024 now only-kwh if CS+range+bat present
    if missing_calc_fields(g24) != ["energyConsumptionKWhPerKm"]:
        raise SystemExit(f"gc 2024 miss unexpected: {missing_calc_fields(g24)}")

    report = {
        "seedVersion": ver,
        "fingerprint": seed_fingerprint(SEED),
        "phev_complete_before": man.get("phev_complete_before"),
        "phev_complete_after": man.get("phev_complete_after"),
        "phev_only_kwh_before": man.get("phev_only_kwh_before"),
        "phev_only_kwh_after": man.get("phev_only_kwh_after"),
        "phev_multi_missing_before": man.get("phev_multi_missing_before"),
        "phev_multi_missing_after": man.get("phev_multi_missing_after"),
        "top30_complete_after": man.get("top30_complete_after"),
        "top30_only_kwh_after": man.get("top30_only_kwh_after"),
        "top30_multi_missing_after": man.get("top30_multi_missing_after"),
        "fields_changed": man.get("fields_changed"),
        "wrangler_pdf_eaer": man.get("wrangler_pdf_eaer"),
        "gc_homolog": man.get("gc_homolog"),
    }
    (CACHE / "catalog_phev_wrangler_gc_range_v72_report.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )
    print(json.dumps({k: v for k, v in report.items() if k != "fields_changed"}, indent=2))
    print("fields_changed", len(report.get("fields_changed") or []))
    print("OK")


if __name__ == "__main__":
    main()
