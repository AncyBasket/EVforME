#!/usr/bin/env python3
"""
Fail if EEA IT Status F+P (or 2022 diesel/DIESEL casing) are still summed into n.

Root cause: co2cars lists each IT registration under Status F (final) and P
(provisional) through ~2024. In 2022 those copies also used different Ft casing
(diesel vs DIESEL). Prefer Status F; fall back to P when F is absent (e.g. 2025).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import fill_catalog_fuels_from_eea as eea
import fix_catalog_truth as truth

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
]


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
                # Confirm Status sub-agg exists on refreshed caches
                has_status = any((f.get("status") or {}).get("buckets") for f in fuels)
                if not has_status and year <= 2024:
                    failures.append(f"{fname} {model} {year}: missing Status sub-agg (re-fetch caches)")
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
    checks = [
        ("MERCEDES-BENZ", ("C220D", 2022, "DIESEL"), 1218.0),
        ("MERCEDES-BENZ", ("C200D", 2024, "DIESEL"), 845.0),
        ("TOYOTA", ("LANDCRUISER150SERIES", 2022, "DIESEL"), 264.0),
        ("RENAULT", ("SCENICETECHELECTRIC", 2024, "ELECTRIC"), 449.0),
    ]
    for brand, key, expect in checks:
        got = float((ice.get(brand) or {}).get(key, {}).get("n") or 0)
        if abs(got - expect) > 0.5:
            failures.append(f"ice_map {brand} {key}: n={got} want {expect}")

    # 2025 is P-only — S 450 d must stay 54
    s450 = float((ice.get("MERCEDES-BENZ") or {}).get(("S450D4MATIC", 2025, "DIESEL"), {}).get("n") or 0)
    if abs(s450 - 54.0) > 0.5:
        failures.append(f"ice_map S450D4MATIC 2025: n={s450} want 54 (P-only year)")

    if failures:
        print("EEA Status F/P dedupe FAIL:", file=sys.stderr)
        for line in failures:
            print(" ", line, file=sys.stderr)
        return 1
    print("EEA Status F/P dedupe OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
