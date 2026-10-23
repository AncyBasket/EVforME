#!/usr/bin/env python3
"""Fail if DIESEL/diesel (case) buckets are summed instead of deduped to max-n."""

from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import fill_catalog_fuels_from_eea as eea

# Known 2022 case-duplicate cells (raw sum_r twice the real volume).
CASES = [
    ("IT_MERCEDES-BENZ_fuels.json", "C 220 D", 2022, "DIESEL", 1218.0, 2436.0),
    ("IT_TOYOTA_fuels.json", "TOYOTA LAND CRUISER (150 SERIES)", 2022, "DIESEL", 264.0, 528.0),
]


def main() -> int:
    failures: list[str] = []
    for fname, model, year, ft, expect_n, bad_sum in CASES:
        path = eea.CACHE_DIR / fname
        wrap = json.loads(path.read_text(encoding="utf-8"))
        found = False
        for mb in wrap["response"]["aggregations"]["models"]["buckets"]:
            if mb.get("key") != model:
                continue
            for yb in mb["years"]["buckets"]:
                if int(yb["key"]) != year:
                    continue
                fuels = yb["fuels"]["buckets"]
                keys = [str(f.get("key")) for f in fuels]
                if len({k.upper() for k in keys}) < len(keys):
                    # case duplicates present — good, we can test
                    pass
                deduped = eea.dedupe_fuel_buckets(fuels)
                got = float(deduped.get(ft, {}).get("n") or 0)
                found = True
                if abs(got - expect_n) > 0.5:
                    failures.append(
                        f"{fname} {model} {year}: deduped n={got} want {expect_n} "
                        f"(must not be summed {bad_sum}); keys={keys}"
                    )
                if abs(got - bad_sum) < 0.5:
                    failures.append(f"{fname} {model} {year}: still summing case duplicates to {got}")
        if not found:
            failures.append(f"missing cell {fname} {model} {year}")

    # parse_brand_aggs must expose the deduped n
    import fix_catalog_truth as truth

    ice = truth.load_ice_maps()
    c = ice["MERCEDES-BENZ"].get(("C220D", 2022, "DIESEL"), {})
    if abs(float(c.get("n") or 0) - 1218.0) > 0.5:
        failures.append(f"ice_map C220D 2022 n={c.get('n')} want 1218")
    lc = ice["TOYOTA"].get(("LANDCRUISER150SERIES", 2022, "DIESEL"), {})
    if abs(float(lc.get("n") or 0) - 264.0) > 0.5:
        failures.append(f"ice_map LANDCRUISER150SERIES 2022 n={lc.get('n')} want 264")

    if failures:
        print("EEA fuel bucket dedupe FAIL:", file=sys.stderr)
        for line in failures:
            print(" ", line, file=sys.stderr)
        return 1
    print("EEA fuel bucket dedupe OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
