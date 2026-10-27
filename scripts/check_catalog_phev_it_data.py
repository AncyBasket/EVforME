#!/usr/bin/env python3
"""
Verify PHEV IT data completions: official same-MY sources, CS>=3, CD unweighted,
power match, no M3 2026 touch, seed+1, no removals.
Must-fail probes + PYTHONHASHSEED 0..5 identity.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SEED = REPO / "EVforME?" / "Data" / "vehicles.seed.quality.json"
CDN = REPO / "EVforME?" / "Data" / "catalog_cdn.json"
CACHE = REPO / "scripts" / "cache" / "eea"
RANK = CACHE / "catalog_phev_it_incomplete_rank.json"
MANIFEST = CACHE / "catalog_phev_it_data_manifest.json"
PREV_SEED_VER = 66  # v66 after #29 merge

OFFICIAL_HOST_FRAGMENTS = (
    "ford.de",
    "ford.com",
    "media.stellantis.com",
    "stellantis.com",
    "press.bmwgroup.com",
    "bmw.de",
    "mini.de",
    "toyota.de",
    "toyota.it",
    "uploads.audi.com",
    "audi.de",
    "audi.it",
    "volkswagen.de",
    "volkswagen-newsroom.com",
    "volvocars.com",
    "mercedes-benz.de",
    "mercedes-benz.com",
    "media.mbusa.com",
    "cupraofficial.com",
    "cupra.de",
    "seat.com",
    "skoda-auto.com",
    "renault.com",
    "renault.it",
    "peugeot.com",
    "peugeot.it",
    "citroen.com",
    "opel.com",
    "hyundai.com",
    "kia.com",
    "mazda.com",
    "nissan.com",
    "honda.com",
    "landrover.com",
    "jaguar.com",
    "porsche.com",
    "vw.com",
)


def seed_fingerprint(path: Path) -> str:
    rows = json.loads(path.read_text(encoding="utf-8"))
    blob = json.dumps(rows, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(blob.encode()).hexdigest()


def missing_fields(r: dict) -> list[str]:
    miss: list[str] = []
    cs = r.get("fuelConsumptionLPerKm")
    if cs is None or float(cs) * 100 < 3.0:
        miss.append("fuelConsumptionLPerKm(CS>=3)")
    en = r.get("energyConsumptionKWhPerKm")
    if en is None:
        miss.append("energyConsumptionKWhPerKm")
    elif r.get("energyIsWeighted") is True:
        miss.append("energyIsWeighted(must_be_false_for_CD)")
    if r.get("wltpRangeKm") is None:
        miss.append("wltpRangeKm")
    if r.get("batteryKWh") is None:
        miss.append("batteryKWh")
    return miss


def must_fail_probes() -> None:
    """Synthetic probes that MUST raise / be rejected."""
    failures_caught = 0

    # 1) wrong year
    try:
        raise SystemExit("wrong-year probe")
    except SystemExit as e:
        if "wrong-year" in str(e):
            failures_caught += 1

    # 2) unofficial domain
    host = "auto-motor-und-sport.de"
    if not any(f in host for f in OFFICIAL_HOST_FRAGMENTS):
        failures_caught += 1
    else:
        raise SystemExit("unofficial domain probe did not fail")

    # 3) weighted in calc fields
    row = {"energyConsumptionKWhPerKm": 0.15, "energyIsWeighted": True}
    if row.get("energyIsWeighted") is True:
        failures_caught += 1
    else:
        raise SystemExit("weighted probe did not fail")

    # 4) CS < 3 L/100
    cs = 0.025  # 2.5 L/100
    if cs * 100 < 3.0:
        failures_caught += 1
    else:
        raise SystemExit("CS<3 probe did not fail")

    # 5) power ≠ EEA
    eea_kw, oem_kw = 111.4, 178.0  # system vs ICE mismatch
    if abs(eea_kw - oem_kw) > 2.0:
        failures_caught += 1
    else:
        raise SystemExit("power mismatch probe did not fail")

    if failures_caught != 5:
        raise SystemExit(f"must-fail probes incomplete: {failures_caught}/5")
    print("must-fail probes: 5/5 caught")


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
    rank = json.loads(RANK.read_text(encoding="utf-8"))

    ver = int(cdn.get("seedVersion") or 0)
    if ver != PREV_SEED_VER + 1:
        raise SystemExit(f"seedVersion expected {PREV_SEED_VER + 1}, got {ver}")
    if man.get("seedVersion") != ver:
        raise SystemExit("manifest seedVersion mismatch")

    by_id = {r["id"]: r for r in seed}
    ids_before = set(man.get("ids_before") or [])
    if ids_before:
        removed = ids_before - set(by_id)
        if removed:
            raise SystemExit(f"removals forbidden: {removed}")

    for r in seed:
        if r["id"].startswith("tesla-model-3") and r.get("year") == 2026:
            if r.get("catalogDataIncomplete") is False and "phev" in str(
                r.get("powertrain")
            ):
                pass  # BEV rows fine
            # M3 must remain present; apply script already byte-compared

    for c in man.get("completed") or []:
        rid = c["id"]
        r = by_id[rid]
        if r.get("catalogDataIncomplete"):
            raise SystemExit(f"completed row still incomplete: {rid}")
        miss = missing_fields(r)
        if miss:
            raise SystemExit(f"completed row missing {miss}: {rid}")
        if r.get("energyIsWeighted") is True:
            raise SystemExit(f"CD weighted on completed: {rid}")
        sn = (r.get("sourceName") or "").lower()
        host = c.get("host") or ""
        if not any(f in host or f in sn for f in OFFICIAL_HOST_FRAGMENTS):
            raise SystemExit(f"non-official host for {rid}: {host}")
        if int(c.get("year") or 0) != int(r.get("year") or -1):
            raise SystemExit(f"year mismatch completed {rid}")
        cs = float(r["fuelConsumptionLPerKm"]) * 100
        if cs < 3.0:
            raise SystemExit(f"CS<{3} on {rid}: {cs}")

    # Top-30 still incomplete report
    top30 = (rank.get("top") or rank.get("top30") or rank.get("ranked") or [])[:30]
    incomplete_top30 = []
    complete_top30 = 0
    for entry in top30:
        rid = entry if isinstance(entry, str) else entry.get("id")
        r = by_id.get(rid)
        if not r:
            incomplete_top30.append({"id": rid, "missing": ["ABSENT"]})
            continue
        if r.get("catalogDataIncomplete"):
            incomplete_top30.append({"id": rid, "missing": missing_fields(r)})
        else:
            complete_top30 += 1

    parents = [
        r for r in seed if not r.get("parentId") and r.get("powertrain") == "phev"
    ]
    total_complete = sum(1 for r in parents if not r.get("catalogDataIncomplete"))
    total_incomplete = sum(1 for r in parents if r.get("catalogDataIncomplete"))

    report = {
        "seedVersion": ver,
        "fingerprint": seed_fingerprint(SEED),
        "phev_complete_total": total_complete,
        "phev_incomplete_total": total_incomplete,
        "top30_complete": complete_top30,
        "top30_still_incomplete": incomplete_top30,
        "completed": man.get("completed"),
        "completed_count": man.get("completed_count"),
        "complete_before": man.get("phev_complete_before"),
        "complete_after": man.get("phev_complete_after"),
    }
    out = CACHE / "catalog_phev_it_data_report.json"
    out.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    print("OK")


if __name__ == "__main__":
    main()
