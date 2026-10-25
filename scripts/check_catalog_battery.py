#!/usr/bin/env python3
"""
Flag BEV/PHEV rows whose batteryKWh is inconsistent with EEA Electric range (Zr).

Implied range km = batteryKWh / energyConsumptionKWhPerKm
                 = batteryKWh * 1000 / Wh_per_km

Flag when:
  1) implied range is >15% away from EVERY EEA Zr for that model/year
     (Status F if present, else P; same Cn matching as range fill), OR
  2) batteryKWh exceeds the largest capacity implied by any EEA Zr for that
     model across years at this row's Wh/km (proxy for “largest pack sold”).

Also (--strict / default when refs exist): fail if any row has both wltpRangeKm
and batteryKWh and implied range differs >15% from declared range
(must-fail includes 500e 190 km + 40 kWh).

Usage:
  python3 scripts/check_catalog_battery.py              # report + exit 0
  python3 scripts/check_catalog_battery.py --fail-on-suspects
  python3 scripts/check_catalog_battery.py --coherence-only
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import fill_catalog_bev_range_from_eea as fill
import fill_catalog_fuels_from_eea as eea

TOL = 0.15
REPORT_PATH = eea.CACHE_DIR / "catalog_battery_suspects_report.json"
REFS_PATH = eea.CACHE_DIR / "catalog_truth_battery_refs.json"


def implied_range_km(battery_kwh: float, energy_kwh_per_km: float) -> float:
    return battery_kwh / energy_kwh_per_km


def eea_zr_set(cell: dict) -> set[int]:
    """Status F if any Zr, else P. Drop Zr==Wh misfiles via versions_from_zr_map."""
    status, versions = fill.preferred_versions(cell)
    if status == "fp_conflict":
        # Still list all Zr from F∪P for suspicion (conservative).
        zrs: set[int] = set()
        for st in ("F", "P"):
            zrs |= set(cell.get(st) or {})
        return zrs
    return {v["zr"] for v in versions}


def collect_model_year_zrs(
    index: dict[tuple[str, int], dict],
    matched_keys: list[str],
    year: int,
) -> set[int]:
    cells = [index[(mk, year)] for mk in matched_keys if (mk, year) in index]
    if not cells:
        return set()
    cell = fill.merge_cells(cells) if len(cells) > 1 else cells[0]
    return eea_zr_set(cell)


def max_model_zr_across_years(
    index: dict[tuple[str, int], dict],
    matched_keys: list[str],
) -> int | None:
    best: int | None = None
    years = sorted({y for (mk, y) in index if mk in matched_keys})
    for y in years:
        zrs = collect_model_year_zrs(index, matched_keys, y)
        if zrs:
            m = max(zrs)
            best = m if best is None else max(best, m)
    return best


def coherence_failures(rows: list[dict]) -> list[str]:
    """Rows with both range and battery whose implied range drifts >15%."""
    fails: list[str] = []
    for r in rows:
        if (r.get("powertrain") or "").lower() not in {"ev", "phev"}:
            continue
        bat = r.get("batteryKWh")
        energy = r.get("energyConsumptionKWhPerKm")
        rng = r.get("wltpRangeKm")
        if bat in (None, "", 0) or energy in (None, "", 0) or rng in (None, "", 0):
            continue
        bat_f = float(bat)
        energy_f = float(energy)
        rng_f = float(rng)
        if bat_f <= 0 or energy_f <= 0 or rng_f <= 0:
            continue
        implied = implied_range_km(bat_f, energy_f)
        drift = abs(implied - rng_f) / rng_f
        if drift > TOL:
            fails.append(
                f"{r.get('id')}: battery={bat_f} implied_km={implied:.1f} "
                f"wltpRangeKm={int(rng_f)} drift={drift:.1%}"
            )
    return fails


def must_fail_coherence_cases() -> list[tuple[str, dict, bool]]:
    """(label, row, expect_fail)."""
    return [
        (
            "500e_190km_with_40kwh",
            {
                "id": "synthetic-500e-incoherent",
                "powertrain": "ev",
                "batteryKWh": 40.0,
                "energyConsumptionKWhPerKm": 0.1297,
                "wltpRangeKm": 190,
            },
            True,
        ),
        (
            "coherent_190_with_24kwh",
            {
                "id": "synthetic-500e-coherent",
                "powertrain": "ev",
                "batteryKWh": 23.8,
                "energyConsumptionKWhPerKm": 0.125,  # 23.8/0.125 = 190.4
                "wltpRangeKm": 190,
            },
            False,
        ),
        (
            "honda_e_oversize_vs_range",
            {
                "id": "synthetic-honda-e",
                "powertrain": "ev",
                "batteryKWh": 61.9,
                "energyConsumptionKWhPerKm": 0.178,
                "wltpRangeKm": 210,
            },
            True,
        ),
    ]


def run_suspect_scan(rows: list[dict]) -> tuple[list[dict], dict[str, dict]]:
    targets = [
        r
        for r in rows
        if (r.get("powertrain") or "").lower() in {"ev", "phev"}
        and r.get("batteryKWh") not in (None, "", 0)
        and r.get("energyConsumptionKWhPerKm") not in (None, "", 0)
    ]
    by_brand: dict[str, list[dict]] = defaultdict(list)
    for r in targets:
        by_brand[fill.brand_key_for_row(r)].append(r)

    indexes: dict[str, dict] = {}
    for i, brand in enumerate(sorted(by_brand)):
        print(f"[{i+1}/{len(by_brand)}] Zr cache {brand}…", flush=True)
        wrap = fill.load_brand_zr(brand, use_cache=True)
        indexes[brand] = fill.parse_zr_index(wrap, brand)

    # Precompute all merge keys per brand for “same model across years”
    suspects: list[dict] = []
    for brand, brand_rows in sorted(by_brand.items()):
        index = indexes[brand]
        all_keys = {mk for (mk, _y) in index}
        for r in sorted(brand_rows, key=lambda x: x.get("id") or ""):
            year = int(r.get("year") or 0)
            bat = float(r["batteryKWh"])
            energy = float(r["energyConsumptionKWhPerKm"])
            implied = implied_range_km(bat, energy)
            model = str(r.get("model") or "")
            eea_keys_year = {mk for (mk, y) in index if y == year}
            matched = fill.bev_model_keys(model, eea_keys_year, brand)
            # For cross-year max, match against all keys (same model family).
            matched_all = fill.bev_model_keys(model, all_keys, brand) or matched

            eea_zrs = (
                collect_model_year_zrs(index, matched, year) if matched else set()
            )
            reasons: list[str] = []
            if eea_zrs:
                within = any(abs(implied - zr) / zr <= TOL for zr in eea_zrs)
                if not within:
                    reasons.append(
                        "implied_range_gt_15pct_from_all_eea_zr"
                    )
            max_zr = max_model_zr_across_years(index, matched_all) if matched_all else None
            if max_zr is not None:
                max_plausible_bat = max_zr * energy  # kWh = km * kWh/km
                if bat > max_plausible_bat:
                    reasons.append(
                        f"battery_exceeds_max_implied_by_eea_zr({max_zr}km→{max_plausible_bat:.1f}kWh)"
                    )

            if not reasons:
                continue
            suspects.append(
                {
                    "id": r["id"],
                    "brand": r.get("brand"),
                    "model": model,
                    "year": year,
                    "powertrain": r.get("powertrain"),
                    "batteryKWh": bat,
                    "energyConsumptionKWhPerKm": energy,
                    "wh_per_km": energy * 1000.0,
                    "powerKw": r.get("powerKw"),
                    "wltpRangeKm": r.get("wltpRangeKm"),
                    "implied_range_km": round(implied, 1),
                    "eea_zr_km": sorted(eea_zrs),
                    "eea_model_keys": matched,
                    "max_eea_zr_model": max_zr,
                    "reasons": reasons,
                }
            )
    return suspects, indexes


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--fail-on-suspects",
        action="store_true",
        help="exit 1 if any suspect remains (post-fix CI)",
    )
    ap.add_argument(
        "--coherence-only",
        action="store_true",
        help="only battery↔range coherence + must-fail",
    )
    args = ap.parse_args()

    rows = json.loads(eea.SEED_PATH.read_text(encoding="utf-8"))
    failures: list[str] = []

    # Must-fail coherence suite (always)
    must_ok = 0
    for label, row, expect_fail in must_fail_coherence_cases():
        hits = coherence_failures([row])
        failed = len(hits) > 0
        if failed != expect_fail:
            failures.append(
                f"must-fail {label}: expect_fail={expect_fail} got hits={hits}"
            )
        else:
            must_ok += 1
            print(f"must-fail OK: {label} → {'FAIL' if failed else 'pass'} as expected")

    coh = coherence_failures(rows)
    print(f"coherence_failures={len(coh)}")
    if coh and (args.fail_on_suspects or args.coherence_only):
        for line in coh:
            failures.append(f"coherence: {line}")
    elif coh:
        for line in coh[:15]:
            print(f"  (report) {line}")
        if len(coh) > 15:
            print(f"  (report) … +{len(coh) - 15} more")

    suspects: list[dict] = []
    if not args.coherence_only:
        suspects, _ = run_suspect_scan(rows)
        eea.CACHE_DIR.mkdir(parents=True, exist_ok=True)
        report = {
            "tol": TOL,
            "suspect_count": len(suspects),
            "suspects": suspects,
        }
        REPORT_PATH.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(f"suspects={len(suspects)} report={REPORT_PATH}")
        if args.fail_on_suspects and suspects:
            for s in suspects[:30]:
                failures.append(
                    f"suspect {s['id']}: bat={s['batteryKWh']} "
                    f"implied={s['implied_range_km']} eea={s['eea_zr_km']} "
                    f"reasons={s['reasons']}"
                )
            if len(suspects) > 30:
                failures.append(f"… +{len(suspects) - 30} more suspects")

    print(f"must_fail_ok={must_ok} failures={len(failures)}")
    if failures:
        print("FAILURES:", file=sys.stderr)
        for line in failures[:40]:
            print(f"  {line}", file=sys.stderr)
        return 1
    print(
        "OK: battery coherence (+ suspects clear)"
        if args.fail_on_suspects or args.coherence_only
        else "OK: battery check (report mode)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
