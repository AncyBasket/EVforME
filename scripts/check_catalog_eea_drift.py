#!/usr/bin/env python3
"""
Fail if any catalog row with an EEA IT match drifts more than ±20% on consumption.

Uses scripts/cache/eea/catalog_truth_eea_refs.json (written by fix_catalog_truth.py)
and/or live cache aggregates.

Exit 0 = OK, 1 = drift, 2 = missing refs.
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

TOLERANCE = 0.20
REFS_PATH = truth.REFS_PATH
SEED_PATH = truth.SEED_PATH


def main() -> int:
    if not REFS_PATH.is_file():
        print(f"missing refs: {REFS_PATH} — run fix_catalog_truth.py first", file=sys.stderr)
        return 2
    rows = {r["id"]: r for r in json.loads(SEED_PATH.read_text(encoding="utf-8"))}
    refs = json.loads(REFS_PATH.read_text(encoding="utf-8"))
    failures: list[str] = []
    checked = 0
    for ref in refs:
        rid = ref.get("id")
        row = rows.get(rid)
        if not row:
            failures.append(f"{rid}: missing from seed")
            continue
        if "eea_l100" in ref:
            old = row.get("fuelConsumptionLPerKm")
            if not isinstance(old, (int, float)) or old <= 0:
                failures.append(f"{rid}: missing fuelConsumptionLPerKm")
                continue
            old100 = float(old) * 100
            exp = float(ref["eea_l100"])
            drift = abs(old100 - exp) / exp
            checked += 1
            if drift > TOLERANCE:
                failures.append(
                    f"{rid}: L/100 seed={old100:.2f} eea={exp:.2f} drift={drift:.1%} (n={ref.get('n')})"
                )
        elif "eea_kwh100" in ref:
            old = row.get("energyConsumptionKWhPerKm")
            if not isinstance(old, (int, float)) or old <= 0:
                failures.append(f"{rid}: missing energyConsumptionKWhPerKm")
                continue
            old100 = float(old) * 100
            exp = float(ref["eea_kwh100"])
            drift = abs(old100 - exp) / max(exp, 1e-9)
            checked += 1
            if drift > TOLERANCE:
                failures.append(
                    f"{rid}: kWh/100 seed={old100:.2f} eea={exp:.2f} drift={drift:.1%}"
                )

    # Spot-check live volume-first resolve for a few known audit IDs.
    ice = truth.load_ice_maps()
    hev = truth.load_hev_maps()
    for rid in (
        "mercedes-benz-gle-2024",
        "bmw-x5-2024",
        "jeep-grand-cherokee-2022",
        "chevrolet-corvette-2025",
    ):
        row = rows.get(rid)
        if not row or (row.get("powertrain") or "").lower() not in ("ice", "hev"):
            continue
        locked = truth.seed_fuel_locked(row)
        hit = truth.resolve_eea_hit(row, ice, hev, prefer_seed_fuel=True, volume_first=False)
        if not hit and locked is None:
            hit = truth.resolve_eea_hit(row, ice, hev, volume_first=True)
        if not hit:
            continue
        _, ft, cell, _ = hit
        fk = locked or truth.ft_to_fuel_kind(ft)
        fc = eea.co2_to_fuel_per_100km(cell.get("co2"), fk if fk in ("petrol", "diesel", "lpg", "cng") else "petrol")
        if fc is None:
            continue
        old100 = float(row.get("fuelConsumptionLPerKm") or 0) * 100
        if old100 <= 0:
            continue
        drift = abs(old100 - fc) / fc
        checked += 1
        if drift > TOLERANCE:
            failures.append(f"{rid} live-check: L/100 seed={old100:.2f} eea={fc:.2f} drift={drift:.1%}")

    if failures:
        print(f"EEA drift FAIL ({len(failures)} / checked≈{checked}):", file=sys.stderr)
        for line in failures[:40]:
            print(" ", line, file=sys.stderr)
        if len(failures) > 40:
            print(f"  … +{len(failures) - 40} more", file=sys.stderr)
        return 1
    print(f"EEA drift OK — checked {checked} ref rows (tolerance ±{int(TOLERANCE * 100)}%)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
