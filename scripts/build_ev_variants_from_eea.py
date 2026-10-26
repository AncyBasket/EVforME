#!/usr/bin/env python3
"""
Build BEV catalog versions from EEA co2cars EU-wide Zr (Electric range km).

Rules (no invented numbers):
- Source: EU Zr caches (same brand/model matching as check_catalog_existence /
  fill_catalog_bev_range_from_eea).
- A version = distinct (rounded kW, Zr). Wh/km is taken from the joint EEA
  record (same kW×Zr) with the most EU registrations — never averaged.
- Prefer Status F; use P only when F has no Zr. F/P with different Zr sets → no
  versions for that model/year (parent unchanged).
- Drop Zr == Wh/km on the same record.
- Drop Wh/km outside [WH_MIN, WH_MAX] (EEA unit junk; not OEM inventing).
- Drop versions with fewer than MIN_F_REGISTRATIONS Status F (or preferred
  status) registrations EU-wide in that year.
- Label: "<kW> kW · <Zr> km WLTP" (+ " · trazione integrale" only if Cn hints
  AWD). No commercial names without an official OEM URL ref.
- batteryKWh: nil on new version rows unless one of the 3 OEM-verified packs
  jointly matches kW±5 and Wh±1.
- Tesla Model 3 2026 official IT trims: untouched.
- seedVersion → 59.

Usage:
  python3 scripts/build_ev_variants_from_eea.py
  python3 scripts/build_ev_variants_from_eea.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import check_catalog_existence as existence
import fill_catalog_bev_range_from_eea as fill
import fill_catalog_fuels_from_eea as eea

NEW_SEED_VERSION = 59
MIN_F_REGISTRATIONS = 10
KW_TOL_ABS = 5.0
WH_TOL = 1.0  # Wh/km
# Passenger-BEV physical band for EEA Wh/km (same spirit as Zr==Wh drop).
# Values like 504 Wh/km with Zr≈175 are known EEA unit junk, not OEM WLTP.
WH_MIN = 90.0
WH_MAX = 350.0

REFS_PATH = eea.CACHE_DIR / "catalog_truth_ev_variants_refs.json"
FIXTURE_REFS = eea.REPO / "EVforME?Tests" / "Fixtures" / "catalog_truth_ev_variants_refs.json"
REPORT_PATH = eea.CACHE_DIR / "catalog_ev_variants_build_report.json"

# Official Tesla Italia Model 3 2026 trims — do not regenerate from EEA.
TESLA_M3_2026_IDS = {
    "tesla-model-3-trazione-posteriore-2026",
    "tesla-model-3-premium-trazione-posteriore-2026",
    "tesla-model-3-premium-long-range-2026",
    "tesla-model-3-performance-2026",
}

AWD_CN_RE = re.compile(
    r"(XDRIVE|4MATIC|QUATTRO|AWD|4WD|4X4|ALL.?WHEEL|TRAZIONE.?INTEGRALE|DUAL.?MOTOR|PERFORMANCE)",
    re.I,
)


def is_awd_hint(cn_raws: set[str]) -> bool:
    return any(AWD_CN_RE.search(cn) for cn in cn_raws)


def version_label(kw: float, zr: int, awd: bool) -> str:
    base = f"{int(round(kw))} kW · {int(zr)} km WLTP"
    if awd:
        return f"{base} · trazione integrale"
    return base


def version_id(parent_id: str, kw: float, wh: float, zr: int) -> str:
    # Identity is (kW, Zr); Wh is an attribute of the winning joint record.
    return f"{parent_id}-v{int(round(kw))}kw-{int(zr)}km"


def oem_battery_matches(parent: dict, kw: float, wh: float) -> float | None:
    """Return verified batteryKWh if parent pack jointly matches this version."""
    batt = parent.get("batteryKWh")
    if batt in (None, "", 0):
        return None
    p_kw = parent.get("powerKw")
    energy = parent.get("energyConsumptionKWhPerKm")
    if p_kw in (None, "", 0) or energy in (None, "", 0):
        return None
    catalog_wh = float(energy) * 1000.0
    if abs(float(p_kw) - float(kw)) > KW_TOL_ABS:
        return None
    if abs(catalog_wh - float(wh)) > WH_TOL:
        return None
    return float(batt)


def collect_versions_for_row(
    row: dict,
    index: dict,
) -> tuple[str, list[dict], set[str]]:
    """
    Returns (result, versions, cn_raws).
    result: ok | no_cn | fp_conflict | none_after_filters | skip_protected
    """
    rid = str(row.get("id") or "")
    if rid in TESLA_M3_2026_IDS:
        return "skip_protected", [], set()

    year = int(row.get("year") or 0)
    brand = fill.brand_key_for_row(row)
    eea_keys = {mk for (mk, y) in index if y == year}
    matched = fill.bev_model_keys(str(row.get("model") or ""), eea_keys, brand)
    if not matched:
        return "no_cn", [], set()

    cells = [index[(mk, year)] for mk in matched if (mk, year) in index]
    if not cells:
        return "no_cn", [], set()

    cell = fill.merge_cells(cells)
    cn_raws = set(cell.get("cn_raws") or [])
    status, raw_versions = fill.preferred_versions(cell)
    if status == "fp_conflict":
        return "fp_conflict", [], cn_raws
    if not raw_versions:
        return "none_after_filters", [], cn_raws

    # Dedupe by integer (kW, Zr); Wh from the joint record with most regs.
    best: dict[tuple[int, int], dict] = {}
    for v in raw_versions:
        kw = float(v["kw"])
        wh = float(v["wh"])
        zr = int(v["zr"])
        if zr <= 0:
            continue
        if wh < WH_MIN or wh > WH_MAX:
            continue
        key = (int(round(kw)), zr)
        prev = best.get(key)
        if prev is None or float(v["n"]) > float(prev["n"]):
            best[key] = {
                "kw": kw,
                "wh": wh,
                "zr": zr,
                "n": float(v["n"]),
                "status": status,
            }

    kept = [v for v in best.values() if float(v["n"]) >= MIN_F_REGISTRATIONS]
    if not kept:
        return "none_after_filters", [], cn_raws

    # Deterministic order: range desc, then kW, then Wh.
    kept.sort(key=lambda v: (-int(v["zr"]), float(v["kw"]), float(v["wh"])))
    return "ok", kept, cn_raws


def build_child_row(
    parent: dict,
    ver: dict,
    *,
    awd: bool,
    cn_raws: set[str],
) -> tuple[dict, dict]:
    kw = float(ver["kw"])
    wh = float(ver["wh"])
    zr = int(ver["zr"])
    pid = str(parent["id"])
    child_id = version_id(pid, kw, wh, zr)
    label = version_label(kw, zr, awd)
    batt = oem_battery_matches(parent, kw, wh)

    child = dict(parent)
    child["id"] = child_id
    child["trim"] = label
    child["parentId"] = pid
    child["powerKw"] = round(kw, 1)
    child["energyConsumptionKWhPerKm"] = round(wh / 1000.0, 6)
    child["wltpConsumptionKWh100km"] = round(wh / 10.0, 2)
    child["wltpRangeKm"] = zr
    child["batteryKWh"] = batt
    child["sourceName"] = "EEA co2cars EU Zr (variant)"
    child["sourceUpdatedAt"] = datetime.now(timezone.utc).date().isoformat()
    child["confidenceScore"] = 0.85 if ver.get("status") == "F" else 0.7

    ref = {
        "id": child_id,
        "parentId": pid,
        "brand": parent.get("brand"),
        "model": parent.get("model"),
        "year": parent.get("year"),
        "kw": round(kw, 1),
        "wh_per_km": round(wh, 1),
        "wltpRangeKm": zr,
        "status": ver.get("status"),
        "registrations": round(float(ver["n"]), 1),
        "countries": ["EU-wide"],
        "cn_raws": sorted(cn_raws),
        "label": label,
        "awd_from_cn": awd,
        "batteryKWh": batt,
        "battery_source": "oem_verified_parent_match" if batt is not None else None,
        "commercial_name": None,
        "commercial_url": None,
        "source": "EEA co2cars EU Zr",
    }
    return child, ref


def bump_cdn(rows: list[dict]) -> None:
    meta_path = eea.REPO / "EVforME?" / "Data" / "catalog_cdn.json"
    meta = {
        "url": "",
        "publishedUrl": "",
        "rows": len(rows),
        "bytes": 0,
        "source": "vehicles.seed.quality.json",
        "host": "bundled-offline-first",
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        "policy": "offline-first",
        "seedVersion": NEW_SEED_VERSION,
        "note": (
            f"seedVersion {NEW_SEED_VERSION}: BEV EEA EU versions "
            f"(min {MIN_F_REGISTRATIONS} F/P regs; F preferred; Zr==Wh dropped; "
            "F/P conflict → no variants; Tesla Model 3 2026 IT trims preserved)."
        ),
    }
    # Approximate minified size after write
    payload = json.dumps(
        [{k: v for k, v in r.items() if v is not None} for r in rows],
        separators=(",", ":"),
        ensure_ascii=False,
    )
    meta["bytes"] = len(payload.encode("utf-8"))
    meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    rows: list[dict] = json.loads(eea.SEED_PATH.read_text(encoding="utf-8"))
    # Idempotent: strip any prior EEA version children before rebuilding.
    rows = [r for r in rows if not r.get("parentId")]
    bev = [r for r in rows if r.get("powertrain") == "ev"]
    before_with_range = sum(1 for r in bev if r.get("wltpRangeKm"))

    brands = sorted({fill.brand_key_for_row(r) for r in bev})
    indexes: dict[str, dict] = {}
    for i, brand in enumerate(brands):
        print(f"[{i+1}/{len(brands)}] EU Zr cache {brand}…", flush=True)
        wrap = existence.load_brand_zr_eu(brand, use_cache=True)
        indexes[brand] = fill.parse_zr_index(wrap, brand)

    children: list[dict] = []
    refs_variants: list[dict] = []
    cleared_parents: list[str] = []
    single_alias: dict[str, str] = {}
    no_variant_parents: list[dict] = []
    stats: dict[str, int] = defaultdict(int)

    by_id = {str(r["id"]): r for r in rows}
    existing_ids = set(by_id)

    for parent in bev:
        pid = str(parent["id"])
        brand = fill.brand_key_for_row(parent)
        result, versions, cn_raws = collect_versions_for_row(parent, indexes[brand])
        stats[result] += 1

        if result != "ok":
            if result != "skip_protected":
                no_variant_parents.append(
                    {
                        "id": pid,
                        "brand": parent.get("brand"),
                        "model": parent.get("model"),
                        "year": parent.get("year"),
                        "reason": result,
                        "had_wltpRangeKm": parent.get("wltpRangeKm"),
                    }
                )
            continue

        awd = is_awd_hint(cn_raws)
        built: list[tuple[dict, dict]] = []
        for ver in versions:
            child, ref = build_child_row(parent, ver, awd=awd, cn_raws=cn_raws)
            if child["id"] in existing_ids or any(c["id"] == child["id"] for c, _ in built):
                # Extremely unlikely collision — skip duplicate id.
                stats["id_collision"] += 1
                continue
            built.append((child, ref))

        if not built:
            stats["ok_but_empty"] += 1
            no_variant_parents.append(
                {
                    "id": pid,
                    "brand": parent.get("brand"),
                    "model": parent.get("model"),
                    "year": parent.get("year"),
                    "reason": "ok_but_empty",
                    "had_wltpRangeKm": parent.get("wltpRangeKm"),
                }
            )
            continue

        if len(built) == 1:
            child, ref = built[0]
            children.append(child)
            refs_variants.append(ref)
            single_alias[pid] = child["id"]
            # Clear parent range so charges require the resolved child via alias.
            if parent.get("wltpRangeKm") is not None:
                cleared_parents.append(pid)
            stats["single"] += 1
        else:
            for child, ref in built:
                children.append(child)
                refs_variants.append(ref)
            if parent.get("wltpRangeKm") is not None:
                cleared_parents.append(pid)
            stats["multi"] += 1

    # Apply to seed copy
    out_rows = []
    cleared_set = set(cleared_parents)
    child_ids = {c["id"] for c in children}
    for r in rows:
        rid = str(r["id"])
        if rid in child_ids:
            continue  # will append fresh children
        row = dict(r)
        if rid in cleared_set:
            row["wltpRangeKm"] = None
        out_rows.append(row)
    out_rows.extend(children)

    # Stable-ish order: keep original relative order, children after parents block
    # (children already appended at end — fine for decode).

    after_bev = [r for r in out_rows if r.get("powertrain") == "ev"]
    after_with_range = sum(1 for r in after_bev if r.get("wltpRangeKm"))

    refs = {
        "seedVersion": NEW_SEED_VERSION,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "source": "EEA co2cars EU field Zr (Electric range km)",
        "rules": [
            f"Min registrations per version: {MIN_F_REGISTRATIONS} (preferred Status)",
            "Status F preferred; P only if F has no Zr",
            "F and P with different Zr sets → no variants for model/year",
            "Drop Zr == Wh/km on same record",
            f"Drop Wh/km outside [{WH_MIN:g}, {WH_MAX:g}] (EEA unit junk)",
            "Dedupe by rounded int(kW)+Zr; Wh from max-registration joint record",
            "Label: '<kW> kW · <Zr> km WLTP' (+ AWD hint from Cn only)",
            "batteryKWh nil unless OEM-verified parent pack matches kW±5 & Wh±1",
            "Tesla Model 3 2026 IT trims preserved",
            "Countries: EU-wide aggregate (no per-MS breakdown in cache)",
        ],
        "minRegistrations": MIN_F_REGISTRATIONS,
        "stats": {
            "bev_before": len(bev),
            "bev_with_range_before": before_with_range,
            "bev_after": len(after_bev),
            "bev_with_range_after": after_with_range,
            "variant_rows": len(children),
            "parents_single": stats["single"],
            "parents_multi": stats["multi"],
            "parents_no_variant": len(no_variant_parents),
            "catalog_rows_before": len(rows),
            "catalog_rows_after": len(out_rows),
            **{f"result_{k}": v for k, v in stats.items()},
        },
        "singleVersionAliases": single_alias,
        "clearedParentRangeIds": sorted(cleared_set),
        "variants": refs_variants,
        "noVariantParents": no_variant_parents,
    }

    report = {
        "seedVersion": NEW_SEED_VERSION,
        "stats": refs["stats"],
        "topParentsByVariantCount": sorted(
            (
                {
                    "parentId": pid,
                    "n": sum(1 for v in refs_variants if v["parentId"] == pid),
                }
                for pid in {v["parentId"] for v in refs_variants}
            ),
            key=lambda x: -x["n"],
        )[:20],
    }

    print(json.dumps(refs["stats"], indent=2))
    print(
        f"variant_rows={len(children)} catalog {len(rows)} → {len(out_rows)} "
        f"range {before_with_range} → {after_with_range}"
    )

    if args.dry_run:
        print("dry-run: no write")
        return 0

    eea.SEED_PATH.write_text(
        json.dumps(out_rows, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    alias_path = eea.REPO / "EVforME?" / "Data" / "ev_variant_single_aliases.json"
    alias_path.write_text(
        json.dumps(single_alias, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    # VehicleCatalogService.bundledSeedVersion bumped in Swift separately.
    bump_cdn(out_rows)
    REFS_PATH.write_text(json.dumps(refs, indent=2) + "\n", encoding="utf-8")
    FIXTURE_REFS.parent.mkdir(parents=True, exist_ok=True)
    # Slim fixture for unit tests (full refs stay in scripts/cache).
    batt = [v for v in refs_variants if v.get("batteryKWh") is not None][:10]
    sample = refs_variants[:30] + batt
    seen: set[str] = set()
    slim_variants = []
    for v in sample:
        if v["id"] in seen:
            continue
        seen.add(v["id"])
        slim_variants.append(v)
    slim = {
        "seedVersion": NEW_SEED_VERSION,
        "generatedAt": refs["generatedAt"],
        "source": refs["source"],
        "rules": refs["rules"],
        "minRegistrations": MIN_F_REGISTRATIONS,
        "stats": refs["stats"],
        "singleVersionAliases": single_alias,
        "clearedParentRangeIds": sorted(cleared_set),
        "variants": slim_variants,
        "noVariantParentsSample": no_variant_parents[:50],
        "noVariantParentsCount": len(no_variant_parents),
        "note": "Slim fixture; full refs in scripts/cache/eea/catalog_truth_ev_variants_refs.json",
    }
    FIXTURE_REFS.write_text(json.dumps(slim, indent=2) + "\n", encoding="utf-8")
    REPORT_PATH.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {eea.SEED_PATH}")
    print(f"wrote {REFS_PATH}")
    print(f"wrote slim fixture {FIXTURE_REFS}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
