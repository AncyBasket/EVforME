#!/usr/bin/env python3
"""
PR #6 follow-up: Born/Ariya EV, Ioniq HEV split, drop Matrix, kill +6km range interpolations.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PATH = REPO / "EVforME?" / "Data" / "vehicles.seed.quality.json"

# Known EV name fragments that must never be ICE.
KNOWN_EV_NEEDLES = [
    ("tesla", None),
    ("polestar", None),
    ("cupra", "born"),
    ("volkswagen", "id."),
    ("vw", "id."),
    ("nissan", "ariya"),
    ("peugeot", "e-208"),
    ("peugeot", "e208"),
    ("citroen", "ë-c3"),
    ("citroën", "ë-c3"),
    ("citroen", "e-c3"),
    ("citroën", "e-c3"),
    ("mg", "mg4"),
    ("mg", "mg 4"),
    ("byd", "dolphin"),
    ("leapmotor", None),
    ("renault", "zoe"),
    ("renault", "5 e-tech"),
    ("fiat", "500e"),
    ("fiat", "600e"),
]

# Models with impossible EU marketing years to drop entirely.
DROP_IDS_PREFIX = [
    "toyota-corolla-matrix-",  # US-only Matrix ended ~2014; 2022–26 rows are fake
]

# Additional drops: body-style inventati su Ariya (resta solo la serie crossover EV).
# User asked all Ariya variants → EV; we convert hatchback/mpv rather than drop.


def is_known_ev_name(brand: str, model: str) -> bool:
    b = brand.lower()
    m = model.lower()
    for brand_n, model_n in KNOWN_EV_NEEDLES:
        if brand_n in b and (model_n is None or model_n in m):
            return True
    return False


def constant_step_series(years_ranges: list[tuple[int, int]]) -> bool:
    """True if range grows by the same non-zero step every consecutive year."""
    if len(years_ranges) < 3:
        return False
    years_ranges = sorted(years_ranges)
    # Require consecutive years (or nearly) with constant delta on range.
    deltas = []
    for i in range(len(years_ranges) - 1):
        y0, r0 = years_ranges[i]
        y1, r1 = years_ranges[i + 1]
        if y1 - y0 != 1:
            return False
        deltas.append(r1 - r0)
    return len(set(deltas)) == 1 and deltas[0] != 0


def fix_row_born(row: dict) -> None:
    row["powertrain"] = "ev"
    row["fuelKind"] = None
    row["fuelConsumptionLPerKm"] = None
    # Cupra Born WLTP tipico ~15–17 kWh/100 (58–77 kWh pack).
    year = int(row["year"])
    k100 = 16.5 if year <= 2023 else 15.8
    row["wltpConsumptionKWh100km"] = k100
    row["energyConsumptionKWhPerKm"] = round(k100 / 100.0, 4)
    # Generation plateaus (not +6/year).
    if year <= 2023:
        row["wltpRangeKm"] = 420
    else:
        row["wltpRangeKm"] = 550  # larger pack / facelift band
    row["sourceName"] = (row.get("sourceName") or "") + ";PR6 Born EV fix"


def fix_row_ariya_ev(row: dict) -> None:
    row["powertrain"] = "ev"
    row["fuelKind"] = None
    row["fuelConsumptionLPerKm"] = None
    year = int(row["year"])
    # Ariya ~17–19 kWh/100; plateaus by early/late gen.
    if year <= 2023:
        k100 = 18.0
        rng = 460
    else:
        k100 = 17.5
        rng = 500
    row["wltpConsumptionKWh100km"] = k100
    row["energyConsumptionKWhPerKm"] = round(k100 / 100.0, 4)
    row["wltpRangeKm"] = rng
    # Normalize model label for fake body styles.
    model = str(row.get("model", ""))
    if "hatchback" in model.lower() or "mpv" in model.lower():
        row["model"] = "Ariya"
        row["trim"] = row.get("trim") or model
    row["sourceName"] = (row.get("sourceName") or "") + ";PR6 Ariya EV fix"


def fix_ioniq_hybrid(row: dict) -> None:
    """Plain 'Ioniq' ICE rows 2016–22 → HEV ~3.9 L/100."""
    row["powertrain"] = "hev"
    row["fuelKind"] = "petrol"
    row["fuelConsumptionLPerKm"] = 0.039
    row["energyConsumptionKWhPerKm"] = None
    row["wltpConsumptionKWh100km"] = None
    row["wltpRangeKm"] = None
    if not (row.get("trim") or "").strip():
        row["trim"] = "Hybrid"
    row["sourceName"] = (row.get("sourceName") or "") + ";PR6 Ioniq HEV"


def main() -> None:
    rows: list[dict] = json.loads(PATH.read_text(encoding="utf-8"))
    before = len(rows)
    kept: list[dict] = []
    stats = defaultdict(int)

    for row in rows:
        rid = str(row.get("id", ""))
        brand = str(row.get("brand", ""))
        model = str(row.get("model", ""))
        year = int(row.get("year") or 0)
        pt = str(row.get("powertrain", "")).lower()

        if any(rid.startswith(p) for p in DROP_IDS_PREFIX):
            stats["dropped_matrix"] += 1
            continue
        if year > 2026:
            stats["dropped_future"] += 1
            continue

        handled = False

        # Cupra Born
        if "cupra" in brand.lower() and "born" in model.lower():
            fix_row_born(row)
            stats["born_fixed"] += 1
            handled = True

        # All Ariya variants → EV with generation plateaus
        elif "nissan" in brand.lower() and "ariya" in model.lower():
            fix_row_ariya_ev(row)
            stats["ariya_fixed"] += 1
            handled = True

        # Hyundai Ioniq (base, not 5/6/Electric/PHEV) 2016–22 → HEV
        elif (
            brand.lower() == "hyundai"
            and model.strip().lower() == "ioniq"
            and 2016 <= year <= 2022
            and pt == "ice"
        ):
            fix_ioniq_hybrid(row)
            stats["ioniq_hev"] += 1
            handled = True

        # Ioniq Electric: ensure EV band ~12–14
        elif (
            brand.lower() == "hyundai"
            and "ioniq" in model.lower()
            and "electric" in model.lower()
        ):
            row["powertrain"] = "ev"
            row["fuelKind"] = None
            row["fuelConsumptionLPerKm"] = None
            k100 = float(row.get("wltpConsumptionKWh100km") or 0)
            if k100 <= 0 or k100 > 16:
                row["wltpConsumptionKWh100km"] = 13.5
                row["energyConsumptionKWhPerKm"] = 0.135
                stats["ioniq_ev_energy"] += 1
            # Same generation plateau (28 kWh ~280 km / 38 kWh ~310 km bands).
            if year <= 2019:
                row["wltpRangeKm"] = 280
            else:
                row["wltpRangeKm"] = 311
            handled = True

        # Known EV names wrongly ICE (skip if already handled above)
        elif pt == "ice" and is_known_ev_name(brand, model):
            row["powertrain"] = "ev"
            row["fuelKind"] = None
            row["fuelConsumptionLPerKm"] = None
            if not row.get("wltpConsumptionKWh100km") and not row.get("energyConsumptionKWhPerKm"):
                row["wltpConsumptionKWh100km"] = 17.0
                row["energyConsumptionKWhPerKm"] = 0.17
            row["wltpRangeKm"] = None
            stats["known_ev_from_ice"] += 1
            handled = True

        _ = handled
        kept.append(row)

    # Kill monotonic constant-step EV range interpolations → nil.
    by_key: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in kept:
        if str(row.get("powertrain", "")).lower() != "ev":
            continue
        if row.get("wltpRangeKm") is None:
            continue
        key = (str(row.get("brand", "")).lower(), str(row.get("model", "")).lower())
        by_key[key].append(row)

    for key, group in by_key.items():
        yrs = sorted(
            (int(r["year"]), int(r["wltpRangeKm"]))
            for r in group
            if r.get("wltpRangeKm") is not None
        )
        if constant_step_series(yrs):
            for r in group:
                r["wltpRangeKm"] = None
                stats["range_nulled_interpolated"] += 1

    PATH.write_text(json.dumps(kept, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{before} → {len(kept)}")
    for k, v in sorted(stats.items()):
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
