#!/usr/bin/env python3
"""
Flag EV/PHEV catalog rows whose model/year has no EEA Electric-range record
in **any EU/EEA reporting country** (not Italy-only).

Does NOT auto-remove. Writes a full id list for PR review.

Usage:
  python3 scripts/check_catalog_existence.py
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import fill_catalog_bev_range_from_eea as fill
import fill_catalog_fuels_from_eea as eea

REPORT_PATH = eea.CACHE_DIR / "catalog_existence_scan_report.json"
REMOVAL_REPORT = eea.CACHE_DIR / "catalog_existence_removal_report.json"


def eu_electric_range_payload(brand_key: str) -> dict:
    """Same as IT Zr payload but without MS=IT — all reporting countries.

    No per-Zr MS sub-aggregation: large brands (AUDI/VW/…) 503 with that nest.
    Existence only needs model/year presence via parse_zr_index.
    """
    p = fill.electric_range_payload(brand_key)
    must = p["query"]["bool"]["must"]
    p["query"]["bool"]["must"] = [
        c
        for c in must
        if not (isinstance(c, dict) and c.get("term", {}).get("MS") == "IT")
    ]
    return p


def eu_cache_name(brand_key: str) -> str:
    return f"EU_{brand_key.replace(' ', '_')}_bev_Zr"


def load_brand_zr_eu(brand_key: str, *, use_cache: bool = True) -> dict:
    return eea.load_or_fetch(
        eu_cache_name(brand_key),
        eu_electric_range_payload(brand_key),
        use_cache=use_cache,
    )


# EU market renames / dual Cn (existence only — does not invent catalog rows).
EXISTENCE_MODEL_ALIASES: dict[tuple[str, str], list[str]] = {
    # NIO EL8 is the EU nameplate for ES8; EEA also has Cn "ES8.EL8".
    ("NIO", "EL8"): ["EL8", "ES8", "ES8.EL8"],
    ("NIO", "ES8"): ["ES8", "EL8", "ES8.EL8"],
}

# Post-rename nameplates: EEA match must include this token (C40 ≠ EC40).
EXISTENCE_REQUIRE_TOKEN: dict[tuple[str, str], str] = {
    ("VOLVO", "EC40"): "EC40",
    ("VOLVO", "EX40"): "EX40",
}


def model_year_in_eea(row: dict, index: dict) -> tuple[bool, list[str], list[str]]:
    """
    True if EEA has this model/year (any EU MS).

    Matching:
      1) fill.bev_model_keys on year keys (plus known EU renames)
      2) catalog model token (len≥3) appears inside any cn_raw for that year
      3) rename nameplates (EC40/EX40) require that token in mk/cn — not parent Cn
    """
    year = int(row.get("year") or 0)
    model = str(row.get("model") or "")
    brand = fill.brand_key_for_row(row)
    eea_keys_year = {mk for (mk, y) in index if y == year}

    candidates = [model]
    # Alias table keys use display-ish tokens (EL8 / ES8).
    for key in (
        (brand, model),
        (brand, model.upper()),
        (brand, eea.norm_alnum(model)),
    ):
        for alias in EXISTENCE_MODEL_ALIASES.get(key, []):
            if alias not in candidates:
                candidates.append(alias)

    matched: list[str] = []
    for cand in candidates:
        matched.extend(fill.bev_model_keys(cand, eea_keys_year, brand))
        mk = eea.model_name_merge_key(cand, brand) or eea.norm_alnum(cand)
        if mk in eea_keys_year:
            matched.append(mk)
    matched = sorted(set(matched))
    cn_hits: list[str] = []
    if matched:
        for mk in matched:
            cell = index.get((mk, year)) or {}
            cn_hits.extend(sorted(cell.get("cn_raws") or []))
        cn_hits = sorted(set(cn_hits))
    else:
        token = eea.norm_alnum(model)
        if len(token) >= 3:
            mks = []
            for (mk, y), cell in index.items():
                if y != year:
                    continue
                for cn in cell.get("cn_raws") or []:
                    if token in eea.norm_alnum(cn):
                        cn_hits.append(cn)
                        mks.append(mk)
                if token in mk:
                    mks.append(mk)
            matched = sorted(set(mks))
            cn_hits = sorted(set(cn_hits))

    if not matched and not cn_hits:
        return False, [], []

    require = EXISTENCE_REQUIRE_TOKEN.get((brand, eea.norm_alnum(model)))
    if require:
        mk_ok = any(require in mk for mk in matched)
        cn_ok = any(require in eea.norm_alnum(cn) for cn in cn_hits)
        if not mk_ok and not cn_ok:
            return False, matched, cn_hits

    return True, matched, cn_hits


def must_fail_cases() -> list[tuple[str, dict, bool]]:
    """expect_missing True → must be flagged as no EEA EU."""
    return [
        (
            "volvo_ec40_2022_name_too_early",
            {
                "id": "synthetic-volvo-ec40-2022",
                "brand": "Volvo",
                "model": "EC40",
                "year": 2022,
                "powertrain": "ev",
            },
            True,
        ),
        (
            "volvo_ec40_2023_name_too_early",
            {
                "id": "synthetic-volvo-ec40-2023",
                "brand": "Volvo",
                "model": "EC40",
                "year": 2023,
                "powertrain": "ev",
            },
            True,
        ),
        (
            "audi_e_tron_gt_2024_real",
            {
                "id": "synthetic-audi-e-tron-gt-2024",
                "brand": "Audi",
                "model": "e-tron GT",
                "year": 2024,
                "powertrain": "ev",
            },
            False,
        ),
        (
            "kia_soul_ev_2023_real",
            {
                "id": "synthetic-kia-soul-ev-2023",
                "brand": "Kia",
                "model": "Soul EV",
                "year": 2023,
                "powertrain": "ev",
            },
            False,
        ),
        (
            "kia_soul_ev_2024_real",
            {
                "id": "synthetic-kia-soul-ev-2024",
                "brand": "Kia",
                "model": "Soul EV",
                "year": 2024,
                "powertrain": "ev",
            },
            False,
        ),
        (
            "nio_el8_2022_via_es8_el8",
            {
                "id": "synthetic-nio-el8-2022",
                "brand": "NIO",
                "model": "EL8",
                "year": 2022,
                "powertrain": "ev",
            },
            False,
        ),
    ]


def scan(rows: list[dict]) -> list[dict]:
    targets = [
        r for r in rows if (r.get("powertrain") or "").lower() in {"ev", "phev"}
    ]
    by_brand: dict[str, list[dict]] = defaultdict(list)
    for r in targets:
        by_brand[fill.brand_key_for_row(r)].append(r)

    indexes: dict[str, dict] = {}
    for i, brand in enumerate(sorted(by_brand)):
        print(f"[{i+1}/{len(by_brand)}] EU Zr cache {brand}…", flush=True)
        wrap = load_brand_zr_eu(brand, use_cache=True)
        indexes[brand] = fill.parse_zr_index(wrap, brand)

    flagged: list[dict] = []
    for brand, brand_rows in sorted(by_brand.items()):
        index = indexes[brand]
        for r in sorted(brand_rows, key=lambda x: x.get("id") or ""):
            ok, matched, cn_hits = model_year_in_eea(r, index)
            if ok:
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
                    "reason": "no_eea_eu_zr_for_model_year",
                    "eea_model_keys_any_year": any_keys,
                    "eea_years_for_model": years_any,
                }
            )
    return flagged


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write-ids-only", action="store_true")
    args = ap.parse_args()

    rows = json.loads(eea.SEED_PATH.read_text(encoding="utf-8"))
    failures: list[str] = []
    must_ok = 0

    # Must-fail against EU indexes
    brand_needed = {
        fill.brand_key_for_row(row) for _, row, _ in must_fail_cases()
    }
    indexes = {
        b: fill.parse_zr_index(load_brand_zr_eu(b, use_cache=True), b)
        for b in sorted(brand_needed)
    }
    for label, row, expect_missing in must_fail_cases():
        brand = fill.brand_key_for_row(row)
        ok, matched, cn = model_year_in_eea(row, indexes[brand])
        missing = not ok
        if missing != expect_missing:
            failures.append(
                f"must-fail {label}: expect_missing={expect_missing} "
                f"got missing={missing} matched={matched} cn={cn[:3]}"
            )
        else:
            must_ok += 1
            print(
                f"must-fail OK: {label} → missing={missing} "
                f"matched={matched[:3]} cn={cn[:2]}"
            )

    # Also assert live catalog ids when present
    by_id = {r["id"]: r for r in rows}
    for live_id, expect_missing in (
        ("volvo-ec40-2022", True),
        ("volvo-ec40-2023", True),
        ("audi-e-tron-gt-2024", False),
        ("kia-soul-ev-2023", False),
        ("kia-soul-ev-2024", False),
        ("nio-el8-2022", False),
    ):
        row = by_id.get(live_id)
        if not row:
            print(f"(skip live {live_id}: not in seed)")
            continue
        brand = fill.brand_key_for_row(row)
        if brand not in indexes:
            indexes[brand] = fill.parse_zr_index(
                load_brand_zr_eu(brand, use_cache=True), brand
            )
        ok, _, _ = model_year_in_eea(row, indexes[brand])
        missing = not ok
        if missing != expect_missing:
            failures.append(
                f"live {live_id}: expect_missing={expect_missing} got {missing}"
            )
        else:
            must_ok += 1
            print(f"must-fail OK: live_{live_id} → missing={missing}")

    if REMOVAL_REPORT.is_file():
        rem = json.loads(REMOVAL_REPORT.read_text(encoding="utf-8"))
        ids = {r["id"] for r in rows}
        for k in rem.get("kept") or []:
            rid = k.get("id")
            if rid and rid not in ids:
                failures.append(f"kept id missing from seed: {rid}")
            elif rid:
                must_ok += 1
                print(f"must-fail OK: kept_still_present {rid}")
        for r in rem.get("removed") or []:
            rid = r.get("id")
            if rid and rid in ids:
                failures.append(f"removed id still in seed: {rid}")
            elif rid:
                must_ok += 1
                print(f"must-fail OK: removed_absent {rid}")

    flagged = scan(rows)
    flagged_ids = sorted(str(x["id"]) for x in flagged if x.get("id"))
    eea.CACHE_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(
        json.dumps(
            {
                "generatedAt": datetime.now(timezone.utc).isoformat(),
                "scope": "EEA CO2 monitoring Electric Zr — all MS (not IT-only)",
                "flagged_count": len(flagged_ids),
                "flagged_ids": flagged_ids,
                "flagged": flagged,
                "note": "Review only — do not auto-delete",
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"flagged_no_eea_eu={len(flagged_ids)} report={REPORT_PATH}")
    print(f"must_fail_ok={must_ok} failures={len(failures)}")
    if args.write_ids_only:
        print("\n".join(flagged_ids))
    if failures:
        for line in failures[:40]:
            print(f"  FAIL {line}", file=sys.stderr)
        return 1
    print("OK: existence scan (EU-wide)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
