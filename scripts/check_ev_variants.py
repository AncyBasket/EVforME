#!/usr/bin/env python3
"""
Verify BEV catalog version groups against catalog_truth_ev_variants_refs.json.

Must-fail cases + seed/ref coherence. PYTHONHASHSEED-stable.

Usage:
  python3 scripts/check_ev_variants.py
"""

from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import build_ev_variants_from_eea as build
import fill_catalog_fuels_from_eea as eea

REFS = eea.CACHE_DIR / "catalog_truth_ev_variants_refs.json"
SEED = eea.SEED_PATH


def _validate_group_bounds(v: dict) -> tuple[bool, str]:
    records = v.get("eea_records") or []
    if not records:
        return False, "missing_eea_records"
    zrs = [int(r["wltpRangeKm"]) for r in records]
    whs = [float(r["wh_per_km"]) for r in records]
    kws = [float(r["kw"]) for r in records]
    zr_min = int(v.get("wltpRangeKmMin", v.get("wltpRangeKm")))
    zr_max = int(v.get("wltpRangeKmMax", zr_min))
    wh_min = float(v.get("wh_per_km_min", v.get("wh_per_km")))
    wh_max = float(v.get("wh_per_km_max", v.get("wh_per_km")))
    if zr_min != min(zrs) or zr_max != max(zrs):
        return False, "minmax_outside_eea_records"
    if abs(wh_min - min(whs)) > 0.15 or abs(wh_max - max(whs)) > 0.15:
        return False, "minmax_outside_eea_records"
    mean_kw = float(v["kw"])
    # Official OEM match may merge axle + system EEA filings under one trim
    # (Tesla rule A); label kw is system max, so skip spread-vs-label check.
    if not v.get("official_matched"):
        if any(abs(k - mean_kw) > build.KW_TOL_ABS + 0.05 for k in kws):
            return False, "kw_spread_over_tol"
    if int(v.get("wltpRangeKm")) != zr_min:
        return False, "calc_not_prudent_min_range"
    if abs(float(v.get("wh_per_km")) - wh_max) > 0.15:
        return False, "calc_not_prudent_max_wh"
    return True, "ok"


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
    if "eea_records" in v:
        return _validate_group_bounds(v)
    return True, "ok"


def must_fail_cases(refs: dict) -> list[tuple[str, dict, bool, str]]:
    sample = (refs.get("variants") or [None])[0]
    if not sample:
        return []
    recs = list(sample.get("eea_records") or [])
    if not recs:
        recs = [
            {
                "kw": sample["kw"],
                "wh_per_km": sample["wh_per_km"],
                "wltpRangeKm": sample["wltpRangeKm"],
                "n": 10,
                "status": "F",
            }
        ]
    zr_min = int(sample.get("wltpRangeKmMin", sample["wltpRangeKm"]))
    zr_max = int(sample.get("wltpRangeKmMax", sample["wltpRangeKm"]))
    wh_min = float(sample.get("wh_per_km_min", sample["wh_per_km"]))
    wh_max = float(sample.get("wh_per_km_max", sample["wh_per_km"]))

    bad_range = dict(sample)
    bad_range["wltpRangeKmMin"] = zr_min - 50
    bad_range["wltpRangeKm"] = zr_min - 50
    bad_range["eea_records"] = recs

    bad_kw = dict(sample)
    bad_kw["eea_records"] = recs + [
        {
            "kw": float(sample["kw"]) + build.KW_TOL_ABS + 20,
            "wh_per_km": wh_max,
            "wltpRangeKm": zr_min,
            "n": 10,
            "status": "F",
        }
    ]

    bad_prudent = dict(sample)
    bad_prudent["wltpRangeKm"] = zr_max if zr_max != zr_min else zr_min + 10
    bad_prudent["wltpRangeKmMin"] = zr_min
    bad_prudent["wltpRangeKmMax"] = max(zr_max, zr_min + 10)
    if zr_max == zr_min:
        bad_prudent["eea_records"] = recs + [
            {
                "kw": sample["kw"],
                "wh_per_km": wh_max,
                "wltpRangeKm": zr_min + 10,
                "n": 10,
                "status": "F",
            }
        ]
    else:
        bad_prudent["eea_records"] = recs

    return [
        ("ok_official_group", dict(sample), True, "ok"),
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
                **{
                    k: sample[k]
                    for k in sample
                    if k not in ("battery_source", "eea_records")
                },
                "batteryKWh": 99.0,
                "battery_source": None,
            },
            False,
            "battery",
        ),
        (
            "fail_commercial_without_url",
            {
                **{k: sample[k] for k in sample if k != "eea_records"},
                "commercial_name": "Long Range",
                "commercial_url": None,
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
        (
            "fail_minmax_outside_records",
            bad_range,
            False,
            "minmax_outside_eea_records",
        ),
        (
            "fail_kw_spread_over_tol",
            bad_kw,
            False,
            "kw_spread_over_tol",
        ),
        (
            "fail_calc_not_prudent_min_range",
            bad_prudent,
            False,
            "calc_not_prudent",
        ),
    ]


def main() -> int:
    if not REFS.exists() or not SEED.exists():
        print("missing refs or seed", file=sys.stderr)
        return 2

    refs = json.loads(REFS.read_text(encoding="utf-8"))
    rows = {str(r["id"]): r for r in json.loads(SEED.read_text(encoding="utf-8"))}
    variants = refs.get("variants") or []
    failures: list[str] = []
    must_ok = 0
    nov = refs.get("noVariantParents") or []

    for label, payload, expect_ok, substr in must_fail_cases(refs):
        ok, detail = validate_variant_dict(payload)
        if ok == expect_ok and (substr in detail or (expect_ok and detail == "ok")):
            print(f"must-fail OK: {label} → ok={ok} ({detail})")
            must_ok += 1
        else:
            failures.append(
                f"{label}: expected_ok={expect_ok} got ok={ok} detail={detail}"
            )
            print(f"must-fail FAIL: {label} → ok={ok} ({detail})")

    if any(x.get("reason") == "fp_conflict" for x in nov):
        failures.append("whole_model_fp_conflict_still_present")
        print("must-fail FAIL: whole_model_discarded_for_fp_conflict")
    else:
        print("must-fail OK: no_whole_model_fp_conflict")
        must_ok += 1

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
        if int(row.get("wltpRangeKmMax") or row.get("wltpRangeKm") or 0) != int(
            v.get("wltpRangeKmMax", v["wltpRangeKm"])
        ):
            failures.append(f"{v.get('id')}: range_max_mismatch")
        if abs(float(row.get("powerKw") or 0) - float(v["kw"])) > 0.6:
            failures.append(f"{v.get('id')}: kw_mismatch")
        energy = row.get("energyConsumptionKWhPerKm")
        if energy is None or abs(float(energy) * 1000.0 - float(v["wh_per_km"])) > 1.05:
            failures.append(f"{v.get('id')}: wh_mismatch_prudent")
        if row.get("parentId") != v.get("parentId"):
            failures.append(f"{v.get('id')}: parent_mismatch")
        if not row.get("usesPrudentVariantBounds"):
            failures.append(f"{v.get('id')}: missing_prudent_flag")
        trim = str(row.get("trim") or "")
        matched = bool(v.get("official_matched"))
        if matched:
            if " · " not in trim or "kW" not in trim:
                failures.append(f"{v.get('id')}: matched_label_format")
            if not v.get("official_url") and not v.get("commercial_url"):
                failures.append(f"{v.get('id')}: matched_missing_url")
            if abs(float(v.get("official_power_kw") or v["kw"]) - float(row.get("powerKw") or 0)) > 0.6:
                failures.append(f"{v.get('id')}: matched_kw_not_official")
        else:
            if not trim.startswith("Versione "):
                failures.append(f"{v.get('id')}: unmatched_label_not_versione")
            # EEA kW must not appear in the title for unmatched versions
            if re.search(r"\b\d+\s*kW\b", trim):
                failures.append(f"{v.get('id')}: unmatched_title_has_eea_kw")
            if not v.get("eeaHomologationNote") and not row.get("eeaHomologationNote"):
                failures.append(f"{v.get('id')}: unmatched_missing_homologation_note")
        if v.get("commercial_name") and not v.get("commercial_url"):
            failures.append(f"{v.get('id')}: commercial_no_url")
        if v.get("official_name") and not (v.get("official_url") or v.get("commercial_url")):
            failures.append(f"{v.get('id')}: official_name_without_url")
        url = str(v.get("official_url") or v.get("commercial_url") or "")
        if url and re.search(
            r"(ev-database|wikipedia|autocar|insideevs|electrek|carwow)", url, re.I
        ):
            failures.append(f"{v.get('id')}: third_party_url")
        if not v.get("eea_records"):
            failures.append(f"{v.get('id')}: missing_eea_records_list")

    for parent, child in sorted((refs.get("singleVersionAliases") or {}).items()):
        if child not in rows:
            failures.append(f"alias {parent}→{child}: child_missing")
        cleared = set(refs.get("clearedParentRangeIds") or [])
        if parent in cleared and parent in rows and rows[parent].get("wltpRangeKm") not in (
            None,
            0,
        ):
            failures.append(f"alias {parent}: parent_range_not_cleared")

    for tid in sorted(build.TESLA_M3_2026_IDS):
        if tid not in rows or not rows[tid].get("wltpRangeKm"):
            failures.append(f"protected_missing_or_no_range:{tid}")
        else:
            print(f"must-fail OK: protected_{tid}")
            must_ok += 1

    for pid in (
        "bmw-i3-2020",
        "bmw-i4-2022",
        "bmw-ix-2022",
        "bmw-ix1-2023",
        "bmw-ix3-2021",
        "bmw-i5-2023",
        "bmw-i7-2023",
        "audi-e-tron-gt-2023",
    ):
        kids = [v for v in variants if v.get("parentId") == pid]
        wiped = any(
            x.get("id") == pid and x.get("reason") == "fp_conflict" for x in nov
        )
        if wiped:
            failures.append(f"focus_{pid}_wiped_by_fp_conflict")
        elif kids:
            print(f"must-fail OK: focus_has_groups_{pid}_n={len(kids)}")
            must_ok += 1
        else:
            # May be no_cn / none_after_filters — not an fp whole wipe.
            print(f"must-fail OK: focus_not_fp_wiped_{pid}")
            must_ok += 1

    ioniq_n = [v for v in variants if v.get("parentId") == "hyundai-ioniq-5-n-2023"]
    if len(ioniq_n) > 1:
        failures.append(f"ioniq-5-n-2023_too_many_groups:{len(ioniq_n)}")
        print(f"must-fail FAIL: ioniq-5-n-2023 groups={len(ioniq_n)}")
    else:
        print(f"must-fail OK: ioniq-5-n-2023_groups={len(ioniq_n)}")
        must_ok += 1

    spring = [v for v in variants if v.get("parentId") == "dacia-spring-2023"]
    if len(spring) > 2:
        failures.append(f"dacia-spring-2023_too_many_groups:{len(spring)}")
        print(f"must-fail FAIL: dacia-spring-2023 groups={len(spring)}")
    else:
        print(f"must-fail OK: dacia-spring-2023_groups={len(spring)}")
        must_ok += 1

    # Label pass gates (seed v61+)
    stats = refs.get("stats") or {}
    top40_src = int(stats.get("top40_with_official_source") or 0)
    if top40_src < 30:
        failures.append(f"top40_official_sources:{top40_src}<30")
        print(f"must-fail FAIL: top40_with_official_source={top40_src}")
    else:
        print(f"must-fail OK: top40_with_official_source={top40_src}")
        must_ok += 1

    mach = [v for v in variants if v.get("parentId") == "ford-mustang-mach-e-2025"]
    if any(float(v.get("eea_kw") or v.get("kw") or 0) > 358 + 5 for v in mach):
        failures.append("mach-e-2025_kept_over_official_max")
        print("must-fail FAIL: mach-e over-max group kept")
    else:
        print("must-fail OK: mach-e-2025_no_over_max")
        must_ok += 1

    ioniq_42 = [
        v
        for v in variants
        if v.get("parentId") == "hyundai-ioniq-5-2021"
        and abs(float(v.get("eea_kw") or v.get("kw") or 0) - 42) < 0.6
    ]
    if ioniq_42 and any(v.get("official_matched") for v in ioniq_42):
        failures.append("ioniq-5-2021_42kw_falsely_matched")
        print("must-fail FAIL: ioniq 42 kW matched")
    elif ioniq_42 and not all(str(v.get("label") or "").startswith("Versione") for v in ioniq_42):
        failures.append("ioniq-5-2021_42kw_not_versione")
        print("must-fail FAIL: ioniq 42 kW not Versione")
    else:
        print("must-fail OK: ioniq-5-2021_42kw_unmatched_versione")
        must_ok += 1

    min_share = float(refs.get("minShareOfParent") or build.MIN_SHARE_OF_PARENT)
    min_abs = float(refs.get("minAbsoluteRegistrations") or build.MIN_ABS_REGISTRATIONS)
    by_parent_regs: dict[str, float] = defaultdict(float)
    for v in variants:
        by_parent_regs[str(v.get("parentId") or "")] += float(v.get("registrations") or 0)
    for v in variants:
        n = float(v.get("registrations") or 0)
        total = by_parent_regs.get(str(v.get("parentId") or ""), 0.0) or 0.0
        share = (n / total) if total > 0 else 0.0
        if n < min_abs and share < min_share:
            failures.append(f"{v.get('id')}: below_registration_threshold")
    else:
        # for-else: no break — still print OK if no failures appended for this check
        pass
    if not any("below_registration_threshold" in f for f in failures):
        print("must-fail OK: no_group_below_registration_threshold")
        must_ok += 1
    else:
        print("must-fail FAIL: group_below_registration_threshold")

    # EEA record fingerprint must not appear under two parents.
    fp_owners: dict[tuple, str] = {}
    shared = 0
    for v in variants:
        pid = str(v.get("parentId") or "")
        for rec in v.get("eea_records") or []:
            fp = rec.get("fingerprint")
            if fp is None:
                fp = (
                    int(rec.get("year") or v.get("year") or 0),
                    str(rec.get("eea_model_key") or ""),
                    round(float(rec["kw"]), 1),
                    round(float(rec["wh_per_km"]), 1),
                    int(rec["wltpRangeKm"]),
                    bool(rec.get("awd")),
                    str(rec.get("status") or ""),
                )
            else:
                fp = tuple(fp)
            prev = fp_owners.get(fp)
            if prev is None:
                fp_owners[fp] = pid
            elif prev != pid:
                shared += 1
                failures.append(f"shared_eea_record:{fp}:parents={prev},{pid}")
    if shared == 0:
        print("must-fail OK: no_eea_record_shared_across_parents")
        must_ok += 1
    else:
        print(f"must-fail FAIL: shared_eea_records={shared}")

    print(
        f"checked_variants={checked} must_fail_ok={must_ok} failures={len(failures)}"
    )
    if failures:
        for f in failures[:40]:
            print(f"FAIL {f}", file=sys.stderr)
        if len(failures) > 40:
            print(f"... +{len(failures)-40} more", file=sys.stderr)
        return 1

    print("OK: ev variant groups match refs; must-fail cases rejected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
