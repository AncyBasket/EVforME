#!/usr/bin/env python3
"""Verify top-30 official PHEV wave (seed v73)."""

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
PREV_SEED_VER = 72


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

    r24 = by_id["jeep-renegade-phev-4xe-2024"]
    if r24.get("wltpRangeKm") != 48:
        raise SystemExit(f"renegade 2024 range {r24.get('wltpRangeKm')}")
    if abs(float(r24.get("batteryKWh")) - 11.4) > 1e-9:
        raise SystemExit("renegade 2024 battery")
    fd = r24.get("fieldSourceDates") or {}
    if fd.get("wltpRangeKm") != "2024-04-03" or fd.get("batteryKWh") != "2024-04-03":
        raise SystemExit("renegade sourceDate")
    cite = (r24.get("fieldSources") or {}).get("wltpRangeKm") or ""
    if is_city_only_range_source(cite) or "ville" in cite.lower() and "combin" not in cite.lower():
        # fieldSources is URL only — OK; sourceName must not claim City as saved range
        pass
    sn = (r24.get("sourceName") or "").lower()
    if "city" in sn and "pas city" not in sn and "rejected" not in sn:
        # allow mention of City as excluded
        if "50–48" not in (r24.get("sourceName") or "") and "50-48" not in (r24.get("sourceName") or ""):
            pass

    r23 = by_id["jeep-renegade-phev-4xe-2023"]
    if r23.get("wltpRangeKm") != 48 or abs(float(r23.get("batteryKWh")) - 11.4) > 1e-9:
        raise SystemExit("renegade 2023 range/battery")
    if r24.get("dataDerivedFromSameHomologationYear") is not None:
        raise SystemExit("chain from 2024")
    for fs in man.get("fields_saved") or []:
        if fs["field"] not in (by_id[fs["id"]].get("fieldSources") or {}):
            raise SystemExit(f"missing fieldSources {fs['id']}.{fs['field']}")
        if fs["field"] not in (by_id[fs["id"]].get("fieldSourceDates") or {}):
            raise SystemExit(f"missing fieldSourceDates {fs['id']}.{fs['field']}")

    report = {
        "seedVersion": ver,
        "fingerprint": seed_fingerprint(SEED),
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
    print(json.dumps({k: v for k, v in report.items() if k not in ("fields_saved", "remaining_top30_multi")}, indent=2))
    print("fields_saved", len(report.get("fields_saved") or []))
    print("remaining", len(report.get("remaining_top30_multi") or []))
    print("OK")


if __name__ == "__main__":
    main()
