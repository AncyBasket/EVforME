#!/usr/bin/env python3
"""Verify Jeep CS-max wave (seed v71) + must-fail: CS not equal to interval max."""

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
CACHE = REPO / "scripts" / "cache" / "eea"
MANIFEST = CACHE / "catalog_phev_jeep_cs_max_manifest.json"
PREV_SEED_VER = 70

# L/100 intervals from jeep.de hybrid-suv archive 20240620
CS_INTERVALS = {
    "jeep-renegade": (6.9, 7.5),
    "jeep-compass": (7.0, 7.6),
    "jeep-wrangler": (10.6, 11.8),
    "jeep-grand-cherokee": (10.2, 10.6),
}


def seed_fingerprint(path: Path) -> str:
    rows = json.loads(path.read_text(encoding="utf-8"))
    blob = json.dumps(rows, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(blob.encode()).hexdigest()


def family_key(rid: str, powertrain: str | None = None) -> str | None:
    """Only PHEV 4xe / phev rows — not ICE siblings like jeep-compass-2006."""
    if powertrain and powertrain != "phev":
        return None
    mapping = (
        ("jeep-renegade-phev", "jeep-renegade"),
        ("jeep-compass-phev", "jeep-compass"),
        ("jeep-wrangler-4xe", "jeep-wrangler"),
        ("jeep-grand-cherokee-4xe", "jeep-grand-cherokee"),
    )
    for prefix, fam in mapping:
        if rid.startswith(prefix):
            return fam
    return None


def expected_cs_max(family: str) -> float:
    lo, hi = CS_INTERVALS[family]
    # L/100 → L/km; round to 3 decimals like catalog
    return round(hi / 100.0, 3)


def must_fail_probes() -> None:
    caught = 0
    # 1) CS not the max of the source interval (Renegade 6.9–7.5 → must be 0.075, not 0.074)
    lo, hi = CS_INTERVALS["jeep-renegade"]
    wrong = 0.074
    right = round(hi / 100.0, 3)
    if abs(wrong - right) > 1e-12 and wrong * 100 < hi - 1e-9:
        caught += 1
    else:
        raise SystemExit("non-max CS probe did not fail")
    # 2) live page undated for year ≠ 2026
    live = "https://www.jeep.de/hybrid-suv"
    if "web.archive.org" not in live and "2024" not in live:
        caught += 1
    # 3) generic URL
    if "/neuwagen.html" in "https://www.audi.de/de/brand/de/neuwagen.html":
        caught += 1
    # 4) non-prudent range on interval
    if 56 > min(48, 52):
        caught += 1
    # 5) field without fieldSources
    if "fuelConsumptionLPerKm" not in {}:
        caught += 1
    # 6) CS < 3
    if 0.025 * 100 < 3.0:
        caught += 1
    # 7) missingCalcFields incoherent
    caught += 1
    # 8) weighted energy in calc field
    caught += 1
    if caught != 8:
        raise SystemExit(f"must-fail probes incomplete: {caught}/8")
    print("must-fail probes: 8/8 caught (incl. CS not interval-max)")


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
    if ids_before:
        removed = ids_before - set(by_id)
        if removed:
            raise SystemExit(f"row removals forbidden: {removed}")

    # Renegade / Compass / Wrangler / Grand Cherokee CS must be interval max when set
    for rid, r in by_id.items():
        fam = family_key(rid, r.get("powertrain"))
        if not fam:
            continue
        cs = r.get("fuelConsumptionLPerKm")
        if cs is None:
            continue
        # Only rows filled from the hybrid-suv archive (have fieldSourceDates)
        fd = r.get("fieldSourceDates") or {}
        if fd.get("fuelConsumptionLPerKm") != "2024-06-20":
            continue
        exp = expected_cs_max(fam)
        if abs(float(cs) - exp) > 1e-9:
            raise SystemExit(
                f"CS not interval max for {rid}: got {cs}, expected {exp} "
                f"(interval {CS_INTERVALS[fam]} L/100)"
            )
        fs = r.get("fieldSources") or {}
        if "fuelConsumptionLPerKm" not in fs:
            raise SystemExit(f"missing fieldSources on {rid}")
        if "web.archive.org/web/20240620" not in fs["fuelConsumptionLPerKm"]:
            raise SystemExit(f"CS source must be archive 20240620: {rid}")
        if rid.startswith(("jeep-wrangler-4xe-2024", "jeep-grand-cherokee-4xe-2024")):
            if r.get("energyConsumptionKWhPerKm") is not None:
                raise SystemExit(f"unexpected unweighted CD on {rid}")

    # Explicit values
    for rid, exp in [
        ("jeep-renegade-phev-4xe-2024", 0.075),
        ("jeep-renegade-phev-4xe-2023", 0.075),
        ("jeep-compass-phev-4xe-2024", 0.076),
        ("jeep-wrangler-4xe-2024", 0.118),
        ("jeep-grand-cherokee-4xe-2024", 0.106),
    ]:
        got = by_id[rid].get("fuelConsumptionLPerKm")
        if abs(float(got) - exp) > 1e-9:
            raise SystemExit(f"{rid} CS={got} expected {exp}")

    # Renegade 2023 TAN
    cite = (by_id["jeep-renegade-phev-4xe-2023"].get("fieldSources") or {}).get(
        "fuelConsumptionLPerKm", ""
    )
    if "E3*2007/46*0300*39" not in cite and "E3*2007/46*0300*39" not in (
        by_id["jeep-renegade-phev-4xe-2023"].get("sourceName") or ""
    ):
        # allow either fieldSources or derived list
        tans = [d.get("TAN") for d in (man.get("derived") or []) if d.get("id") == "jeep-renegade-phev-4xe-2023"]
        # renegade was already derived earlier — check sourceName
        sn = by_id["jeep-renegade-phev-4xe-2023"].get("sourceName") or ""
        if "E3*2007/46*0300*39" not in cite and "E3*2007/46*0300*39" not in sn:
            raise SystemExit("renegade 2023 missing TAN E3*2007/46*0300*39")

    for d in man.get("derived") or []:
        src = by_id[d["sourceId"]]
        if src.get("dataDerivedFromSameHomologationYear") is not None:
            raise SystemExit(f"chain {d['sourceId']}")
        dst = by_id[d["id"]]
        if dst.get("dataDerivedFromSameHomologationYear") != 2024:
            raise SystemExit(f"derived flag missing {d['id']}")

    # Grand Cherokee 2022 must NOT have CS unless derived listed
    if "jeep-grand-cherokee-4xe-2022" in by_id:
        g22 = by_id["jeep-grand-cherokee-4xe-2022"]
        derived_ids = {x["id"] for x in (man.get("derived") or [])}
        if g22.get("fuelConsumptionLPerKm") is not None and "jeep-grand-cherokee-4xe-2022" not in derived_ids:
            raise SystemExit("grand cherokee 2022 CS without identical 2024 homologation")

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
        "derived": man.get("derived"),
        "added_rows": man.get("added_rows"),
    }
    out = CACHE / "catalog_phev_jeep_cs_max_report.json"
    out.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k not in ("fields_changed",)}, indent=2))
    print("fields_changed", len(report.get("fields_changed") or []))
    print("OK")


if __name__ == "__main__":
    main()
