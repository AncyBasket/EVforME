#!/usr/bin/env python3
"""
Verify every filled BEV wltpRangeKm in catalog_truth_range_refs.json against
EEA IT Zr caches (same matching rules as fill_catalog_bev_range_from_eea.py).

Fails if:
- a fill's seed value ≠ ref value
- re-resolving from EEA does not yield the same unique Zr
- a must-fail fixture case unexpectedly passes

Exit 0 = OK, 1 = mismatch, 2 = missing inputs.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import fill_catalog_bev_range_from_eea as fill
import fill_catalog_fuels_from_eea as eea

REFS_PATH = fill.REFS_PATH
SEED_PATH = eea.SEED_PATH

# Synthetic must-fail cases: (description, mutate_fn returning (row, index, brand, expect_fail_reason_substr))
# These never write to disk; they only assert the resolver rejects bad situations.


def _must_fail_cases(indexes: dict[str, dict]) -> list[tuple[str, dict, dict, str, str]]:
    """Return (label, row, index, brand, reason_substr_expected)."""
    cases: list[tuple[str, dict, dict, str, str]] = []

    # 1) Year outside EEA window must not invent a number.
    cases.append(
        (
            "year_2026_outside_window",
            {
                "id": "synthetic-tesla-model-3-2026",
                "model": "Model 3",
                "year": 2026,
                "energyConsumptionKWhPerKm": 0.132,
                "powerKw": 208,
            },
            indexes.get("TESLA") or {},
            "TESLA",
            "outside EEA",
        )
    )

    # 2) Multi-Zr with no catalog Wh/kW → ambiguous (leave nil).
    tesla_idx = indexes.get("TESLA") or {}
    if ("MODEL3", 2024) in tesla_idx:
        cases.append(
            (
                "ambiguous_no_disambiguators",
                {
                    "id": "synthetic-model3-no-wh-kw",
                    "model": "Model 3",
                    "year": 2024,
                    "energyConsumptionKWhPerKm": None,
                    "powerKw": None,
                },
                tesla_idx,
                "TESLA",
                "ambiguous",
            )
        )

    # 3) Wh that matches multiple Zr bands still needs unique pin — use a Wh that
    # hits nothing and a kW that hits many → still ambiguous or skip, never a guess.
    if ("MODEL3", 2024) in tesla_idx:
        cases.append(
            (
                "wh_miss_kw_multi",
                {
                    "id": "synthetic-model3-bad-wh",
                    "model": "Model 3",
                    "year": 2024,
                    "energyConsumptionKWhPerKm": 0.999,  # no EEA Wh near 999
                    "powerKw": 208,  # several Zr share 208 kW
                },
                tesla_idx,
                "TESLA",
                "ambiguous",
            )
        )

    # 4) Wrong-year copy must not be accepted: 2023 Wh/kW against empty year index cell.
    empty_index: dict = {}
    cases.append(
        (
            "no_cn_for_year",
            {
                "id": "synthetic-missing-cn",
                "model": "Model 3",
                "year": 2020,
                "energyConsumptionKWhPerKm": 0.132,
                "powerKw": 208,
            },
            empty_index,
            "TESLA",
            "no EEA Cn match",
        )
    )

    return cases


def main() -> int:
    if not REFS_PATH.is_file():
        print(f"missing refs: {REFS_PATH}", file=sys.stderr)
        return 2
    if not SEED_PATH.is_file():
        print(f"missing seed: {SEED_PATH}", file=sys.stderr)
        return 2

    refs = json.loads(REFS_PATH.read_text(encoding="utf-8"))
    fills = refs.get("fills") or []
    if not fills:
        print("refs contain zero fills — nothing to verify", file=sys.stderr)
        return 2

    rows = {r["id"]: r for r in json.loads(SEED_PATH.read_text(encoding="utf-8"))}
    brands = sorted({str(f.get("eea_brand") or "") for f in fills if f.get("eea_brand")})
    if "TESLA" not in brands:
        brands.append("TESLA")
    indexes: dict[str, dict] = {}
    for brand in brands:
        wrap = fill.load_brand_zr(brand, use_cache=True)
        indexes[brand] = fill.parse_zr_index(wrap, brand)

    failures: list[str] = []
    checked = 0

    for ref in fills:
        rid = ref.get("id")
        exp = ref.get("wltpRangeKm")
        row = rows.get(rid)
        if not row:
            failures.append(f"{rid}: missing from seed")
            continue
        seed_val = row.get("wltpRangeKm")
        if seed_val != exp:
            failures.append(f"{rid}: seed wltpRangeKm={seed_val} ≠ ref={exp}")
            continue
        brand = str(ref.get("eea_brand") or fill.brand_key_for_row(row))
        decision = fill.resolve_zr_for_row(row, indexes.get(brand) or {}, brand)
        checked += 1
        if not decision or decision.get("result") != "fill":
            failures.append(
                f"{rid}: re-resolve did not fill (got {decision})"
            )
            continue
        got = decision.get("wltpRangeKm")
        if got != exp:
            failures.append(
                f"{rid}: re-resolve Zr={got} ≠ ref={exp} "
                f"(status={decision.get('status')} model={decision.get('eea_model')})"
            )
            continue
        if decision.get("status") != ref.get("status"):
            failures.append(
                f"{rid}: status re-resolve={decision.get('status')} ≠ ref={ref.get('status')}"
            )

    # Must-fail suite
    must_fail_ok = 0
    for label, row, index, brand, substr in _must_fail_cases(indexes):
        decision = fill.resolve_zr_for_row(row, index, brand)
        ok_fail = (
            decision is not None
            and decision.get("result") == "skip"
            and substr.lower() in str(decision.get("reason") or "").lower()
        )
        if not ok_fail:
            failures.append(
                f"must-fail {label}: expected skip containing {substr!r}, got {decision}"
            )
        else:
            must_fail_ok += 1
            print(f"must-fail OK: {label} → {decision.get('reason')}")

    print(f"checked_fills={checked} must_fail_ok={must_fail_ok} failures={len(failures)}")
    if failures:
        print("FAILURES:", file=sys.stderr)
        for line in failures[:50]:
            print(f"  {line}", file=sys.stderr)
        if len(failures) > 50:
            print(f"  … +{len(failures) - 50} more", file=sys.stderr)
        return 1
    print("OK: all range refs match EEA re-resolve; must-fail cases rejected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
