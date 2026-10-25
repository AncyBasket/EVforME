#!/usr/bin/env python3
"""
Battery verification for BEV/PHEV catalog rows.

A battery may remain ONLY if catalog_truth_battery_refs.json has an official
manufacturer URL for that id with:
  - capacity_kind in {net, gross}
  - source_year equal to the catalog row year
  - catalog powerKw present and matching the ref powerKw (±5 kW)
  - batteryKWh matching the ref value

EEA ±15% alone is NOT sufficient. No kW on the row → must be nil.

Also flag synthetic packs:
  - ≥3 distinct models in the same year share implied km within ±1
  - same model has ≥3 consecutive years with constant implied-km step
    (including step ≈ 0: battery changes, derived range stays flat)

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

import fill_catalog_fuels_from_eea as eea

TOL = 0.15
KW_TOL = 5.0
IMPLIED_TOL_KM = 1.0
REPORT_PATH = eea.CACHE_DIR / "catalog_battery_suspects_report.json"
REFS_PATH = eea.CACHE_DIR / "catalog_truth_battery_refs.json"


def implied_range_km(battery_kwh: float, energy_kwh_per_km: float) -> float:
    return battery_kwh / energy_kwh_per_km


def load_oem_corrections(refs_path: Path = REFS_PATH) -> dict[str, dict]:
    if not refs_path.is_file():
        return {}
    refs = json.loads(refs_path.read_text(encoding="utf-8"))
    out: dict[str, dict] = {}
    for c in refs.get("corrected") or []:
        rid = c.get("id")
        if not rid:
            continue
        out[str(rid)] = c
    return out


def oem_ref_valid_for_row(row: dict, ref: dict) -> tuple[bool, str]:
    """Official OEM URL + same source_year as row + matching kW + matching kWh."""
    url = (ref.get("url") or "").strip()
    if not url.startswith("http"):
        return False, "missing_or_invalid_official_url"
    kind = ref.get("capacity_kind")
    if kind not in {"net", "gross"}:
        return False, f"capacity_kind_not_net_or_gross({kind!r})"
    row_year = int(row.get("year") or 0)
    source_year = ref.get("source_year")
    if source_year is None:
        return False, "missing_source_year"
    if int(source_year) != row_year:
        return False, f"source_year_{source_year}_!=_row_year_{row_year}"
    pkw = row.get("powerKw")
    if pkw in (None, "", 0):
        return False, "row_missing_powerKw"
    ref_kw = ref.get("powerKw")
    if ref_kw in (None, "", 0):
        return False, "ref_missing_powerKw"
    if abs(float(pkw) - float(ref_kw)) > KW_TOL:
        return False, f"powerKw_mismatch_row={pkw}_ref={ref_kw}"
    bat = row.get("batteryKWh")
    ref_bat = ref.get("batteryKWh")
    if bat in (None, "", 0) or ref_bat in (None, "", 0):
        return False, "missing_batteryKWh"
    if abs(float(bat) - float(ref_bat)) > 0.05:
        return False, f"batteryKWh_mismatch_row={bat}_ref={ref_bat}"
    return True, "ok"


def oem_verified_ids(refs_path: Path = REFS_PATH, rows: list[dict] | None = None) -> set[str]:
    """IDs whose battery is backed by a valid same-year OEM ref."""
    corrections = load_oem_corrections(refs_path)
    if not corrections:
        return set()
    by_id = {r["id"]: r for r in (rows or [])} if rows is not None else None
    if by_id is None:
        seed_rows = json.loads(eea.SEED_PATH.read_text(encoding="utf-8"))
        by_id = {r["id"]: r for r in seed_rows}
    out: set[str] = set()
    for rid, ref in corrections.items():
        row = by_id.get(rid)
        if not row:
            continue
        ok, _ = oem_ref_valid_for_row(row, ref)
        if ok:
            out.add(rid)
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


def _cluster_by_tolerance(
    values: list[tuple[float, object]],
    tol: float,
) -> list[list[tuple[float, object]]]:
    """Union-find clusters where |a-b| <= tol."""
    n = len(values)
    parent = list(range(n))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i: int, j: int) -> None:
        ri, rj = find(i), find(j)
        if ri != rj:
            parent[rj] = ri

    for i in range(n):
        for j in range(i + 1, n):
            if abs(values[i][0] - values[j][0]) <= tol:
                union(i, j)
    groups: dict[int, list[tuple[float, object]]] = defaultdict(list)
    for i, item in enumerate(values):
        groups[find(i)].append(item)
    return list(groups.values())


def find_synthetic_pattern_ids(rows: list[dict]) -> dict[str, str]:
    """
    Return id → reason for batteries that look generated:
    - ≥3 distinct (brand, model) share implied km within ±1 in one year
    - same model has ≥3 consecutive years with constant Δ implied km
      (including Δ ≈ 0 within ±1 km — flat derived range)
    """
    flagged: dict[str, str] = {}

    by_year: dict[int, list[tuple[float, str, str, str]]] = defaultdict(list)
    by_model: dict[tuple[str, str], list[tuple[int, float, str]]] = defaultdict(list)

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
        imp = implied_range_km(float(bat), float(energy))
        by_year[year].append((imp, brand, model, rid))
        by_model[(brand, model)].append((year, imp, rid))

    for year, items in by_year.items():
        clusters = _cluster_by_tolerance(
            [(imp, (brand, model, rid)) for imp, brand, model, rid in items],
            IMPLIED_TOL_KM,
        )
        for cluster in clusters:
            models = {(brand, model) for _imp, (brand, model, _rid) in cluster}
            if len(models) < 3:
                continue
            imps = [imp for imp, _ in cluster]
            center = sum(imps) / len(imps)
            reason = (
                f"synthetic_same_implied_km≈{center:.0f}"
                f"_across_{len(models)}_models_in_{year}"
            )
            for _imp, (_b, _m, rid) in cluster:
                flagged[rid] = reason

    for (_brand, _model), vals in by_model.items():
        # one entry per year (keep first id if duplicates)
        by_y: dict[int, tuple[float, str]] = {}
        for year, imp, rid in sorted(vals, key=lambda x: x[0]):
            by_y.setdefault(year, (imp, rid))
        years_sorted = sorted(by_y)
        if len(years_sorted) < 3:
            continue
        for i in range(len(years_sorted) - 2):
            y0, y1, y2 = years_sorted[i], years_sorted[i + 1], years_sorted[i + 2]
            if y1 - y0 != 1 or y2 - y1 != 1:
                continue
            imp0, id0 = by_y[y0]
            imp1, id1 = by_y[y1]
            imp2, id2 = by_y[y2]
            step01 = imp1 - imp0
            step12 = imp2 - imp1
            if abs(step01 - step12) > IMPLIED_TOL_KM:
                continue
            # Constant step including ~0 (flat derived autonomy)
            step = (step01 + step12) / 2.0
            step_label = 0 if abs(step) <= IMPLIED_TOL_KM else int(round(step))
            reason = f"synthetic_fixed_step_{step_label}_km_per_year"
            run_ids = [id0, id1, id2]
            prev_y, prev_imp = y2, imp2
            j = i + 3
            while j < len(years_sorted):
                y = years_sorted[j]
                imp, rid = by_y[y]
                if y - prev_y != 1:
                    break
                if abs((imp - prev_imp) - step) > IMPLIED_TOL_KM:
                    break
                run_ids.append(rid)
                prev_y, prev_imp = y, imp
                j += 1
            for rid in run_ids:
                flagged[rid] = reason

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
    """
    rows_same = [
        {
            "id": "synthetic-a-2021",
            "brand": "BrandA",
            "model": "ModelA",
            "year": 2021,
            "powertrain": "ev",
            "batteryKWh": 44.6,
            "energyConsumptionKWhPerKm": 0.1,
        },
        {
            "id": "synthetic-b-2021",
            "brand": "BrandB",
            "model": "ModelB",
            "year": 2021,
            "powertrain": "ev",
            "batteryKWh": 44.7,
            "energyConsumptionKWhPerKm": 0.1,  # 447 — within ±1 of 446
        },
        {
            "id": "synthetic-c-2021",
            "brand": "BrandC",
            "model": "ModelC",
            "year": 2021,
            "powertrain": "ev",
            "batteryKWh": 44.55,
            "energyConsumptionKWhPerKm": 0.1,
        },
    ]
    rows_step = []
    for year, imp in (
        (2021, 446),
        (2022, 452),
        (2023, 458),
        (2024, 484),
        (2025, 490),
        (2026, 496),
    ):
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
    # Constant ~350 km derived range (EQV-style): battery and consumption both drift
    rows_flat = []
    for year, bat, energy in (
        (2020, 98.8, 0.2823),
        (2021, 98.1, 0.2803),
        (2022, 98.5, 0.2814),
        (2023, 101.1, 0.289),
        (2024, 99.3, 0.2838),
    ):
        rows_flat.append(
            {
                "id": f"synthetic-eqv-{year}",
                "brand": "SynthMB",
                "model": "EQVFlat",
                "year": year,
                "powertrain": "ev",
                "batteryKWh": bat,
                "energyConsumptionKWhPerKm": energy,
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
        (
            "constant_implied_350_eqv_style",
            rows_flat,
            True,
            "synthetic_fixed_step_0",
        ),
    ]


def must_fail_oem_gate_cases() -> list[tuple[str, dict, dict, bool]]:
    """
    (label, row, ref, expect_valid).
    Official URL gate: same source_year + matching kW required.
    """
    base_row = {
        "id": "synthetic-oem-car-2023",
        "year": 2023,
        "powertrain": "ev",
        "powerKw": 150.0,
        "batteryKWh": 60.4,
    }
    good_ref = {
        "id": "synthetic-oem-car-2023",
        "url": "https://example.oem/press/2023",
        "capacity_kind": "gross",
        "source_year": 2023,
        "powerKw": 150.0,
        "batteryKWh": 60.4,
    }
    return [
        ("oem_ok_same_year_kw", base_row, good_ref, True),
        (
            "oem_fail_wrong_source_year",
            base_row,
            {**good_ref, "source_year": 2022},
            False,
        ),
        (
            "oem_fail_missing_row_kw",
            {**base_row, "powerKw": None},
            good_ref,
            False,
        ),
        (
            "oem_fail_kw_mismatch",
            {**base_row, "powerKw": 200.0},
            good_ref,
            False,
        ),
        (
            "oem_fail_no_url",
            base_row,
            {**good_ref, "url": "IT-listino"},
            False,
        ),
    ]


def run_suspect_scan(
    rows: list[dict],
    *,
    oem_ok: set[str] | None = None,
) -> tuple[list[dict], dict[str, dict]]:
    """
    Any non-nil battery without a valid same-year OEM URL ref is a suspect.
    Synthetic patterns are attached as extra reasons (still require OEM to keep).
    """
    targets = [
        r
        for r in rows
        if (r.get("powertrain") or "").lower() in {"ev", "phev"}
        and r.get("batteryKWh") not in (None, "", 0)
    ]
    if oem_ok is None:
        oem_ok = oem_verified_ids(rows=rows)
    corrections = load_oem_corrections()
    synthetic = find_synthetic_pattern_ids(rows)

    suspects: list[dict] = []
    for r in sorted(targets, key=lambda x: x.get("id") or ""):
        rid = str(r.get("id") or "")
        year = int(r.get("year") or 0)
        bat = float(r["batteryKWh"])
        energy = r.get("energyConsumptionKWhPerKm")
        implied = (
            implied_range_km(bat, float(energy))
            if energy not in (None, "", 0)
            else None
        )
        reasons: list[str] = []

        if rid not in oem_ok:
            ref = corrections.get(rid)
            if not ref:
                reasons.append("missing_official_oem_url_ref")
            else:
                ok, detail = oem_ref_valid_for_row(r, ref)
                if not ok:
                    reasons.append(f"oem_ref_invalid:{detail}")
                else:
                    # Should have been in oem_ok — treat as missing
                    reasons.append("oem_ref_not_accepted")

        if r.get("powerKw") in (None, "", 0) and rid not in oem_ok:
            if "row_missing_powerKw" not in " ".join(reasons):
                reasons.append("row_missing_powerKw")

        if rid in synthetic and rid not in oem_ok:
            reasons.append(synthetic[rid])

        if not reasons:
            continue
        suspects.append(
            {
                "id": rid,
                "brand": r.get("brand"),
                "model": r.get("model"),
                "year": year,
                "powertrain": r.get("powertrain"),
                "batteryKWh": bat,
                "energyConsumptionKWhPerKm": energy,
                "powerKw": r.get("powerKw"),
                "wltpRangeKm": r.get("wltpRangeKm"),
                "implied_range_km": round(implied, 1) if implied is not None else None,
                "reasons": reasons,
                "oem_ref": rid in oem_ok,
            }
        )
    return suspects, {}


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

    for label, row, ref, expect_valid in must_fail_oem_gate_cases():
        ok, detail = oem_ref_valid_for_row(row, ref)
        if ok != expect_valid:
            failures.append(
                f"must-fail {label}: expect_valid={expect_valid} got ok={ok} ({detail})"
            )
        else:
            must_ok += 1
            print(f"must-fail OK: {label} → valid={ok} ({detail})")

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
                    f"implied={s['implied_range_km']} reasons={s['reasons']}"
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
