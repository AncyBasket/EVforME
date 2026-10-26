#!/usr/bin/env python3
"""
Verify Tesla Model 3 2026 IT trim rows match catalog_truth_tesla_m3_2026_refs.json.

Usage:
  python3 scripts/check_catalog_tesla_m3_2026.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import fill_catalog_fuels_from_eea as eea

REFS = eea.CACHE_DIR / "catalog_truth_tesla_m3_2026_refs.json"
OLD_ID = "tesla-model-3-2026"


def must_fail_cases(refs: dict) -> list[tuple[str, dict, bool, str]]:
    """(label, row, expect_ok, detail_substr)."""
    good = refs["trims"][0]
    return [
        (
            "match_rwd_official",
            {
                "id": good["id"],
                "wltpRangeKm": good["wltpRangeKm"],
                "energyConsumptionKWhPerKm": good["energyConsumptionKWhPerKm"],
                "batteryKWh": None,
            },
            True,
            "ok",
        ),
        (
            "fail_invented_battery",
            {
                "id": good["id"],
                "wltpRangeKm": good["wltpRangeKm"],
                "energyConsumptionKWhPerKm": good["energyConsumptionKWhPerKm"],
                "batteryKWh": 60.0,
            },
            False,
            "battery",
        ),
        (
            "fail_wrong_range",
            {
                "id": good["id"],
                "wltpRangeKm": 999,
                "energyConsumptionKWhPerKm": good["energyConsumptionKWhPerKm"],
                "batteryKWh": None,
            },
            False,
            "range",
        ),
        (
            "fail_old_generic_id_still_present",
            {"id": OLD_ID},
            False,
            "removed",
        ),
    ]


def row_matches_ref(row: dict, ref: dict) -> tuple[bool, str]:
    if row.get("batteryKWh") not in (None, "", 0):
        return False, "battery_must_be_nil"
    if str(row.get("trim") or "") != str(ref.get("trim") or ""):
        return False, f"trim_mismatch_{row.get('trim')}_vs_{ref.get('trim')}"
    if int(row.get("wltpRangeKm") or 0) != int(ref["wltpRangeKm"]):
        return False, f"range_mismatch_{row.get('wltpRangeKm')}_vs_{ref['wltpRangeKm']}"
    energy = row.get("energyConsumptionKWhPerKm")
    if energy is None or abs(float(energy) - float(ref["energyConsumptionKWhPerKm"])) > 0.0005:
        return False, f"energy_mismatch_{energy}_vs_{ref['energyConsumptionKWhPerKm']}"
    w100 = row.get("wltpConsumptionKWh100km")
    if w100 is None or abs(float(w100) - float(ref["wltpConsumptionKWh100km"])) > 0.05:
        return False, f"w100_mismatch_{w100}_vs_{ref['wltpConsumptionKWh100km']}"
    for dim in ("lengthM", "widthM", "heightM"):
        if dim not in ref:
            continue
        got = row.get(dim)
        if got is None or abs(float(got) - float(ref[dim])) > 0.0015:
            return False, f"{dim}_mismatch_{got}_vs_{ref[dim]}"
    if int(row.get("maintenancePerYear") or 0) != int(ref.get("maintenancePerYear") or 0):
        return False, f"maint_mismatch_{row.get('maintenancePerYear')}_vs_{ref.get('maintenancePerYear')}"
    if row.get("powerKw") not in (None, "", 0) and ref.get("powerKw") in (None, "", 0):
        return False, "powerKw_invented"
    return True, "ok"


def main() -> int:
    if not REFS.is_file():
        print("MISSING refs", REFS, file=sys.stderr)
        return 1
    refs = json.loads(REFS.read_text(encoding="utf-8"))
    rows = {r["id"]: r for r in json.loads(eea.SEED_PATH.read_text(encoding="utf-8"))}
    failures: list[str] = []
    must_ok = 0

    if OLD_ID in rows:
        failures.append(f"old generic id still in seed: {OLD_ID}")
    else:
        must_ok += 1
        print(f"must-fail OK: old_id_removed → absent")

    for trim in refs.get("trims") or []:
        rid = trim["id"]
        row = rows.get(rid)
        if not row:
            failures.append(f"missing trim row {rid}")
            continue
        ok, detail = row_matches_ref(row, trim)
        if not ok:
            failures.append(f"trim {rid}: {detail}")
        else:
            must_ok += 1
            print(f"must-fail OK: trim_{rid} → {detail}")

    # Synthetic must-fail against refs without mutating seed
    for label, fake, expect_ok, substr in must_fail_cases(refs):
        if label == "fail_old_generic_id_still_present":
            ok = OLD_ID not in rows
            detail = "removed" if ok else "still_present"
            if ok != expect_ok and not (expect_ok is False and detail == "still_present"):
                # expect_ok False means we expect the check to "fail" the presence
                # Here we already asserted absence above; treat as pass when absent.
                pass
            if OLD_ID in rows:
                failures.append(f"must-fail {label}: old id still present")
            else:
                must_ok += 1
                print(f"must-fail OK: {label} → {detail}")
            continue
        ref = next(t for t in refs["trims"] if t["id"] == fake["id"])
        merged = {**ref, **fake}
        ok, detail = row_matches_ref(merged, ref)
        if ok != expect_ok:
            failures.append(
                f"must-fail {label}: expect_ok={expect_ok} got ok={ok} ({detail})"
            )
        else:
            must_ok += 1
            print(f"must-fail OK: {label} → ok={ok} ({detail})")

    # Migration / alias target exists
    mig = (refs.get("migration") or refs.get("alias") or {}).get(OLD_ID)
    if not mig or mig not in rows:
        failures.append(f"migration target missing: {mig}")
    else:
        must_ok += 1
        print(f"must-fail OK: migration_target {mig}")

    print(f"must_fail_ok={must_ok} failures={len(failures)}")
    if failures:
        for line in failures[:30]:
            print(f"  FAIL {line}", file=sys.stderr)
        return 1
    print("OK: Tesla Model 3 2026 IT trims match refs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
