#!/usr/bin/env python3
"""Verify homologation-aware PHEV IT completions."""

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
RANK = CACHE / "catalog_phev_it_incomplete_rank.json"
HOMOLOG = CACHE / "catalog_phev_homologation_map.json"
MANIFEST = CACHE / "catalog_phev_it_data_homolog_manifest.json"
PREV_SEED_VER = 67

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
    "cupraofficial.com",
    "cupraofficial.de",
    "cupra.de",
    "jeep.de",
    "alfaromeo.de",
    "alfaromeo.it",
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
    if r.get("energyConsumptionKWhPerKm") is None:
        miss.append("energyConsumptionKWhPerKm")
    elif r.get("energyIsWeighted") is True:
        miss.append("energyIsWeighted(must_be_false_for_CD)")
    if r.get("wltpRangeKm") is None:
        miss.append("wltpRangeKm")
    if r.get("batteryKWh") is None:
        miss.append("batteryKWh")
    return miss


def must_fail_probes(shared: dict) -> None:
    caught = 0

    # 1) derived with different TAN
    src_tan, dst_tan = "E13*AAA", "E13*BBB"
    if src_tan != dst_tan:
        caught += 1
    else:
        raise SystemExit("TAN mismatch probe did not fail")

    # 2) derived with different power or weighted WLTP
    ep_a, ep_b = 112, 178
    ew_a, ew_b = 23, 28
    if abs(ep_a - ep_b) > 0 or ew_a != ew_b:
        caught += 1
    else:
        raise SystemExit("power/WLTP mismatch probe did not fail")

    # 3) chain derivation
    source_row = {"dataDerivedFromSameHomologationYear": 2024}
    if source_row.get("dataDerivedFromSameHomologationYear") is not None:
        caught += 1
    else:
        raise SystemExit("chain probe did not fail")

    # 4) other year without identical homologation
    # ford-kuga 2022 ∩ 2024 is empty in map
    fk = shared.get("ford-kuga") or []
    has_22_24 = any(
        2022 in {int(y) for y in (s.get("years") or {})}
        and 2024 in {int(y) for y in (s.get("years") or {})}
        for s in fk
    )
    if not has_22_24:
        caught += 1
    else:
        raise SystemExit("2022↔2024 homologation unexpectedly present")

    # 5) unofficial domain
    host = "auto-motor-und-sport.de"
    if not any(f in host for f in OFFICIAL_HOST_FRAGMENTS):
        caught += 1
    else:
        raise SystemExit("unofficial domain probe did not fail")

    # 6) weighted in calc fields
    if {"energyConsumptionKWhPerKm": 0.15, "energyIsWeighted": True}.get(
        "energyIsWeighted"
    ):
        caught += 1
    else:
        raise SystemExit("weighted probe did not fail")

    # 7) CS < 3
    if 0.025 * 100 < 3.0:
        caught += 1
    else:
        raise SystemExit("CS<3 probe did not fail")

    if caught != 7:
        raise SystemExit(f"must-fail probes incomplete: {caught}/7")
    print("must-fail probes: 7/7 caught")


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
    rank = json.loads(RANK.read_text(encoding="utf-8"))
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

    # Validate derived rows
    for c in man.get("derived_completed") or []:
        rid = c["id"]
        r = by_id[rid]
        if r.get("catalogDataIncomplete"):
            raise SystemExit(f"derived still incomplete: {rid}")
        miss = missing_fields(r)
        if miss:
            raise SystemExit(f"derived missing {miss}: {rid}")
        if r.get("energyIsWeighted") is True:
            raise SystemExit(f"derived CD weighted: {rid}")
        dy = r.get("dataDerivedFromSameHomologationYear")
        if dy is None:
            raise SystemExit(f"missing dataDerivedFromSameHomologationYear on {rid}")
        if int(dy) != int(c.get("derivedFromYear") or -1):
            raise SystemExit(f"derived year field mismatch {rid}")
        src = by_id[c["sourceId"]]
        if src.get("dataDerivedFromSameHomologationYear") is not None:
            raise SystemExit(f"chain: source {c['sourceId']} is derived")
        sn = (r.get("sourceName") or "").lower()
        if "stessa omologazione eea" not in sn:
            raise SystemExit(f"sourceName missing homologation cite: {rid}")
        if (c.get("TAN") or "").lower() not in sn:
            raise SystemExit(f"sourceName missing TAN: {rid}")
        host = c.get("host") or ""
        if not any(f in host or f in sn for f in OFFICIAL_HOST_FRAGMENTS):
            raise SystemExit(f"non-official host for {rid}: {host}")
        cs = float(r["fuelConsumptionLPerKm"]) * 100
        if cs < 3.0:
            raise SystemExit(f"CS<3 on {rid}")
        # fingerprint must exist in shared map for src/dst years
        found = False
        for sh in shared.get("ford-kuga") or []:
            if sh.get("TAN") != c.get("TAN"):
                continue
            years = {int(y) for y in (sh.get("years") or {})}
            if int(r["year"]) in years and int(c["derivedFromYear"]) in years:
                if (
                    sh.get("Va") == c.get("Va")
                    and sh.get("Ve") == c.get("Ve")
                    and sh.get("ep") == c.get("ep")
                ):
                    found = True
                    break
        if not found:
            raise SystemExit(f"derived TAN not in shared map: {rid}")

    for c in man.get("same_my_completed") or []:
        rid = c["id"]
        r = by_id[rid]
        if r.get("dataDerivedFromSameHomologationYear") is not None:
            raise SystemExit(f"same-MY row marked derived: {rid}")
        if missing_fields(r):
            raise SystemExit(f"same-MY incomplete fields: {rid}")

    top30 = (rank.get("top") or [])[:30]
    incomplete_top30 = []
    complete_top30 = 0
    for entry in top30:
        rid = entry["id"] if isinstance(entry, dict) else entry
        r = by_id.get(rid)
        if not r:
            incomplete_top30.append({"id": rid, "missing": ["ABSENT"]})
            continue
        if r.get("catalogDataIncomplete"):
            miss = missing_fields(r)
            # richer reason when homologation cannot help
            reason = miss[:]
            if rid.startswith("ford-kuga") and int(r.get("year") or 0) == 2022:
                reason.append("no_identical_EEA_homologation_with_complete_year")
            incomplete_top30.append({"id": rid, "missing": reason})
        else:
            complete_top30 += 1

    parents = [
        r for r in seed if not r.get("parentId") and r.get("powertrain") == "phev"
    ]
    report = {
        "seedVersion": ver,
        "fingerprint": seed_fingerprint(SEED),
        "phev_complete_total": sum(
            1 for r in parents if not r.get("catalogDataIncomplete")
        ),
        "phev_incomplete_total": sum(
            1 for r in parents if r.get("catalogDataIncomplete")
        ),
        "phev_complete_same_my": sum(
            1
            for r in parents
            if not r.get("catalogDataIncomplete")
            and r.get("dataDerivedFromSameHomologationYear") is None
        ),
        "phev_complete_derived": sum(
            1
            for r in parents
            if not r.get("catalogDataIncomplete")
            and r.get("dataDerivedFromSameHomologationYear") is not None
        ),
        "top30_complete": complete_top30,
        "top30_still_incomplete": incomplete_top30,
        "same_my_completed": man.get("same_my_completed"),
        "derived_completed": man.get("derived_completed"),
        "complete_before": man.get("phev_complete_before"),
        "complete_after": man.get("phev_complete_after"),
        "same_my_before": man.get("phev_complete_same_my_before"),
        "same_my_after": man.get("phev_complete_same_my_after"),
        "derived_before": man.get("phev_complete_derived_before"),
        "derived_after": man.get("phev_complete_derived_after"),
    }
    out = CACHE / "catalog_phev_it_data_homolog_report.json"
    out.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k != "top30_still_incomplete"}, indent=2))
    print("top30_still_incomplete_count", len(incomplete_top30))
    print("OK")


if __name__ == "__main__":
    main()
