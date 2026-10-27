#!/usr/bin/env python3
"""
Build BEV catalog versions from EEA co2cars EU-wide Zr (Electric range km).

Rules (no invented numbers):
- Source: EU Zr caches (same brand/model matching as check_catalog_existence /
  fill_catalog_bev_range_from_eea).
- Exclusive matching: sport/longer catalog siblings do not share EEA records
  with the base model. Sport trim without own Cn → at most 1 group if an EEA
  record kW matches an official OEM power (±5); else 0 groups.
- Version GROUP = same power cluster (kW ±5) + same traction.
- Noise: keep group only if n ≥ 2% of parent total OR n ≥ 200.
- Official kW audit for top-30 BEV MY + parents with >6 groups.
- Zr/Wh min–max from group EEA records only; calc = min Zr + max Wh.
- Tesla Model 3 2026 official IT trims: untouched.
- seedVersion → 60.

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

NEW_SEED_VERSION = 60
MIN_F_REGISTRATIONS = 10
KW_TOL_ABS = 5.0
WH_TOL = 1.0
WH_MIN = 90.0
WH_MAX = 350.0
MIN_SHARE_OF_PARENT = 0.02
MIN_ABS_REGISTRATIONS = 200.0

REFS_PATH = eea.CACHE_DIR / "catalog_truth_ev_variants_refs.json"
FIXTURE_REFS = eea.REPO / "EVforME?Tests" / "Fixtures" / "catalog_truth_ev_variants_refs.json"
REPORT_PATH = eea.CACHE_DIR / "catalog_ev_variants_build_report.json"
ALIAS_PATH = eea.REPO / "EVforME?" / "Data" / "ev_variant_single_aliases.json"
OFFICIAL_KW_PATH = SCRIPT_DIR / "ev_variant_official_kw.json"

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


def load_official_kw() -> dict:
    if not OFFICIAL_KW_PATH.exists():
        return {"byParentId": {}}
    return json.loads(OFFICIAL_KW_PATH.read_text(encoding="utf-8"))


def official_entry(official: dict, parent_id: str) -> dict | None:
    return (official.get("byParentId") or {}).get(parent_id)


def kw_matches_official(kw: float, powers: list[float]) -> bool:
    return any(abs(float(kw) - float(p)) <= KW_TOL_ABS for p in powers)


def merge_key_for_row(row: dict) -> str:
    brand = fill.brand_key_for_row(row)
    model = str(row.get("model") or "")
    return eea.model_name_merge_key(model, brand) or eea.norm_alnum(model)


def bev_model_keys_strict(seed_model: str, eea_keys: set[str], brand_key: str) -> list[str]:
    """
    Like fill.bev_model_keys but never fuzzy-falls onto a shorter base Cn when
    the seed merge key is longer (Ioniq 5 N must not absorb IONIQ5).
    """
    seed_merge = eea.model_name_merge_key(seed_model, brand_key) or eea.norm_alnum(
        seed_model
    )
    sn = eea.clean_model_norm(seed_model) or eea.norm_alnum(seed_model)
    seeds: list[str] = []
    for cand in (seed_merge, sn):
        if cand and cand not in seeds:
            seeds.append(cand)

    family: set[str] = set()
    for cand in seeds:
        for em in sorted(eea_keys):
            if fill.is_same_model_variant(cand, em):
                family.add(em)
    if family:
        return sorted(family)

    fuzzy = eea.match_model(seed_model, eea_keys, for_ice=False)
    if not fuzzy or fuzzy not in eea_keys:
        return []
    # Reject shorter base absorption (IONIQ5N → IONIQ5).
    for cand in seeds:
        if cand.startswith(fuzzy) and len(cand) > len(fuzzy):
            return []
    expanded: set[str] = set()
    for em in sorted(eea_keys):
        if fill.is_same_model_variant(fuzzy, em) or fill.is_same_model_variant(em, fuzzy):
            expanded.add(em)
        for cand in seeds:
            if fill.is_same_model_variant(cand, em):
                expanded.add(em)
    return sorted(expanded) if expanded else [fuzzy]


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


def record_fingerprint(rec: dict, year: int | None = None) -> tuple:
    y = int(year if year is not None else rec.get("year") or 0)
    return (
        y,
        str(rec.get("eea_model_key") or ""),
        round(float(rec["kw"]), 1),
        round(float(rec["wh"]), 1),
        int(rec["zr"]),
        bool(rec.get("awd")),
        str(rec.get("status") or ""),
    )


def cluster_by_kw(records: list[dict]) -> list[list[dict]]:
    if not records:
        return []
    ordered = sorted(records, key=lambda r: (-float(r["n"]), float(r["kw"]), int(r["zr"])))
    clusters: list[list[dict]] = []
    for rec in ordered:
        placed = False
        for cluster in clusters:
            tw = sum(float(r["n"]) for r in cluster) or 1.0
            mean_kw = sum(float(r["kw"]) * float(r["n"]) for r in cluster) / tw
            if abs(float(rec["kw"]) - mean_kw) <= KW_TOL_ABS:
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


def atoms_from_matched_keys(
    matched: list[str],
    year: int,
    index: dict,
    *,
    exclude_fps: set[tuple] | None = None,
) -> tuple[list[dict], set[str], int]:
    exclude_fps = exclude_fps or set()
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
            tagged.append(
                {
                    **v,
                    "awd": awd,
                    "eea_model_key": mk,
                    "cn_raws": sorted(cn),
                    "year": year,
                }
            )

    dedup: dict[tuple, dict] = {}
    for v in tagged:
        key = (
            int(year),
            int(round(float(v["kw"]))),
            int(v["zr"]),
            round(float(v["wh"]), 1),
            bool(v["awd"]),
            str(v.get("eea_model_key") or ""),
            str(v.get("status") or ""),
        )
        prev = dedup.get(key)
        if prev is None:
            dedup[key] = dict(v)
        else:
            prev["n"] = float(prev["n"]) + float(v["n"])

    atoms: list[dict] = []
    for v in dedup.values():
        if float(v["n"]) < MIN_F_REGISTRATIONS:
            continue
        fp = record_fingerprint(v, year)
        if fp in exclude_fps:
            continue
        atoms.append(v)
    return atoms, all_cn, fp_conflicts


def groups_from_atoms(atoms: list[dict], year: int) -> list[dict]:
    groups: list[dict] = []
    for awd_flag in (False, True):
        subset = [a for a in atoms if bool(a["awd"]) == awd_flag]
        for cluster in cluster_by_kw(subset):
            tw = sum(float(r["n"]) for r in cluster) or 1.0
            mean_kw = sum(float(r["kw"]) * float(r["n"]) for r in cluster) / tw
            zrs = [int(r["zr"]) for r in cluster]
            whs = [float(r["wh"]) for r in cluster]
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
                    "year": int(r.get("year") or year),
                    "fingerprint": list(record_fingerprint(r, year)),
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
                    "fingerprints": [record_fingerprint(r, year) for r in cluster],
                }
            )
    groups.sort(key=lambda g: (-int(g["zr_min"]), float(g["kw"]), not g["awd"]))
    return groups


def apply_noise_filter(groups: list[dict]) -> tuple[list[dict], list[dict]]:
    total = sum(float(g["n"]) for g in groups) or 0.0
    kept: list[dict] = []
    dropped: list[dict] = []
    for g in groups:
        n = float(g["n"])
        share = (n / total) if total > 0 else 0.0
        if n >= MIN_ABS_REGISTRATIONS or share >= MIN_SHARE_OF_PARENT:
            kept.append(g)
        else:
            dropped.append(
                {
                    "kw": round(float(g["kw"]), 1),
                    "awd": bool(g["awd"]),
                    "n": round(n, 1),
                    "share": round(share, 4),
                    "reason": "below_registration_threshold",
                }
            )
    return kept, dropped


def sibling_map(bev: list[dict]) -> dict[str, dict]:
    """parentId → {base_id, sport_ids, merge_key, is_sport}."""
    by_by: dict[tuple[str, int], list[tuple[str, str, dict]]] = defaultdict(list)
    for r in bev:
        brand = fill.brand_key_for_row(r)
        year = int(r.get("year") or 0)
        mk = merge_key_for_row(r)
        by_by[(brand, year)].append((mk, str(r["id"]), r))

    info: dict[str, dict] = {}
    for (_b, _y), items in by_by.items():
        items = sorted(items, key=lambda x: len(x[0]))
        for i, (mk1, id1, _r1) in enumerate(items):
            sports = []
            for mk2, id2, _r2 in items[i + 1 :]:
                if mk2.startswith(mk1) and len(mk2) > len(mk1) and len(mk1) >= 4:
                    sports.append(id2)
            info.setdefault(
                id1,
                {
                    "merge_key": mk1,
                    "base_id": None,
                    "sport_ids": sports,
                    "is_sport": False,
                },
            )
            info[id1]["sport_ids"] = sports
            for sid in sports:
                smk = next(mk for mk, iid, _ in items if iid == sid)
                info[sid] = {
                    "merge_key": smk,
                    "base_id": id1,
                    "sport_ids": [],
                    "is_sport": True,
                }
        for mk, iid, _r in items:
            info.setdefault(
                iid,
                {
                    "merge_key": mk,
                    "base_id": None,
                    "sport_ids": [],
                    "is_sport": False,
                },
            )
    return info


def collect_groups_for_row(
    row: dict,
    index: dict,
    *,
    exclude_fps: set[tuple] | None = None,
    strict: bool = True,
) -> tuple[str, list[dict], set[str], int]:
    rid = str(row.get("id") or "")
    if rid in TESLA_M3_2026_IDS:
        return "skip_protected", [], set(), 0

    year = int(row.get("year") or 0)
    brand = fill.brand_key_for_row(row)
    eea_keys = {mk for (mk, y) in index if y == year}
    model = str(row.get("model") or "")
    if strict:
        matched = bev_model_keys_strict(model, eea_keys, brand)
    else:
        matched = fill.bev_model_keys(model, eea_keys, brand)
    if not matched:
        return "no_cn", [], set(), 0

    atoms, all_cn, fp_conflicts = atoms_from_matched_keys(
        matched, year, index, exclude_fps=exclude_fps
    )
    if not atoms:
        return "none_after_filters", [], all_cn, fp_conflicts
    groups = groups_from_atoms(atoms, year)
    if not groups:
        return "none_after_filters", [], all_cn, fp_conflicts
    return "ok", groups, all_cn, fp_conflicts


def sport_rule_b_group(
    parent: dict,
    base_row: dict,
    index: dict,
    official: dict,
    claimed: set[tuple],
) -> tuple[str, list[dict], set[str], int, dict]:
    """
    At most one group from base EEA atoms whose kW matches official OEM power.
    Returns (result, groups, cn, fp_drop, outcome_meta).
    """
    pid = str(parent["id"])
    entry = official_entry(official, pid)
    meta = {
        "parentId": pid,
        "baseId": str(base_row["id"]),
        "outcome": "zero",
        "reason": "",
        "official_url": None,
        "official_powers_kw": [],
        "matched_kw": None,
    }
    if not entry:
        meta["reason"] = "no_official_source"
        return "no_cn", [], set(), 0, meta

    powers = [float(x) for x in (entry.get("powers_kw") or [])]
    meta["official_url"] = entry.get("url")
    meta["official_powers_kw"] = powers
    if not powers:
        meta["reason"] = "empty_official_powers"
        return "no_cn", [], set(), 0, meta

    year = int(base_row.get("year") or 0)
    brand = fill.brand_key_for_row(base_row)
    eea_keys = {mk for (mk, y) in index if y == year}
    matched = bev_model_keys_strict(str(base_row.get("model") or ""), eea_keys, brand)
    if not matched:
        # Base may use non-strict historically; still try strict-or-fill for pool.
        matched = fill.bev_model_keys(str(base_row.get("model") or ""), eea_keys, brand)
    atoms, all_cn, fp_drop = atoms_from_matched_keys(
        matched, year, index, exclude_fps=claimed
    )
    candidates = [a for a in atoms if kw_matches_official(float(a["kw"]), powers)]
    if not candidates:
        meta["reason"] = "no_eea_kw_within_tol_of_official"
        return "none_after_filters", [], all_cn, fp_drop, meta

    # Prefer highest n among official-matching atoms; one cluster only.
    candidates.sort(key=lambda a: (-float(a["n"]), float(a["kw"])))
    # Take all candidates that fall in the same kW±5 cluster as the top one.
    top = candidates[0]
    cluster = [
        a
        for a in candidates
        if abs(float(a["kw"]) - float(top["kw"])) <= KW_TOL_ABS
        and bool(a["awd"]) == bool(top["awd"])
    ]
    groups = groups_from_atoms(cluster, year)
    if not groups:
        meta["reason"] = "cluster_empty"
        return "none_after_filters", [], all_cn, fp_drop, meta
    # Force at most one group (highest n).
    groups = sorted(groups, key=lambda g: -float(g["n"]))[:1]
    meta["outcome"] = "one"
    meta["matched_kw"] = round(float(groups[0]["kw"]), 1)
    meta["reason"] = "official_kw_match"
    return "ok", groups, all_cn, fp_drop, meta


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
        "wh_per_km": round(wh_max, 1),
        "wh_per_km_min": round(wh_min, 1),
        "wh_per_km_max": round(wh_max, 1),
        "wltpRangeKm": zr_min,
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
            f"(exclusive Cn; noise ≥{MIN_SHARE_OF_PARENT:.0%}/≥{int(MIN_ABS_REGISTRATIONS)}; "
            f"official kW audit; kW±{KW_TOL_ABS:g}+traction; prudent minZr/maxWh; "
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

    official = load_official_kw()
    raw_rows: list[dict] = json.loads(eea.SEED_PATH.read_text(encoding="utf-8"))
    # Model/year with autonomy BEFORE this rebuild (parents or existing children).
    old_children = [r for r in raw_rows if r.get("parentId") and r.get("powertrain") == "ev"]
    old_parents = [
        r for r in raw_rows if r.get("powertrain") == "ev" and not r.get("parentId")
    ]
    old_child_parents = {
        str(c["parentId"]) for c in old_children if c.get("wltpRangeKm")
    }
    before_with_range = len(
        {
            str(r["id"])
            for r in old_parents
            if r.get("wltpRangeKm") or str(r["id"]) in old_child_parents
        }
    )
    before_variant_groups = len(old_children)

    rows = [r for r in raw_rows if not r.get("parentId")]
    for r in rows:
        for k in (
            "wltpRangeKmMax",
            "energyConsumptionKWhPerKmMin",
            "variantRangeCaption",
            "usesPrudentVariantBounds",
        ):
            r.pop(k, None)

    bev = [r for r in rows if r.get("powertrain") == "ev"]
    by_id = {str(r["id"]): r for r in bev}
    sib = sibling_map(bev)

    brands = sorted({fill.brand_key_for_row(r) for r in bev})
    indexes: dict[str, dict] = {}
    for i, brand in enumerate(brands):
        print(f"[{i+1}/{len(brands)}] EU Zr cache {brand}…", flush=True)
        wrap = existence.load_brand_zr_eu(brand, use_cache=True)
        indexes[brand] = fill.parse_zr_index(wrap, brand)

    # Claimed EEA fingerprints per (brand, year) so base/sport never share.
    claimed_by_by: dict[tuple[str, int], set[tuple]] = defaultdict(set)
    dual_claim_resolutions: list[dict] = []
    sport_outcomes: list[dict] = []
    discarded_groups: list[dict] = []
    unverified_official: list[dict] = []

    # Process order: sport siblings first (longest merge key), then others.
    ordered = sorted(
        bev,
        key=lambda r: (
            fill.brand_key_for_row(r),
            int(r.get("year") or 0),
            0 if sib.get(str(r["id"]), {}).get("is_sport") else 1,
            -len(sib.get(str(r["id"]), {}).get("merge_key") or ""),
            str(r["id"]),
        ),
    )

    parent_groups: dict[str, tuple[str, list[dict], set[str], int]] = {}
    stats: dict[str, int] = defaultdict(int)

    for parent in ordered:
        pid = str(parent["id"])
        brand = fill.brand_key_for_row(parent)
        year = int(parent.get("year") or 0)
        index = indexes[brand]
        claimed = claimed_by_by[(brand, year)]
        info = sib.get(pid, {})

        if info.get("is_sport"):
            # Pass 1: own Cn only (strict — no base absorption).
            result, groups, cn_raws, fp_drop = collect_groups_for_row(
                parent, index, exclude_fps=claimed, strict=True
            )
            stats["fp_pair_conflicts_dropped"] += fp_drop
            if result == "ok" and groups:
                dual_claim_resolutions.append(
                    {
                        "sportId": pid,
                        "baseId": info.get("base_id"),
                        "resolution": "own_cn_exclusive",
                        "n_groups": len(groups),
                    }
                )
                sport_outcomes.append(
                    {
                        "parentId": pid,
                        "baseId": info.get("base_id"),
                        "outcome": "one_or_more_own_cn",
                        "reason": "own_cn_exclusive",
                        "n_groups": len(groups),
                    }
                )
            elif info.get("base_id") and info["base_id"] in by_id:
                result, groups, cn_raws, fp_drop, meta = sport_rule_b_group(
                    parent, by_id[info["base_id"]], index, official, claimed
                )
                stats["fp_pair_conflicts_dropped"] += fp_drop
                sport_outcomes.append(meta)
                dual_claim_resolutions.append(
                    {
                        "sportId": pid,
                        "baseId": info.get("base_id"),
                        "resolution": "sport_rule_b",
                        "outcome": meta.get("outcome"),
                        "reason": meta.get("reason"),
                        "matched_kw": meta.get("matched_kw"),
                        "official_url": meta.get("official_url"),
                    }
                )
            else:
                result, groups, cn_raws = "no_cn", [], set()
                sport_outcomes.append(
                    {
                        "parentId": pid,
                        "outcome": "zero",
                        "reason": "sport_without_base_sibling",
                    }
                )
        else:
            result, groups, cn_raws, fp_drop = collect_groups_for_row(
                parent, index, exclude_fps=claimed, strict=True
            )
            stats["fp_pair_conflicts_dropped"] += fp_drop

        if result == "skip_protected":
            stats[result] += 1
            parent_groups[pid] = (result, [], set(), 0)
            continue

        if result != "ok" or not groups:
            stats[result] += 1
            parent_groups[pid] = (result, [], cn_raws, 0)
            continue

        # Noise filter
        kept, dropped = apply_noise_filter(groups)
        for d in dropped:
            discarded_groups.append({"parentId": pid, **d})
        if not kept:
            stats["none_after_noise"] += 1
            parent_groups[pid] = ("none_after_filters", [], cn_raws, 0)
            continue

        # Claim fingerprints so siblings cannot reuse.
        for g in kept:
            for fp in g.get("fingerprints") or []:
                claimed.add(tuple(fp) if not isinstance(fp, tuple) else fp)

        stats["ok"] += 1
        parent_groups[pid] = ("ok", kept, cn_raws, 0)

    # Official kW audit: top-30 by regs + parents with >6 groups + any curated OEM entry.
    parent_n = {
        pid: sum(float(g["n"]) for g in groups)
        for pid, (res, groups, _cn, _) in parent_groups.items()
        if res == "ok"
    }
    top30_ids = {
        pid for pid, _n in sorted(parent_n.items(), key=lambda x: -x[1])[:30]
    }
    over6_ids = {
        pid for pid, (res, groups, _cn, _) in parent_groups.items()
        if res == "ok" and len(groups) > 6
    }
    curated_ids = set((official.get("byParentId") or {}).keys())
    audit_ids = top30_ids | over6_ids | curated_ids

    for pid in sorted(audit_ids):
        res, groups, cn_raws, _ = parent_groups[pid]
        if res != "ok":
            continue
        entry = official_entry(official, pid)
        if not entry or not entry.get("powers_kw"):
            unverified_official.append(
                {
                    "parentId": pid,
                    "n_groups": len(groups),
                    "reason": "no_official_source",
                }
            )
            continue
        powers = [float(x) for x in entry["powers_kw"]]
        url = entry.get("url")
        kept: list[dict] = []
        for g in groups:
            if kw_matches_official(float(g["kw"]), powers):
                kept.append(g)
            else:
                discarded_groups.append(
                    {
                        "parentId": pid,
                        "kw": round(float(g["kw"]), 1),
                        "awd": bool(g["awd"]),
                        "n": round(float(g["n"]), 1),
                        "reason": "kw_not_on_official_sheet",
                        "official_url": url,
                    }
                )
        if not kept:
            stats["none_after_official_kw"] += 1
            parent_groups[pid] = ("none_after_filters", [], cn_raws, 0)
        else:
            parent_groups[pid] = ("ok", kept, cn_raws, 0)

    children: list[dict] = []
    refs_variants: list[dict] = []
    cleared_parents: list[str] = []
    single_alias: dict[str, str] = {}
    no_variant_parents: list[dict] = []
    existing_ids = {str(r["id"]) for r in rows}
    groups_per_parent: list[int] = []

    for parent in bev:
        pid = str(parent["id"])
        result, groups, cn_raws, _ = parent_groups.get(
            pid, ("no_cn", [], set(), 0)
        )
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
            if child["id"] in existing_ids or any(c["id"] == child["id"] for c, _ in built):
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

    after_bev_parents = [
        r for r in out_rows if r.get("powertrain") == "ev" and not r.get("parentId")
    ]
    after_bev_all = [r for r in out_rows if r.get("powertrain") == "ev"]
    parents_with_child_range = {
        str(c["parentId"]) for c in children if c.get("wltpRangeKm")
    }
    model_years_with_range_after = len(
        {
            str(r["id"])
            for r in after_bev_parents
            if r.get("wltpRangeKm") or str(r["id"]) in parents_with_child_range
        }
    )

    dist = distribution(groups_per_parent)
    over8 = [
        {
            "parentId": pid,
            "n": n,
            "brand": next((v["brand"] for v in refs_variants if v["parentId"] == pid), None),
            "model": next((v["model"] for v in refs_variants if v["parentId"] == pid), None),
            "year": next((v["year"] for v in refs_variants if v["parentId"] == pid), None),
        }
        for pid, n in Counter(v["parentId"] for v in refs_variants).most_common()
        if n > 8
    ]
    reason_counts = Counter(x["reason"] for x in no_variant_parents)

    top10 = sorted(
        (
            {
                "parentId": pid,
                "n": n,
                "brand": next((v["brand"] for v in refs_variants if v["parentId"] == pid), None),
                "model": next((v["model"] for v in refs_variants if v["parentId"] == pid), None),
                "year": next((v["year"] for v in refs_variants if v["parentId"] == pid), None),
                "group_kw": sorted(
                    {
                        round(float(v["kw"]), 1)
                        for v in refs_variants
                        if v["parentId"] == pid
                    }
                ),
                "official": official_entry(official, pid),
            }
            for pid, n in Counter(v["parentId"] for v in refs_variants).items()
        ),
        key=lambda x: -x["n"],
    )[:10]

    refs = {
        "seedVersion": NEW_SEED_VERSION,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "source": "EEA co2cars EU field Zr (Electric range km)",
        "rules": [
            f"Min registrations per atomic EEA record: {MIN_F_REGISTRATIONS}",
            f"Version group = kW±{KW_TOL_ABS:g} + traction (AWD from Cn/key)",
            "Exclusive Cn/records across base vs sport siblings; sport without Cn → rule B",
            f"Noise: keep if n≥{MIN_ABS_REGISTRATIONS:g} OR share≥{MIN_SHARE_OF_PARENT}",
            "Official kW audit for top-30 BEV MY + parents with >6 groups",
            "Zr/Wh min–max from group EEA records only; calc uses min Zr + max Wh",
            "F preferred; P-only (kW,Zr) kept; F/P Wh conflict drops pair only",
            "Tesla Model 3 2026 IT trims preserved",
        ],
        "minRegistrations": MIN_F_REGISTRATIONS,
        "minShareOfParent": MIN_SHARE_OF_PARENT,
        "minAbsoluteRegistrations": MIN_ABS_REGISTRATIONS,
        "kwToleranceAbs": KW_TOL_ABS,
        "stats": {
            "bev_model_years_before": len(bev),
            "bev_model_years_with_range_before": before_with_range,
            "bev_model_years_after": len(after_bev_parents),
            "bev_model_years_with_range_after": model_years_with_range_after,
            "bev_rows_after_including_versions": len(after_bev_all),
            "variant_groups": len(children),
            "variant_groups_before": before_variant_groups,
            "parents_single": stats["single"],
            "parents_multi": stats["multi"],
            "parents_no_variant": len(no_variant_parents),
            "no_variant_reasons": dict(sorted(reason_counts.items())),
            "catalog_rows_before": len(rows),
            "catalog_rows_after": len(out_rows),
            "groups_per_parent_distribution": dist,
            "parents_over_8_groups": len(over8),
            "fp_pair_conflicts_dropped": stats["fp_pair_conflicts_dropped"],
            **{
                f"result_{k}": v
                for k, v in stats.items()
                if k != "fp_pair_conflicts_dropped"
            },
        },
        "singleVersionAliases": single_alias,
        "clearedParentRangeIds": sorted(cleared_set),
        "variants": refs_variants,
        "noVariantParents": no_variant_parents,
        "parentsOver8Groups": over8,
        "discardedGroups": discarded_groups,
        "sportTrimOutcomes": sport_outcomes,
        "dualClaimResolutions": dual_claim_resolutions,
        "unverifiedOfficialKw": unverified_official,
    }

    report = {
        "seedVersion": NEW_SEED_VERSION,
        "stats": refs["stats"],
        "topParentsByVariantCount": top10,
        "parentsOver8Groups": over8,
        "noVariantReasons": dict(sorted(reason_counts.items())),
        "sportTrimOutcomes": sport_outcomes,
        "dualClaimResolutions": dual_claim_resolutions,
        "unverifiedOfficialKwCount": len(unverified_official),
        "discardedGroupsCount": len(discarded_groups),
    }

    print(json.dumps(refs["stats"], indent=2))
    print("top10", json.dumps(top10, indent=2))
    print("sport_outcomes", json.dumps(sport_outcomes, indent=2))
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
    multi = [
        v
        for v in refs_variants
        if (v.get("wltpRangeKmMax") or 0) > (v.get("wltpRangeKmMin") or 0)
    ][:15]
    focus_ids = {
        "hyundai-ioniq-5-n-2023",
        "dacia-spring-2023",
        "tesla-model-y-2023",
    }
    focus = [v for v in refs_variants if v.get("parentId") in focus_ids]
    sample = refs_variants[:20] + batt + multi + focus
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
        "minShareOfParent": MIN_SHARE_OF_PARENT,
        "minAbsoluteRegistrations": MIN_ABS_REGISTRATIONS,
        "kwToleranceAbs": KW_TOL_ABS,
        "stats": refs["stats"],
        "singleVersionAliases": single_alias,
        "clearedParentRangeIds": sorted(cleared_set),
        "variants": slim_variants,
        "noVariantParentsSample": no_variant_parents[:50],
        "noVariantParentsCount": len(no_variant_parents),
        "noVariantReasons": dict(sorted(reason_counts.items())),
        "topParentsByVariantCount": top10,
        "sportTrimOutcomes": sport_outcomes,
        "dualClaimResolutions": dual_claim_resolutions,
        "discardedGroupsSample": discarded_groups[:40],
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
