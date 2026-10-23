#!/usr/bin/env python3
"""
Fail if EEA IT Status F+P (or 2022 diesel/DIESEL casing) are still summed into n,
or if any EEA-labeled seed row cites an n that does not match the Status-F
cell (P if F absent or F≪P) for the same variant / fuel / year.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import fill_catalog_fuels_from_eea as eea
import fix_catalog_truth as truth
import refresh_eea_status_f_caches as refresh

# (cache file, Cn, year, ft_norm, expect_n_after_F, bad_summed_n)
CASES = [
    # 2022: F under 'diesel', P under 'DIESEL' — case-dedupe + Status F → half
    ("IT_MERCEDES-BENZ_fuels.json", "C 220 D", 2022, "DIESEL", 1218.0, 2436.0),
    ("IT_TOYOTA_fuels.json", "TOYOTA LAND CRUISER (150 SERIES)", 2022, "DIESEL", 264.0, 528.0),
    # 2024: F+P in the same Ft bucket
    ("IT_MERCEDES-BENZ_fuels.json", "C 200 D", 2024, "DIESEL", 845.0, 1690.0),
    ("IT_RENAULT_fuels.json", "SCENIC E-TECH ELECTRIC", 2024, "ELECTRIC", 449.0, 898.0),
    ("IT_DS_fuels.json", "DS7", 2024, "DIESEL", 2927.0, 5854.0),
    ("IT_VOLKSWAGEN_fuels.json", "TOUAREG", 2024, "DIESEL", 317.0, 634.0),
    # Uneven F vs P (not a clean double)
    ("IT_ALFA_ROMEO_fuels.json", "STELVIO", 2023, "DIESEL", 6120.0, 12240.0),
    ("IT_KIA_fuels.json", "CEED", 2019, "PETROL", 1297.0, 1788.0),
]

N_PAT = re.compile(r"\bn=(\d+)\b")
EEA_LABEL_PAT = re.compile(r"^EEA\b", re.I)

# Seed rows that must cite these n values after Status-F recalc.
SEED_N_CASES = [
    ("alfa-romeo-stelvio-diesel-2023", 6120),
    ("kia-ceed-2019", 1297),
]


def _normalize_ice_keys(ice: dict, hev: dict) -> None:
    for maps in (ice, hev):
        for key in list(maps.keys()):
            if "_" in key and key != "MERCEDES-BENZ":
                fixed = key.replace("_", " ")
                if fixed not in maps or len(maps[fixed]) < len(maps[key]):
                    maps[fixed] = maps.pop(key)
                elif key in maps:
                    maps.pop(key, None)


def main() -> int:
    failures: list[str] = []
    for fname, model, year, ft, expect_n, bad_sum in CASES:
        path = eea.CACHE_DIR / fname
        if not path.is_file():
            failures.append(f"missing cache {fname}")
            continue
        wrap = json.loads(path.read_text(encoding="utf-8"))
        found = False
        for mb in wrap["response"]["aggregations"]["models"]["buckets"]:
            if mb.get("key") != model:
                continue
            for yb in mb["years"]["buckets"]:
                if int(yb["key"]) != year:
                    continue
                fuels = yb["fuels"]["buckets"]
                deduped = eea.dedupe_fuel_buckets(fuels)
                got = float(deduped.get(ft, {}).get("n") or 0)
                found = True
                has_status = any((f.get("status") or {}).get("buckets") for f in fuels)
                if not has_status and year <= 2024:
                    failures.append(
                        f"{fname} {model} {year}: missing Status sub-agg (re-fetch caches)"
                    )
                if abs(got - expect_n) > 0.5:
                    failures.append(
                        f"{fname} {model} {year}: n={got} want {expect_n} "
                        f"(must not be F+P sum {bad_sum})"
                    )
                if abs(got - bad_sum) < 0.5:
                    failures.append(f"{fname} {model} {year}: still summing F+P to {got}")
        if not found:
            failures.append(f"missing cell {fname} {model} {year}")

    ice = truth.load_ice_maps()
    hev = truth.load_hev_maps()
    _normalize_ice_keys(ice, hev)

    checks = [
        ("MERCEDES-BENZ", ("C220D", 2022, "DIESEL"), 1218.0),
        ("MERCEDES-BENZ", ("C200D", 2024, "DIESEL"), 845.0),
        ("TOYOTA", ("LANDCRUISER150SERIES", 2022, "DIESEL"), 264.0),
        ("RENAULT", ("SCENICETECHELECTRIC", 2024, "ELECTRIC"), 449.0),
        ("ALFA ROMEO", ("STELVIO", 2023, "DIESEL"), 6120.0),
        ("KIA", ("CEED", 2019, "PETROL"), 1297.0),
    ]
    for brand, key, expect in checks:
        got = float((ice.get(brand) or {}).get(key, {}).get("n") or 0)
        if abs(got - expect) > 0.5:
            failures.append(f"ice_map {brand} {key}: n={got} want {expect}")

    # 2025 is P-only — S 450 d must stay 54
    s450 = float(
        (ice.get("MERCEDES-BENZ") or {}).get(("S450D4MATIC", 2025, "DIESEL"), {}).get("n") or 0
    )
    if abs(s450 - 54.0) > 0.5:
        failures.append(f"ice_map S450D4MATIC 2025: n={s450} want 54 (P-only year)")

    rows: list[dict] = json.loads(truth.SEED_PATH.read_text(encoding="utf-8"))
    by_id = {r["id"]: r for r in rows}
    for rid, expect_n in SEED_N_CASES:
        row = by_id.get(rid)
        if not row:
            failures.append(f"missing seed row {rid}")
            continue
        sn = str(row.get("sourceName") or "")
        m = N_PAT.search(sn)
        cited = int(m.group(1)) if m else None
        if cited != expect_n:
            failures.append(f"seed {rid}: sourceName n={cited} want {expect_n} ({sn})")

    # Every EEA-labeled row must match Status-F (else P) for same variant/fuel/year.
    mismatch = 0
    unresolved = 0
    for r in rows:
        sn = str(r.get("sourceName") or "")
        if not EEA_LABEL_PAT.match(sn) or "n=" not in sn:
            continue
        m = N_PAT.search(sn)
        if not m:
            failures.append(f"EEA row {r.get('id')}: sourceName missing n= ({sn})")
            unresolved += 1
            continue
        cited = int(m.group(1))
        hit = refresh.resolve_label_cell(r, ice, hev)
        if not hit:
            failures.append(f"EEA row {r.get('id')}: unresolved Status-F cell ({sn})")
            unresolved += 1
            continue
        mn, ft, cell, ey = hit
        cite_y = refresh._cite_year(sn, int(r.get("year") or 0))
        if int(ey) != cite_y:
            failures.append(
                f"EEA row {r.get('id')}: resolved year {ey} != cited year {cite_y}"
            )
            unresolved += 1
            continue
        real = int(float(cell.get("n") or 0))
        if cited != real:
            failures.append(
                f"EEA row {r.get('id')}: cited n={cited} != Status-F n={real} "
                f"({mn} {ft} {ey})"
            )
            mismatch += 1

    if failures:
        print("EEA Status F/P dedupe FAIL:", file=sys.stderr)
        for line in failures[:80]:
            print(" ", line, file=sys.stderr)
        if len(failures) > 80:
            print(f"  … and {len(failures) - 80} more", file=sys.stderr)
        print(
            f"total failures={len(failures)} mismatch={mismatch} unresolved={unresolved}",
            file=sys.stderr,
        )
        return 1
    print("EEA Status F/P dedupe OK (all EEA n= labels match Status F/P cells)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
