#!/usr/bin/env python3
"""
Verify BEV catalog variants against catalog_truth_ev_variants_refs.json.

Must-fail cases + seed/ref coherence. PYTHONHASHSEED-stable.

Usage:
  python3 scripts/check_ev_variants.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import build_ev_variants_from_eea as build
import fill_catalog_fuels_from_eea as eea

REFS = eea.CACHE_DIR / "catalog_truth_ev_variants_refs.json"
SEED = eea.SEED_PATH


def must_fail_cases(refs: dict) -> list[tuple[str, dict, bool, str]]:
    """(label, synthetic_ref_or_row, expect_ok, detail_substr)."""
    sample = (refs.get("variants") or [None])[0]
    if not sample:
        return []
    return [
        (
            "ok_official_triple",
            {
                "kw": sample["kw"],
                "wh_per_km": sample["wh_per_km"],
                "wltpRangeKm": sample["wltpRangeKm"],
                "batteryKWh": None,
                "commercial_name": None,
                "commercial_url": None,
                "status": sample["status"],
            },
            True,
            "ok",
        ),
        (
            "fail_zr_equals_wh",
            {
                "kw": 150,
                "wh_per_km": 400,
                "wltpRangeKm": 400,
                "batteryKWh": None,
                "commercial_name": None,
                "commercial_url": None,
                "status": "F",
            },
            False,
            "zr_eq_wh",
        ),
        (
            "fail_battery_without_source",
            {
                "kw": sample["kw"],
                "wh_per_km": sample["wh_per_km"],
                "wltpRangeKm": sample["wltpRangeKm"],
                "batteryKWh": 99.0,
                "battery_source": None,
                "commercial_name": None,
                "commercial_url": None,
                "status": "F",
            },
            False,
            "battery",
        ),
        (
            "fail_commercial_without_url",
            {
                "kw": sample["kw"],
                "wh_per_km": sample["wh_per_km"],
                "wltpRangeKm": sample["wltpRangeKm"],
                "batteryKWh": None,
                "commercial_name": "Long Range",
                "commercial_url": None,
                "status": "F",
            },
            False,
            "commercial",
        ),
        (
            "fail_fp_conflict_marker",
            {
                "kw": 100,
                "wh_per_km": 150,
                "wltpRangeKm": 400,
                "batteryKWh": None,
                "commercial_name": None,
                "commercial_url": None,
                "status": "fp_conflict",
            },
            False,
            "fp_conflict",
        ),
    ]


def validate_variant_dict(v: dict) -> tuple[bool, str]:
    kw = v.get("kw")
    wh = v.get("wh_per_km")
    zr = v.get("wltpRangeKm")
    if kw is None or wh is None or zr is None:
        return False, "missing_fields"
    if int(round(float(zr))) == int(round(float(wh))):
        return False, "zr_eq_wh"
    if str(v.get("status") or "") == "fp_conflict":
        return False, "fp_conflict"
    if v.get("batteryKWh") not in (None, "", 0) and not v.get("battery_source"):
        return False, "battery_without_source"
    if v.get("commercial_name") and not v.get("commercial_url"):
        return False, "commercial_without_url"
    return True, "ok"


def main() -> int:
    if not REFS.exists() or not SEED.exists():
        print("missing refs or seed", file=sys.stderr)
        return 2

    refs = json.loads(REFS.read_text(encoding="utf-8"))
    rows = {str(r["id"]): r for r in json.loads(SEED.read_text(encoding="utf-8"))}
    variants = refs.get("variants") or []
    failures: list[str] = []
    must_ok = 0

    for label, payload, expect_ok, substr in must_fail_cases(refs):
        ok, detail = validate_variant_dict(payload)
        if ok == expect_ok and (substr in detail or (expect_ok and detail == "ok")):
            print(f"must-fail OK: {label} → ok={ok} ({detail})")
            must_ok += 1
        else:
            failures.append(f"{label}: expected_ok={expect_ok} got ok={ok} detail={detail}")
            print(f"must-fail FAIL: {label} → ok={ok} ({detail})")

    # Every ref variant must exist in seed with matching range/energy/power.
    checked = 0
    for v in sorted(variants, key=lambda x: str(x.get("id") or "")):
        checked += 1
        ok, detail = validate_variant_dict(v)
        if not ok:
            failures.append(f"{v.get('id')}: ref_invalid_{detail}")
            continue
        row = rows.get(str(v["id"]))
        if not row:
            failures.append(f"{v.get('id')}: missing_in_seed")
            continue
        if int(row.get("wltpRangeKm") or 0) != int(v["wltpRangeKm"]):
            failures.append(f"{v.get('id')}: range_mismatch")
        if abs(float(row.get("powerKw") or 0) - float(v["kw"])) > 0.6:
            failures.append(f"{v.get('id')}: kw_mismatch")
        energy = row.get("energyConsumptionKWhPerKm")
        if energy is None or abs(float(energy) * 1000.0 - float(v["wh_per_km"])) > 1.05:
            failures.append(f"{v.get('id')}: wh_mismatch")
        if row.get("parentId") != v.get("parentId"):
            failures.append(f"{v.get('id')}: parent_mismatch")
        if (row.get("batteryKWh") or None) != (v.get("batteryKWh") or None):
            # Allow both nil
            if row.get("batteryKWh") not in (None, 0) or v.get("batteryKWh") not in (None, 0):
                failures.append(f"{v.get('id')}: battery_mismatch")
        label = str(row.get("trim") or "")
        if "km WLTP" not in label:
            failures.append(f"{v.get('id')}: label_missing_wltp")
        if v.get("commercial_name") and not v.get("commercial_url"):
            failures.append(f"{v.get('id')}: commercial_no_url")

    # Single-version aliases must point at live children.
    for parent, child in sorted((refs.get("singleVersionAliases") or {}).items()):
        if child not in rows:
            failures.append(f"alias {parent}→{child}: child_missing")
        cleared = set(refs.get("clearedParentRangeIds") or [])
        if parent in cleared and parent in rows and rows[parent].get("wltpRangeKm") not in (None, 0):
            failures.append(f"alias {parent}: parent_range_not_cleared")

    # Tesla Model 3 2026 protected rows still present with range.
    for tid in sorted(build.TESLA_M3_2026_IDS):
        if tid not in rows or not rows[tid].get("wltpRangeKm"):
            failures.append(f"protected_missing_or_no_range:{tid}")
        else:
            print(f"must-fail OK: protected_{tid}")
            must_ok += 1

    print(
        f"checked_variants={checked} must_fail_ok={must_ok} failures={len(failures)}"
    )
    if failures:
        for f in failures[:40]:
            print(f"FAIL {f}", file=sys.stderr)
        if len(failures) > 40:
            print(f"... +{len(failures)-40} more", file=sys.stderr)
        return 1

    print("OK: ev variants match refs; must-fail cases rejected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
