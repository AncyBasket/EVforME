#!/usr/bin/env python3
"""
Battery verification for BEV/PHEV catalog rows.

A battery is VERIFIED only if:
  A) EEA has Zr for that model/year and implied range
     (battery / energyConsumptionKWhPerKm) is within 15% of at least one Zr, OR
  B) an official OEM ref exists for the SAME year + matching kW (±5).

Otherwise the battery is a suspect → must be nil.

Also flag:
  - implied range >15% from all EEA Zr (when EEA exists)
  - battery exceeds max capacity implied by any EEA Zr for the model
  - synthetic patterns: ≥3 different models in the same year share the same
    implied km (±1), or a model-year series grows by a fixed step

Coherence: battery↔wltpRangeKm drift >15% fails.

Usage:
  python3 scripts/check_catalog_battery.py
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


def round_implied_km(battery_kwh: float, energy_kwh_per_km: float) -> int:
    return int(round(implied_range_km(battery_kwh, energy_kwh_per_km)))


def eea_zr_set(cell: dict) -> set[int]:
    status, versions = fill.preferred_versions(cell)
    if status == "fp_conflict":
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


def oem_verified_ids(refs_path: Path = REFS_PATH) -> set[str]:
    """IDs with an official OEM correction recorded for this seed."""
    if not refs_path.is_file():
        return set()
    refs = json.loads(refs_path.read_text(encoding="utf-8"))
    out: set[str] = set()
    for c in refs.get("corrected") or []:
        if c.get("id") and c.get("capacity_kind") in {"net", "gross"}:
            out.add(c["id"])
    return out


def coherence_failures(rows: list[dict]) -> list[str]:
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


def find_synthetic_pattern_ids(rows: list[dict]) -> dict[str, str]:
    """
    Return id → reason for batteries that look generated:
    - ≥3 distinct (brand, model) share the same implied km (±0 after round) in one year
    - same model has ≥3 consecutive year-steps with identical non-zero Δ implied km
    """
    flagged: dict[str, str] = {}

    by_year: dict[int, list[tuple[int, str, str, str]]] = defaultdict(list)
    by_model: dict[tuple[str, str], list[tuple[int, int, str]]] = defaultdict(list)

    for r in rows:
        if (r.get("powertrain") or "").lower() not in {"ev", "phev"}:
            continue
        bat = r.get("batteryKWh")
        energy = r.get("energyConsumptionKWhPerKm")
        if bat in (None, "", 0) or energy in (None, "", 0):
            continue
        year = int(r.get("year") or 0)
        brand = str(r.get("brand") or "")
        model = str(r.get("model") or "")
        rid = str(r.get("id") or "")
        imp = round_implied_km(float(bat), float(energy))
        by_year[year].append((imp, brand, model, rid))
        by_model[(brand, model)].append((year, imp, rid))

    for year, items in by_year.items():
        buckets: dict[int, set[tuple[str, str]]] = defaultdict(set)
        bucket_ids: dict[int, list[str]] = defaultdict(list)
        for imp, brand, model, rid in items:
            buckets[imp].add((brand, model))
            bucket_ids[imp].append(rid)
        for imp, models in buckets.items():
            if len(models) >= 3:
                reason = (
                    f"synthetic_same_implied_km={imp}_across_{len(models)}_models_in_{year}"
                )
                for rid in bucket_ids[imp]:
                    flagged[rid] = reason

    for (_brand, _model), vals in by_model.items():
        vals = sorted(set(vals))  # unique year entries
        vals = sorted(vals, key=lambda x: x[0])
        if len(vals) < 3:
            continue
        # Look for runs of consecutive years with constant step
        for i in range(len(vals) - 2):
            y0, imp0, id0 = vals[i]
            y1, imp1, id1 = vals[i + 1]
            y2, imp2, id2 = vals[i + 2]
            if y1 - y0 != 1 or y2 - y1 != 1:
                continue
            step = imp1 - imp0
            if step == 0:
                continue
            if imp2 - imp1 == step:
                reason = f"synthetic_fixed_step_{step}_km_per_year"
                for rid in (id0, id1, id2):
                    flagged[rid] = reason
                # extend the run forward
                j = i + 3
                prev_y, prev_imp = y2, imp2
                while j < len(vals):
                    y, imp, rid = vals[j]
                    if y - prev_y == 1 and imp - prev_imp == step:
                        flagged[rid] = reason
                        prev_y, prev_imp = y, imp
                        j += 1
                    else:
                        break

    return flagged


def must_fail_coherence_cases() -> list[tuple[str, dict, bool]]:
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
                "energyConsumptionKWhPerKm": 0.125,
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


def must_fail_synthetic_cases() -> list[tuple[str, list[dict], bool, str]]:
    """
    (label, rows, expect_flagged, reason_substr).
    expect_flagged True → find_synthetic_pattern_ids must mark those ids.
    """
    # Same implied km across ≥3 models in 2021 (446 km pattern)
    rows_same = [
        {
            "id": "synthetic-a-2021",
            "brand": "BrandA",
            "model": "ModelA",
            "year": 2021,
            "powertrain": "ev",
            "batteryKWh": 44.6,
            "energyConsumptionKWhPerKm": 0.1,  # → 446
        },
        {
            "id": "synthetic-b-2021",
            "brand": "BrandB",
            "model": "ModelB",
            "year": 2021,
            "powertrain": "ev",
            "batteryKWh": 44.6,
            "energyConsumptionKWhPerKm": 0.1,
        },
        {
            "id": "synthetic-c-2021",
            "brand": "BrandC",
            "model": "ModelC",
            "year": 2021,
            "powertrain": "ev",
            "batteryKWh": 44.6,
            "energyConsumptionKWhPerKm": 0.1,
        },
    ]
    # Fixed step 6 km/year: 2021=446, 2022=452, … and 2025=490, 2026=496
    rows_step = []
    for year, imp in (
        (2021, 446),
        (2022, 452),
        (2023, 458),
        (2024, 484),
        (2025, 490),
        (2026, 496),
    ):
        # bat = imp * 0.1
        rows_step.append(
            {
                "id": f"synthetic-step-{year}",
                "brand": "SynthCo",
                "model": "Stepper",
                "year": year,
                "powertrain": "ev",
                "batteryKWh": round(imp * 0.1, 1),
                "energyConsumptionKWhPerKm": 0.1,
            }
        )
    return [
        (
            "same_implied_across_3_models_2021",
            rows_same,
            True,
            "synthetic_same_implied",
        ),
        (
            "fixed_step_series_446_to_496",
            rows_step,
            True,
            "synthetic_fixed_step",
        ),
    ]


def run_suspect_scan(
    rows: list[dict],
    *,
    oem_ok: set[str] | None = None,
) -> tuple[list[dict], dict[str, dict]]:
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

    if oem_ok is None:
        oem_ok = oem_verified_ids()
    synthetic = find_synthetic_pattern_ids(rows)

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
            rid = str(r.get("id") or "")
            eea_keys_year = {mk for (mk, y) in index if y == year}
            matched = fill.bev_model_keys(model, eea_keys_year, brand)
            matched_all = fill.bev_model_keys(model, all_keys, brand) or matched

            eea_zrs = (
                collect_model_year_zrs(index, matched, year) if matched else set()
            )
            reasons: list[str] = []

            # No EEA Zr for this model/year → unverified (unless OEM ref).
            if not eea_zrs:
                if rid not in oem_ok:
                    reasons.append("no_eea_zr_unverified")
            else:
                within = any(abs(implied - zr) / zr <= TOL for zr in eea_zrs)
                if not within:
                    if rid not in oem_ok:
                        reasons.append("implied_range_gt_15pct_from_all_eea_zr")

            max_zr = (
                max_model_zr_across_years(index, matched_all) if matched_all else None
            )
            if max_zr is not None:
                max_plausible_bat = max_zr * energy
                if bat > max_plausible_bat and rid not in oem_ok:
                    reasons.append(
                        f"battery_exceeds_max_implied_by_eea_zr({max_zr}km→{max_plausible_bat:.1f}kWh)"
                    )

            if rid in synthetic and rid not in oem_ok:
                reasons.append(synthetic[rid])

            if not reasons:
                continue
            suspects.append(
                {
                    "id": rid,
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
                    "oem_ref": rid in oem_ok,
                }
            )
    return suspects, indexes


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fail-on-suspects", action="store_true")
    ap.add_argument("--coherence-only", action="store_true")
    args = ap.parse_args()

    rows = json.loads(eea.SEED_PATH.read_text(encoding="utf-8"))
    failures: list[str] = []
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

    for label, synth_rows, expect_flagged, substr in must_fail_synthetic_cases():
        flagged = find_synthetic_pattern_ids(synth_rows)
        hit = any(substr in reason for reason in flagged.values())
        ids_hit = [i for i, reason in flagged.items() if substr in reason]
        if expect_flagged and not hit:
            failures.append(
                f"must-fail {label}: expected synthetic flag containing {substr!r}, "
                f"got {flagged}"
            )
        elif not expect_flagged and hit:
            failures.append(f"must-fail {label}: unexpected flag {flagged}")
        else:
            must_ok += 1
            print(f"must-fail OK: {label} → flagged {sorted(ids_hit)[:6]}…")

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
        REPORT_PATH.write_text(
            json.dumps(
                {"tol": TOL, "suspect_count": len(suspects), "suspects": suspects},
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
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
