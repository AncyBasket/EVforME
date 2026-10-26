#!/usr/bin/env python3
"""
Build BEV catalog versions from EEA co2cars EU-wide Zr (Electric range km).

Rules (no invented numbers):
- Source: EU Zr caches (same brand/model matching as check_catalog_existence /
  fill_catalog_bev_range_from_eea).
- A version GROUP = same power cluster (kW ±5) + same traction (AWD hint from
  EEA Cn / model key). Merge all qualifying EEA records into the group.
- Each group exposes Zr min/max and Wh/km min/max from its EEA records only.
- Catalog calc fields use the prudent pair: Zr MIN + Wh MAX.
- Prefer Status F; keep P-only (kW,Zr) keys; if F and P share (kW,Zr) with
  different Wh → drop that conflicting pair only (never the whole model/year).
- Drop Zr == Wh/km; drop Wh outside [WH_MIN, WH_MAX]; min registrations threshold.
- Label: "<kW> kW" (+ " · trazione integrale"); range shown separately in UI.
- batteryKWh: nil unless OEM-verified parent pack matches kW±5 & Wh±1 (prudent Wh).
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
from collections import Counter, defaultdict
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
WH_MIN = 90.0
WH_MAX = 350.0

REFS_PATH = eea.CACHE_DIR / "catalog_truth_ev_variants_refs.json"
FIXTURE_REFS = eea.REPO / "EVforME?Tests" / "Fixtures" / "catalog_truth_ev_variants_refs.json"
REPORT_PATH = eea.CACHE_DIR / "catalog_ev_variants_build_report.json"
ALIAS_PATH = eea.REPO / "EVforME?" / "Data" / "ev_variant_single_aliases.json"

TESLA_M3_2026_IDS = {
    "tesla-model-3-trazione-posteriore-2026",
    "tesla-model-3-premium-trazione-posteriore-2026",
    "tesla-model-3-premium-long-range-2026",
    "tesla-model-3-performance-2026",
}

AWD_CN_RE = re.compile(
    r"(XDRIVE|4MATIC|QUATTRO|AWD|4WD|4X4|ALL.?WHEEL|TRAZIONE.?INTEGRALE|DUAL.?MOTOR)",
    re.I,
)


def is_awd_hint(cn_raws: set[str], model_key: str = "") -> bool:
    blob = " ".join(cn_raws) + " " + model_key
    return bool(AWD_CN_RE.search(blob))


def version_label(kw: float, awd: bool) -> str:
    base = f"{int(round(kw))} kW"
    if awd:
        return f"{base} · trazione integrale"
    return base


def version_id(parent_id: str, kw: float, awd: bool) -> str:
    suffix = "awd" if awd else "rwd"
    return f"{parent_id}-v{int(round(kw))}kw-{suffix}"


def range_caption(zr_min: int, zr_max: int) -> str:
    if zr_min == zr_max:
        return f"Autonomia WLTP {zr_min} km (dipende da cerchi e optional)"
    return (
        f"Autonomia WLTP {zr_min}–{zr_max} km "
        f"(dipende da cerchi e optional)"
    )


def oem_battery_matches(parent: dict, kw: float, wh: float) -> float | None:
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


def filter_raw_versions(raw: list[dict], status: str) -> list[dict]:
    out: list[dict] = []
    for v in raw:
        kw = float(v["kw"])
        wh = float(v["wh"])
        zr = int(v["zr"])
        if zr <= 0:
            continue
        if wh < WH_MIN or wh > WH_MAX:
            continue
        out.append(
            {
                "kw": kw,
                "wh": wh,
                "zr": zr,
                "n": float(v["n"]),
                "status": status,
            }
        )
    return out


def merge_fp_versions(cell: dict) -> tuple[list[dict], int]:
    """
    Prefer F; keep P-only (kW,Zr). If F and P share (kW,Zr) with different Wh,
    drop that conflicting pair only. Returns (versions, n_conflicts_dropped).
    """
    f_raw = filter_raw_versions(fill.versions_from_zr_map(cell.get("F") or {}), "F")
    p_raw = filter_raw_versions(fill.versions_from_zr_map(cell.get("P") or {}), "P")

    def index(vs: list[dict]) -> dict[tuple[int, int], dict]:
        best: dict[tuple[int, int], dict] = {}
        for v in vs:
            key = (int(round(float(v["kw"]))), int(v["zr"]))
            prev = best.get(key)
            if prev is None or float(v["n"]) > float(prev["n"]):
                best[key] = v
        return best

    f_by = index(f_raw)
    p_by = index(p_raw)
    conflicts = 0
    out: list[dict] = []
    for key in sorted(set(f_by) | set(p_by)):
        if key in f_by and key in p_by:
            if abs(float(f_by[key]["wh"]) - float(p_by[key]["wh"])) > WH_TOL:
                conflicts += 1
                continue
            out.append(f_by[key])
        elif key in f_by:
            out.append(f_by[key])
        else:
            out.append(p_by[key])
    return out, conflicts


def cluster_by_kw(records: list[dict]) -> list[list[dict]]:
    """Greedy clusters: same AWD already filtered; merge kW within ±KW_TOL_ABS."""
    if not records:
        return []
    ordered = sorted(records, key=lambda r: (-float(r["n"]), float(r["kw"]), int(r["zr"])))
    clusters: list[list[dict]] = []
    for rec in ordered:
        placed = False
        for cluster in clusters:
            # Representative = registration-weighted mean of current cluster kW
            tw = sum(float(r["n"]) for r in cluster) or 1.0
            mean_kw = sum(float(r["kw"]) * float(r["n"]) for r in cluster) / tw
            if abs(float(rec["kw"]) - mean_kw) <= KW_TOL_ABS:
                # Also require every member stays within ±5 of new mean
                trial = cluster + [rec]
                tw2 = sum(float(r["n"]) for r in trial) or 1.0
                mean2 = sum(float(r["kw"]) * float(r["n"]) for r in trial) / tw2
                if all(abs(float(r["kw"]) - mean2) <= KW_TOL_ABS for r in trial):
                    cluster.append(rec)
                    placed = True
                    break
        if not placed:
            clusters.append([rec])
    return clusters


def collect_groups_for_row(
    row: dict,
    index: dict,
) -> tuple[str, list[dict], set[str], int]:
    """
    Returns (result, groups, cn_raws, fp_conflicts_dropped).
    Each group dict: kw, awd, zr_min, zr_max, wh_min, wh_max, n, status, records.
    """
    rid = str(row.get("id") or "")
    if rid in TESLA_M3_2026_IDS:
        return "skip_protected", [], set(), 0

    year = int(row.get("year") or 0)
    brand = fill.brand_key_for_row(row)
    eea_keys = {mk for (mk, y) in index if y == year}
    matched = fill.bev_model_keys(str(row.get("model") or ""), eea_keys, brand)
    if not matched:
        return "no_cn", [], set(), 0

    all_cn: set[str] = set()
    tagged: list[dict] = []
    fp_conflicts = 0

    for mk in sorted(matched):
        if (mk, year) not in index:
            continue
        cell = index[(mk, year)]
        cn = set(cell.get("cn_raws") or [])
        all_cn |= cn
        awd = is_awd_hint(cn, mk)
        versions, n_conf = merge_fp_versions(cell)
        fp_conflicts += n_conf
        for v in versions:
            tagged.append({**v, "awd": awd, "eea_model_key": mk, "cn_raws": sorted(cn)})

    if not tagged:
        return "none_after_filters", [], all_cn, fp_conflicts

    # Dedupe identical (kw_r, zr, wh_r, awd) keeping max n (sum regs across keys).
    dedup: dict[tuple, dict] = {}
    for v in tagged:
        key = (
            int(round(float(v["kw"]))),
            int(v["zr"]),
            round(float(v["wh"]), 1),
            bool(v["awd"]),
        )
        prev = dedup.get(key)
        if prev is None:
            dedup[key] = dict(v)
        else:
            prev["n"] = float(prev["n"]) + float(v["n"])
            # Keep richer cn/key lists in records later via eea_records.

    # Registration threshold per atomic record before grouping.
    atoms = [v for v in dedup.values() if float(v["n"]) >= MIN_F_REGISTRATIONS]
    if not atoms:
        return "none_after_filters", [], all_cn, fp_conflicts

    groups: list[dict] = []
    for awd_flag in (False, True):
        subset = [a for a in atoms if bool(a["awd"]) == awd_flag]
        for cluster in cluster_by_kw(subset):
            tw = sum(float(r["n"]) for r in cluster) or 1.0
            mean_kw = sum(float(r["kw"]) * float(r["n"]) for r in cluster) / tw
            zrs = [int(r["zr"]) for r in cluster]
            whs = [float(r["wh"]) for r in cluster]
            # Prefer F if any
            statuses = {str(r.get("status")) for r in cluster}
            status = "F" if "F" in statuses else "P"
            eea_records = [
                {
                    "kw": round(float(r["kw"]), 1),
                    "wh_per_km": round(float(r["wh"]), 1),
                    "wltpRangeKm": int(r["zr"]),
                    "n": round(float(r["n"]), 1),
                    "status": r.get("status"),
                    "eea_model_key": r.get("eea_model_key"),
                    "awd": bool(r["awd"]),
                }
                for r in sorted(
                    cluster,
                    key=lambda r: (-float(r["n"]), int(r["zr"]), float(r["kw"])),
                )
            ]
            groups.append(
                {
                    "kw": mean_kw,
                    "awd": awd_flag,
                    "zr_min": min(zrs),
                    "zr_max": max(zrs),
                    "wh_min": min(whs),
                    "wh_max": max(whs),
                    "n": tw,
                    "status": status,
                    "eea_records": eea_records,
                }
            )

    if not groups:
        return "none_after_filters", [], all_cn, fp_conflicts

    # Deterministic: higher min range first, then kW, then AWD last.
    groups.sort(key=lambda g: (-int(g["zr_min"]), float(g["kw"]), not g["awd"]))
    return "ok", groups, all_cn, fp_conflicts


def build_child_row(
    parent: dict,
    group: dict,
    *,
    cn_raws: set[str],
) -> tuple[dict, dict]:
    kw = float(group["kw"])
    awd = bool(group["awd"])
    zr_min = int(group["zr_min"])
    zr_max = int(group["zr_max"])
    wh_min = float(group["wh_min"])
    wh_max = float(group["wh_max"])
    pid = str(parent["id"])
    child_id = version_id(pid, kw, awd)
    label = version_label(kw, awd)
    caption = range_caption(zr_min, zr_max)
    # Prudent calc pair: min range, max consumption.
    batt = oem_battery_matches(parent, kw, wh_max)

    child = dict(parent)
    child["id"] = child_id
    child["trim"] = label
    child["parentId"] = pid
    child["powerKw"] = round(kw, 1)
    child["energyConsumptionKWhPerKm"] = round(wh_max / 1000.0, 6)
    child["wltpConsumptionKWh100km"] = round(wh_max / 10.0, 2)
    child["wltpRangeKm"] = zr_min
    child["wltpRangeKmMax"] = zr_max
    child["energyConsumptionKWhPerKmMin"] = round(wh_min / 1000.0, 6)
    child["variantRangeCaption"] = caption
    child["usesPrudentVariantBounds"] = True
    child["batteryKWh"] = batt
    child["sourceName"] = "EEA co2cars EU Zr (variant group)"
    child["sourceUpdatedAt"] = datetime.now(timezone.utc).date().isoformat()
    child["confidenceScore"] = 0.85 if group.get("status") == "F" else 0.7

    ref = {
        "id": child_id,
        "parentId": pid,
        "brand": parent.get("brand"),
        "model": parent.get("model"),
        "year": parent.get("year"),
        "kw": round(kw, 1),
        "awd": awd,
        "wh_per_km": round(wh_max, 1),  # prudent (max) used in catalog calc
        "wh_per_km_min": round(wh_min, 1),
        "wh_per_km_max": round(wh_max, 1),
        "wltpRangeKm": zr_min,  # prudent (min)
        "wltpRangeKmMin": zr_min,
        "wltpRangeKmMax": zr_max,
        "status": group.get("status"),
        "registrations": round(float(group["n"]), 1),
        "countries": ["EU-wide"],
        "cn_raws": sorted(cn_raws),
        "label": label,
        "rangeCaption": caption,
        "awd_from_cn": awd,
        "batteryKWh": batt,
        "battery_source": "oem_verified_parent_match" if batt is not None else None,
        "commercial_name": None,
        "commercial_url": None,
        "source": "EEA co2cars EU Zr",
        "eea_records": group["eea_records"],
        "prudent": {"wltpRangeKm": zr_min, "wh_per_km": round(wh_max, 1)},
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
            f"seedVersion {NEW_SEED_VERSION}: BEV EEA EU version groups "
            f"(kW±{KW_TOL_ABS:g}+traction; Zr/Wh min–max; prudent minZr/maxWh; "
            f"min {MIN_F_REGISTRATIONS} regs; F/P conflict drops pair only; "
            "Tesla Model 3 2026 IT trims preserved)."
        ),
    }
    payload = json.dumps(
        [{k: v for k, v in r.items() if v is not None} for r in rows],
        separators=(",", ":"),
        ensure_ascii=False,
    )
    meta["bytes"] = len(payload.encode("utf-8"))
    meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")


def distribution(counts: list[int]) -> dict[str, int]:
    c = Counter(counts)
    return {str(k): int(c[k]) for k in sorted(c)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    rows: list[dict] = json.loads(eea.SEED_PATH.read_text(encoding="utf-8"))
    rows = [r for r in rows if not r.get("parentId")]
    # Drop previous group-only fields if re-run on dirty parents.
    for r in rows:
        for k in (
            "wltpRangeKmMax",
            "energyConsumptionKWhPerKmMin",
            "variantRangeCaption",
            "usesPrudentVariantBounds",
        ):
            r.pop(k, None)

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
    existing_ids = {str(r["id"]) for r in rows}
    groups_per_parent: list[int] = []

    for parent in bev:
        pid = str(parent["id"])
        brand = fill.brand_key_for_row(parent)
        result, groups, cn_raws, fp_drop = collect_groups_for_row(
            parent, indexes[brand]
        )
        stats[result] += 1
        stats["fp_pair_conflicts_dropped"] += fp_drop

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

        built: list[tuple[dict, dict]] = []
        for group in groups:
            child, ref = build_child_row(parent, group, cn_raws=cn_raws)
            if child["id"] in existing_ids or any(
                c["id"] == child["id"] for c, _ in built
            ):
                # Collision: disambiguate with zr_min.
                child["id"] = f"{child['id']}-{int(group['zr_min'])}km"
                ref["id"] = child["id"]
                if child["id"] in existing_ids or any(
                    c["id"] == child["id"] for c, _ in built
                ):
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

        groups_per_parent.append(len(built))
        if len(built) == 1:
            child, ref = built[0]
            children.append(child)
            refs_variants.append(ref)
            single_alias[pid] = child["id"]
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

    out_rows: list[dict] = []
    cleared_set = set(cleared_parents)
    child_ids = {c["id"] for c in children}
    for r in rows:
        rid = str(r["id"])
        if rid in child_ids:
            continue
        row = dict(r)
        if rid in cleared_set:
            row["wltpRangeKm"] = None
        out_rows.append(row)
    out_rows.extend(children)

    after_bev_parents = [r for r in out_rows if r.get("powertrain") == "ev" and not r.get("parentId")]
    after_bev_all = [r for r in out_rows if r.get("powertrain") == "ev"]
    after_parents_with_range = sum(
        1 for r in after_bev_parents if r.get("wltpRangeKm")
    )
    # Model/year with autonomy = parents that keep range OR have ≥1 child with range.
    parents_with_child_range = {
        str(c["parentId"])
        for c in children
        if c.get("wltpRangeKm")
    }
    model_years_with_range_after = len(
        {
            str(r["id"])
            for r in after_bev_parents
            if r.get("wltpRangeKm") or str(r["id"]) in parents_with_child_range
        }
    )
    # Protected Tesla rows count as model/year with range even without parentId children.
    for tid in TESLA_M3_2026_IDS:
        # already in after_bev_parents
        pass

    dist = distribution(groups_per_parent)
    over8 = [
        {
            "parentId": pid,
            "n": n,
            "brand": next(
                (v["brand"] for v in refs_variants if v["parentId"] == pid), None
            ),
            "model": next(
                (v["model"] for v in refs_variants if v["parentId"] == pid), None
            ),
            "year": next(
                (v["year"] for v in refs_variants if v["parentId"] == pid), None
            ),
        }
        for pid, n in Counter(
            v["parentId"] for v in refs_variants
        ).most_common()
        if n > 8
    ]

    reason_counts = Counter(x["reason"] for x in no_variant_parents)

    refs = {
        "seedVersion": NEW_SEED_VERSION,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "source": "EEA co2cars EU field Zr (Electric range km)",
        "rules": [
            f"Min registrations per atomic EEA record: {MIN_F_REGISTRATIONS}",
            f"Version group = kW±{KW_TOL_ABS:g} + traction (AWD from Cn/key)",
            "Zr/Wh min–max from group EEA records only; calc uses min Zr + max Wh",
            "F preferred; P-only (kW,Zr) kept; F/P same (kW,Zr) different Wh → drop pair only",
            "Drop Zr == Wh/km on same record",
            f"Drop Wh/km outside [{WH_MIN:g}, {WH_MAX:g}]",
            "Label: '<kW> kW' (+ AWD); range caption separate",
            "batteryKWh nil unless OEM-verified parent pack matches",
            "Tesla Model 3 2026 IT trims preserved",
        ],
        "minRegistrations": MIN_F_REGISTRATIONS,
        "kwToleranceAbs": KW_TOL_ABS,
        "stats": {
            "bev_model_years_before": len(bev),
            "bev_model_years_with_range_before": before_with_range,
            "bev_model_years_after": len(after_bev_parents),
            "bev_model_years_with_range_after": model_years_with_range_after,
            "bev_rows_after_including_versions": len(after_bev_all),
            "variant_groups": len(children),
            "parents_single": stats["single"],
            "parents_multi": stats["multi"],
            "parents_no_variant": len(no_variant_parents),
            "no_variant_reasons": dict(sorted(reason_counts.items())),
            "catalog_rows_before": len(rows),
            "catalog_rows_after": len(out_rows),
            "groups_per_parent_distribution": dist,
            "parents_over_8_groups": len(over8),
            "fp_pair_conflicts_dropped": stats["fp_pair_conflicts_dropped"],
            **{f"result_{k}": v for k, v in stats.items() if k != "fp_pair_conflicts_dropped"},
        },
        "singleVersionAliases": single_alias,
        "clearedParentRangeIds": sorted(cleared_set),
        "variants": refs_variants,
        "noVariantParents": no_variant_parents,
        "parentsOver8Groups": over8,
    }

    top10 = sorted(
        (
            {
                "parentId": pid,
                "n": n,
                "brand": next(
                    (v["brand"] for v in refs_variants if v["parentId"] == pid),
                    None,
                ),
                "model": next(
                    (v["model"] for v in refs_variants if v["parentId"] == pid),
                    None,
                ),
                "year": next(
                    (v["year"] for v in refs_variants if v["parentId"] == pid),
                    None,
                ),
            }
            for pid, n in Counter(v["parentId"] for v in refs_variants).items()
        ),
        key=lambda x: -x["n"],
    )[:10]

    report = {
        "seedVersion": NEW_SEED_VERSION,
        "stats": refs["stats"],
        "topParentsByVariantCount": top10,
        "parentsOver8Groups": over8,
        "noVariantReasons": dict(sorted(reason_counts.items())),
    }

    print(json.dumps(refs["stats"], indent=2))
    print("top10", json.dumps(top10, indent=2))
    print(
        f"variant_groups={len(children)} catalog {len(rows)} → {len(out_rows)} "
        f"model/year range {before_with_range} → {model_years_with_range_after}"
    )

    if args.dry_run:
        print("dry-run: no write")
        return 0

    eea.SEED_PATH.write_text(
        json.dumps(out_rows, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    ALIAS_PATH.write_text(
        json.dumps(single_alias, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    bump_cdn(out_rows)
    REFS_PATH.write_text(json.dumps(refs, indent=2) + "\n", encoding="utf-8")
    FIXTURE_REFS.parent.mkdir(parents=True, exist_ok=True)
    batt = [v for v in refs_variants if v.get("batteryKWh") is not None][:10]
    multi = [v for v in refs_variants if (v.get("wltpRangeKmMax") or 0) > (v.get("wltpRangeKmMin") or 0)][:15]
    sample = refs_variants[:20] + batt + multi
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
        "kwToleranceAbs": KW_TOL_ABS,
        "stats": refs["stats"],
        "singleVersionAliases": single_alias,
        "clearedParentRangeIds": sorted(cleared_set),
        "variants": slim_variants,
        "noVariantParentsSample": no_variant_parents[:50],
        "noVariantParentsCount": len(no_variant_parents),
        "noVariantReasons": dict(sorted(reason_counts.items())),
        "topParentsByVariantCount": top10,
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
