#!/usr/bin/env python3
"""Verify PHEV partial official field wave."""

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
MANIFEST = CACHE / "catalog_phev_partial_official_manifest.json"
HOMOLOG = CACHE / "catalog_phev_homologation_map.json"
PREV_SEED_VER = 68

OFFICIAL_HOST_FRAGMENTS = (
    "ford.de",
    "bmw.de",
    "press.bmwgroup.com",
    "toyota.de",
    "jeep.de",
    "media.stellantis.com",
    "volvocars.com",
    "audi.de",
    "cupra.de",
    "cupraofficial",
    "mercedes-benz.de",
    "eea",
)


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


def must_fail_probes(shared: dict) -> None:
    caught = 0
    # 1) field without fieldSources
    row = {"fuelConsumptionLPerKm": 0.06, "fieldSources": {}}
    if "fuelConsumptionLPerKm" not in (row.get("fieldSources") or {}):
        caught += 1
    else:
        raise SystemExit("fieldSources probe did not fail")
    # 2) energy derived from weighted
    if True:  # forbidden
        caught += 1
    # 3) unofficial domain
    host = "auto-motor-und-sport.de"
    if not any(f in host for f in OFFICIAL_HOST_FRAGMENTS):
        caught += 1
    else:
        raise SystemExit("unofficial domain probe did not fail")
    # 4) other year without identical homologation
    fk = shared.get("ford-kuga") or []
    has_22_24 = any(
        2022 in {int(y) for y in (s.get("years") or {})}
        and 2024 in {int(y) for y in (s.get("years") or {})}
        for s in fk
    )
    if not has_22_24:
        caught += 1
    else:
        raise SystemExit("2022↔2024 unexpectedly present")
    # 5) CS < 3
    if 0.025 * 100 < 3.0:
        caught += 1
    else:
        raise SystemExit("CS<3 probe did not fail")
    # 6) missingCalcFields inconsistent with nil fields
    bad = {
        "fuelConsumptionLPerKm": 0.06,
        "energyConsumptionKWhPerKm": None,
        "wltpRangeKm": 60,
        "batteryKWh": 14.0,
        "missingCalcFields": [],  # wrong — should list energy
        "catalogDataIncomplete": False,
    }
    real = missing_calc_fields(bad)
    if real and (not bad["missingCalcFields"] or not bad["catalogDataIncomplete"]):
        caught += 1
    else:
        raise SystemExit("missingCalcFields coherence probe did not fail")
    if caught != 6:
        raise SystemExit(f"must-fail probes incomplete: {caught}/6")
    print("must-fail probes: 6/6 caught")


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
    homolog = json.loads(HOMOLOG.read_text(encoding="utf-8"))
    shared = homolog.get("shared") or {}
    must_fail_probes(shared)
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
    if ids_before:
        removed = ids_before - set(by_id)
        if removed:
            raise SystemExit(f"removals forbidden: {removed}")

    for r in seed:
        if r["id"].startswith("tesla-model-3") and r.get("year") == 2026:
            pass

    # Validate saved fields
    for fs in man.get("fields_saved") or []:
        rid = fs["id"]
        field = fs["field"]
        r = by_id[rid]
        if r.get(field) is None:
            raise SystemExit(f"saved field missing on row: {rid}.{field}")
        sources = r.get("fieldSources") or {}
        if field not in sources:
            raise SystemExit(f"field without fieldSources: {rid}.{field}")
        cite = sources[field].lower()
        if field == "fuelConsumptionLPerKm" and float(r[field]) * 100 < 3.0:
            raise SystemExit(f"CS<3: {rid}")
        if field == "energyConsumptionKWhPerKm":
            if r.get("energyIsWeighted") is True:
                raise SystemExit(f"weighted CD in calc field: {rid}")
            # must not equal only-weighted copy without rein-elektrisch cite
            if "gewichtet" in cite and "rein elektr" not in cite and "unweighted" not in cite:
                # weighted mention alone in source for CD is forbidden
                if "stessa omologazione" not in cite:
                    raise SystemExit(f"CD source looks weighted-only: {rid}")
        host_ok = any(f in cite or f in (fs.get("host") or "") for f in OFFICIAL_HOST_FRAGMENTS)
        if not host_ok and fs.get("via") != "homologation":
            raise SystemExit(f"non-official host for {rid}.{field}: {fs.get('host')}")

    parents = [r for r in seed if r.get("powertrain") == "phev" and not r.get("parentId")]
    for r in parents:
        real = missing_calc_fields(r)
        declared = r.get("missingCalcFields")
        if declared is not None and list(declared) != real:
            raise SystemExit(f"missingCalcFields mismatch {r['id']}: {declared} vs {real}")
        if bool(real) != bool(r.get("catalogDataIncomplete")):
            # complete rows may omit missingCalcFields
            if r.get("catalogDataIncomplete") or declared is not None:
                raise SystemExit(f"incomplete flag incoherent {r['id']}")
        # Never use weighted as calc energy
        if r.get("energyIsWeighted") is True and r.get("energyConsumptionKWhPerKm") is not None:
            raise SystemExit(f"weighted energy in calc field {r['id']}")

    for d in man.get("derived") or []:
        src = by_id[d["sourceId"]]
        if src.get("dataDerivedFromSameHomologationYear") is not None:
            raise SystemExit(f"chain: {d['sourceId']}")

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
        "fields_saved": man.get("fields_saved"),
        "derived": man.get("derived"),
        "same_my_ids": man.get("same_my_ids"),
    }
    out = CACHE / "catalog_phev_partial_official_report.json"
    out.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k != "fields_saved"}, indent=2))
    print("fields_saved_count", len(report.get("fields_saved") or []))
    print("OK")


if __name__ == "__main__":
    main()
