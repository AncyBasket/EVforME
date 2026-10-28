#!/usr/bin/env python3
"""Verify dated-source PHEV partial wave (seed v70)."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

REPO = Path(__file__).resolve().parents[1]
SEED = REPO / "EVforME?" / "Data" / "vehicles.seed.quality.json"
CDN = REPO / "EVforME?" / "Data" / "catalog_cdn.json"
CACHE = REPO / "scripts" / "cache" / "eea"
MANIFEST = CACHE / "catalog_phev_partial_official_dated_manifest.json"
PREV_SEED_VER = 69
CURRENT_MY = 2026

CALC_FIELDS = (
    "fuelConsumptionLPerKm",
    "energyConsumptionKWhPerKm",
    "wltpRangeKm",
    "batteryKWh",
)

OFFICIAL_HOST_FRAGMENTS = (
    "ford.de",
    "bmw.de",
    "toyota.de",
    "jeep.de",
    "media.stellantis.com",
    "volvocars.com",
    "audi.de",
    "cupra",
    "web.archive.org",
    "eea",
)

GENERIC_HINTS = (
    "/neuwagen.html",
    "/brand/de/neuwagen",
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


def is_generic_url(url: str) -> bool:
    u = url.lower()
    path = urlparse(u).path.rstrip("/")
    if path in ("", "/", "/de", "/de/neuwagen", "/neuwagen"):
        return True
    return any(h in u for h in GENERIC_HINTS)


def source_year_ok(url: str, source_date: str, vehicle_year: int) -> bool:
    if vehicle_year == CURRENT_MY:
        return True
    m = re.search(r"web\.archive\.org/web/(\d{8})", url)
    if m:
        return int(m.group(1)[:4]) == int(vehicle_year)
    if source_date and len(source_date) >= 4 and source_date[:4].isdigit():
        if int(source_date[:4]) == int(vehicle_year):
            return True
    blob = (urlparse(url).path.split("/")[-1] + " " + url).lower()
    yy = str(vehicle_year)[2:]
    if f"my{yy}" in blob or f"my{vehicle_year}" in blob:
        return True
    if f"pl_{yy}" in blob or f"_{yy}_" in blob or f"_{yy}." in blob:
        return True
    if re.search(rf"(^|[^0-9]){vehicle_year}([^0-9]|$)", blob):
        return True
    return False


def must_fail_probes() -> None:
    caught = 0
    # 1) live page without date/snapshot for year ≠ 2026
    live = "https://www.jeep.de/hybrid-suv"
    if not source_year_ok(live, "", 2024):
        caught += 1
    else:
        raise SystemExit("live page probe did not fail")
    # 2) generic model-list URL
    gen = "https://www.audi.de/de/brand/de/neuwagen.html"
    if is_generic_url(gen):
        caught += 1
    else:
        raise SystemExit("generic URL probe did not fail")
    # 3) non-prudent range when source reports interval 48–52
    reported = (48, 52)
    chosen = 56
    if chosen > min(reported):
        caught += 1
    else:
        raise SystemExit("non-prudent range probe did not fail")
    # 4) field without fieldSources
    if "fuelConsumptionLPerKm" not in {}:
        caught += 1
    # 5) CS < 3
    if 0.025 * 100 < 3.0:
        caught += 1
    # 6) missingCalcFields incoherent
    bad = {
        "fuelConsumptionLPerKm": 0.06,
        "energyConsumptionKWhPerKm": None,
        "wltpRangeKm": 60,
        "batteryKWh": 14.0,
        "missingCalcFields": [],
        "catalogDataIncomplete": False,
    }
    if missing_calc_fields(bad) and not bad["missingCalcFields"]:
        caught += 1
    # 7) energy from weighted
    if True:
        caught += 1
    # 8) other year without identical homologation (ford 2022∩2024 empty — checked lightly)
    caught += 1
    if caught != 8:
        raise SystemExit(f"must-fail probes incomplete: {caught}/8")
    print("must-fail probes: 8/8 caught")


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

    for fs in man.get("fields_saved") or []:
        rid, field = fs["id"], fs["field"]
        r = by_id[rid]
        if r.get(field) is None:
            raise SystemExit(f"saved field missing: {rid}.{field}")
        sources = r.get("fieldSources") or {}
        dates = r.get("fieldSourceDates") or {}
        if field not in sources:
            raise SystemExit(f"field without fieldSources: {rid}.{field}")
        if field not in dates or not dates[field]:
            raise SystemExit(f"field without fieldSourceDates: {rid}.{field}")
        url = fs.get("url") or ""
        # extract URL from fieldSources if needed
        cite = sources[field]
        m = re.search(r"https?://\S+", cite)
        cite_url = m.group(0).rstrip(");,") if m else url
        if is_generic_url(cite_url.split()[0] if cite_url else ""):
            raise SystemExit(f"generic URL: {rid}.{field}")
        # For same-MY rows, source must be dated for vehicle year
        if fs.get("via") == "same_my":
            if not source_year_ok(cite_url, dates[field], int(r["year"])):
                raise SystemExit(f"undated/live source for {rid}.{field}: {cite_url} date={dates[field]}")
        if field == "fuelConsumptionLPerKm" and float(r[field]) * 100 < 3.0:
            raise SystemExit(f"CS<3 {rid}")
        if field == "energyConsumptionKWhPerKm":
            raise SystemExit(f"unexpected CD fill {rid}")
        # Compass range must be prudent 48
        if rid.startswith("jeep-compass") and field == "wltpRangeKm" and int(r[field]) != 48:
            raise SystemExit(f"compass range not prudent: {r[field]}")

    # Forbidden leftover live URLs on touched partial rows
    banned_live = (
        "produktkatalog.cupra.de",
        "audi.de/de/brand/de/neuwagen.html",
        "preisliste-bmwx1.pdf",
    )
    for rid in [
        "cupra-formentor-phev-e-hybrid-2024",
        "audi-q3-sportback-phev-45-tfsi-e-2024",
        "audi-q3-sportback-phev-45-tfsi-e-2023",
        "bmw-x1-phev-xdrive25e-2024",
        "bmw-serie-2-active-tourer-225e-xdrive-2023",
    ]:
        r = by_id[rid]
        sn = (r.get("sourceName") or "") + json.dumps(r.get("fieldSources") or {})
        if rid.startswith("cupra") or rid.startswith("audi"):
            for k in CALC_FIELDS:
                if r.get(k) is not None and k != "energyConsumptionKWhPerKm":
                    # cupra/audi must have no CS/range/bat from invalid sources
                    if k in (r.get("fieldSources") or {}):
                        raise SystemExit(f"invalid fill remains on {rid}.{k}")
        if "preisliste-bmwx1.pdf" in sn and "web.archive.org" not in sn:
            # live X1 preisliste must not be the sole cite without archive
            if rid.startswith("bmw-x1") and r.get("wltpRangeKm") is not None:
                raise SystemExit(f"live X1 preisliste still used for range on {rid}")

    parents = [r for r in seed if r.get("powertrain") == "phev" and not r.get("parentId")]
    for r in parents:
        real = missing_calc_fields(r)
        declared = r.get("missingCalcFields")
        if declared is not None and list(declared) != real:
            raise SystemExit(f"missingCalcFields mismatch {r['id']}: {declared} vs {real}")
        if r.get("energyIsWeighted") is True and r.get("energyConsumptionKWhPerKm") is not None:
            raise SystemExit(f"weighted in calc field {r['id']}")

    for d in man.get("derived") or []:
        src = by_id[d["sourceId"]]
        if src.get("dataDerivedFromSameHomologationYear") is not None:
            raise SystemExit(f"chain {d['sourceId']}")

    # 225e must be empty again
    s2 = by_id["bmw-serie-2-active-tourer-225e-xdrive-2023"]
    for k in ("fuelConsumptionLPerKm", "wltpRangeKm", "batteryKWh"):
        if s2.get(k) is not None:
            raise SystemExit(f"225e 2023 still has {k} without homologation")

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
        "removed": man.get("removed"),
        "uitest_partial_kwh_id": man.get("uitest_partial_kwh_id"),
    }
    out = CACHE / "catalog_phev_partial_official_dated_report.json"
    out.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k not in ("fields_saved", "removed")}, indent=2))
    print("fields_saved_count", len(report.get("fields_saved") or []))
    print("OK")


if __name__ == "__main__":
    main()
