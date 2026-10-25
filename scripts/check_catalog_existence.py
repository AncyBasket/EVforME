#!/usr/bin/env python3
"""
Flag EV/PHEV catalog rows whose model/year has no EEA Zr match.

Does NOT auto-remove. Writes a report for PR review.

Usage:
  python3 scripts/check_catalog_existence.py
  python3 scripts/check_catalog_existence.py --fail-on-empty-report-schema
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

REPORT_PATH = eea.CACHE_DIR / "catalog_existence_scan_report.json"
REMOVAL_REPORT = eea.CACHE_DIR / "catalog_existence_removal_report.json"


def must_fail_cases() -> list[tuple[str, dict, bool]]:
    """Synthetic rows: expect_missing True → should be flagged as no EEA."""
    return [
        (
            "ghost_equus_2025",
            {
                "id": "synthetic-hyundai-equus-2025",
                "brand": "Hyundai",
                "model": "Equus",
                "year": 2025,
                "powertrain": "ev",
            },
            True,
        ),
        (
            "real_ipace_shape",
            {
                "id": "synthetic-jaguar-i-pace-2024",
                "brand": "Jaguar",
                "model": "I-Pace",
                "year": 2024,
                "powertrain": "ev",
            },
            False,
        ),
    ]


def row_missing_eea(row: dict, index: dict) -> bool:
    year = int(row.get("year") or 0)
    model = str(row.get("model") or "")
    brand = fill.brand_key_for_row(row)
    eea_keys_year = {mk for (mk, y) in index if y == year}
    matched = fill.bev_model_keys(model, eea_keys_year, brand)
    return not bool(matched)


def scan(rows: list[dict]) -> list[dict]:
    targets = [
        r
        for r in rows
        if (r.get("powertrain") or "").lower() in {"ev", "phev"}
    ]
    by_brand: dict[str, list[dict]] = defaultdict(list)
    for r in targets:
        by_brand[fill.brand_key_for_row(r)].append(r)

    indexes: dict[str, dict] = {}
    for i, brand in enumerate(sorted(by_brand)):
        print(f"[{i+1}/{len(by_brand)}] Zr cache {brand}…", flush=True)
        wrap = fill.load_brand_zr(brand, use_cache=True)
        indexes[brand] = fill.parse_zr_index(wrap, brand)

    flagged: list[dict] = []
    for brand, brand_rows in sorted(by_brand.items()):
        index = indexes[brand]
        for r in sorted(brand_rows, key=lambda x: x.get("id") or ""):
            if not row_missing_eea(r, index):
                continue
            year = int(r.get("year") or 0)
            model = str(r.get("model") or "")
            all_keys = {mk for (mk, _y) in index}
            any_keys = fill.bev_model_keys(model, all_keys, brand)
            years_any = sorted({y for (mk, y) in index if mk in set(any_keys or [])})
            flagged.append(
                {
                    "id": r.get("id"),
                    "brand": r.get("brand"),
                    "model": model,
                    "year": year,
                    "powertrain": r.get("powertrain"),
                    "reason": "no_eea_zr_for_model_year",
                    "eea_model_keys_any_year": any_keys,
                    "eea_years_for_model": years_any,
                }
            )
    return flagged


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--fail-on-empty-report-schema",
        action="store_true",
        help="Fail if report cannot be written / must-fail broken",
    )
    args = ap.parse_args()

    rows = json.loads(eea.SEED_PATH.read_text(encoding="utf-8"))
    failures: list[str] = []
    must_ok = 0

    # Must-fail against live brand indexes for Jaguar/Hyundai
    jag = fill.parse_zr_index(fill.load_brand_zr("JAGUAR", use_cache=True), "JAGUAR")
    hyu = fill.parse_zr_index(fill.load_brand_zr("HYUNDAI", use_cache=True), "HYUNDAI")
    for label, row, expect_missing in must_fail_cases():
        brand = fill.brand_key_for_row(row)
        index = jag if brand == "JAGUAR" else hyu if brand == "HYUNDAI" else {}
        missing = row_missing_eea(row, index)
        if missing != expect_missing:
            failures.append(
                f"must-fail {label}: expect_missing={expect_missing} got {missing}"
            )
        else:
            must_ok += 1
            print(f"must-fail OK: {label} → missing={missing}")

    # Removal report integrity: kept ids still present; removed ids absent
    if REMOVAL_REPORT.is_file():
        rem = json.loads(REMOVAL_REPORT.read_text(encoding="utf-8"))
        by_id = {r["id"] for r in rows}
        for k in rem.get("kept") or []:
            rid = k.get("id")
            if rid and rid not in by_id:
                failures.append(f"kept id missing from seed: {rid}")
            else:
                must_ok += 1
                print(f"must-fail OK: kept_still_present {rid}")
        for r in rem.get("removed") or []:
            rid = r.get("id")
            if rid and rid in by_id:
                failures.append(f"removed id still in seed: {rid}")
            else:
                must_ok += 1
                print(f"must-fail OK: removed_absent {rid}")

    flagged = scan(rows)
    eea.CACHE_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(
        json.dumps(
            {
                "generatedAt": __import__("datetime").datetime.now(
                    __import__("datetime").timezone.utc
                ).isoformat(),
                "flagged_count": len(flagged),
                "flagged": flagged,
                "note": "Review only — do not auto-delete",
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"flagged_no_eea={len(flagged)} report={REPORT_PATH}")
    print(f"must_fail_ok={must_ok} failures={len(failures)}")
    if failures:
        for line in failures[:40]:
            print(f"  FAIL {line}", file=sys.stderr)
        return 1
    if args.fail_on_empty_report_schema and not REPORT_PATH.is_file():
        return 1
    print("OK: existence scan")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
