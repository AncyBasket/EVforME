#!/usr/bin/env python3
"""
Fill BEV `wltpRangeKm` from EEA co2cars IT field `Zr` (Electric range km).

Rules (no invented numbers):
- Prefer Status F; use P only when F has no Zr for that model/year.
- Match Cn with the same brand aliases / model merge as fuel scripts.
- If multiple Zr values exist, disambiguate with catalog Wh/km and/or powerKw.
- If still ambiguous or year absent in EEA → leave nil (no other-year copy).
- Never average Zr values.

Writes:
  scripts/cache/eea/catalog_truth_range_refs.json
  updates seed + seedVersion 55 + catalog_cdn bytes

Usage:
  python3 scripts/fill_catalog_bev_range_from_eea.py
  python3 scripts/fill_catalog_bev_range_from_eea.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import fill_catalog_fuels_from_eea as eea

NEW_SEED_VERSION = 55
REFS_PATH = eea.CACHE_DIR / "catalog_truth_range_refs.json"
REPORT_PATH = eea.CACHE_DIR / "catalog_bev_range_fill_v55_report.json"
FIXTURE_REFS = eea.REPO / "EVforME?Tests" / "Fixtures" / "catalog_truth_range_refs.json"

# Extra Mk spellings for BEV brands not in BRAND_MK_ALIASES.
EXTRA_MK: dict[str, list[str]] = {
    "GENESIS": ["GENESIS"],
    "NIO": ["NIO"],
    "POLESTAR": ["POLESTAR"],
    "SMART": ["SMART"],
    "LUCID": ["LUCID"],
    "RIVIAN": ["RIVIAN"],
    "XPENG": ["XPENG"],
    "CHEVROLET": ["CHEVROLET"],
    "LEAPMOTOR": ["LEAPMOTOR"],
}

KW_TOL_ABS = 5.0
KW_TOL_REL = 0.03
WH_TOL = 1.0  # Wh/km integer match


def brand_key_for_row(row: dict) -> str:
    raw = str(row.get("brand") or "")
    mapped = eea.BRAND_TO_EEA_MK.get(raw.upper(), raw)
    return eea.canonical_ice_brand_key(mapped)


def mk_names_for_brand(brand_key: str) -> list[str]:
    key = brand_key.upper() if brand_key != "MERCEDES-BENZ" else "MERCEDES-BENZ"
    if key in eea.BRAND_MK_ALIASES:
        return list(eea.BRAND_MK_ALIASES[key])
    if key in EXTRA_MK:
        return list(EXTRA_MK[key])
    # fall back to aliases_for / bare name
    try:
        return eea.brand_aliases_for(brand_key)
    except Exception:
        return [brand_key]


def electric_range_payload(brand_key: str) -> dict:
    # Prefer shared alias clauses when the brand is in BRAND_MK_ALIASES.
    key_u = "MERCEDES-BENZ" if brand_key.upper().replace(" ", "-") == "MERCEDES-BENZ" else brand_key.upper()
    if key_u in eea.BRAND_MK_ALIASES or brand_key in eea.BRAND_MK_ALIASES:
        should = eea.brand_mk_should_clauses(brand_key if brand_key in eea.BRAND_MK_ALIASES else key_u)
    else:
        should = []
        names = mk_names_for_brand(brand_key)
        seen: set[str] = set()
        for name in names:
            for candidate in (name, name.title(), name.upper(), name.lower()):
                if candidate in seen:
                    continue
                seen.add(candidate)
                should.append({"term": {"Mk": candidate}})
                should.append({"wildcard": {"Mk": candidate + "*"}})
        token = re.sub(r"[^A-Z0-9]", "", brand_key.upper())[:12]
        if token:
            cn = {"bool": {"should": [{"wildcard": {"Cn": f"*{token}*"}}], "minimum_should_match": 1}}
            should.append({"bool": {"must": [{"term": {"Mk": ""}}, cn]}})
            should.append(
                {"bool": {"must": [{"bool": {"must_not": [{"exists": {"field": "Mk"}}]}}, cn]}}
            )
    return {
        "size": 0,
        "query": {
            "bool": {
                "must": [
                    {"term": {"MS": "IT"}},
                    {"bool": {"should": should, "minimum_should_match": 1}},
                    {"range": {"year": {"gte": 2017, "lte": 2025}}},
                    {
                        "bool": {
                            "should": [
                                {"term": {"Ft": "ELECTRIC"}},
                                {"term": {"Ft": "electric"}},
                                {"term": {"Ft": "Electric"}},
                            ],
                            "minimum_should_match": 1,
                        }
                    },
                    {"exists": {"field": "Zr"}},
                ]
            }
        },
        "aggs": {
            "models": {
                "terms": {"field": "Cn", "size": 1500},
                "aggs": {
                    "years": {
                        "terms": {"field": "year", "size": 20},
                        "aggs": {
                            "status": {
                                "terms": {"field": "Status", "size": 5},
                                "aggs": {
                                    "zr": {
                                        "terms": {"field": "Zr", "size": 40},
                                        "aggs": {
                                            "sum_r": {"sum": {"field": "r"}},
                                            "wh": {
                                                "terms": {"field": "z__Wh_km_", "size": 20},
                                                "aggs": {"sum_r": {"sum": {"field": "r"}}},
                                            },
                                            "kw": {
                                                "terms": {"field": "ep__KW_", "size": 20},
                                                "aggs": {"sum_r": {"sum": {"field": "r"}}},
                                            },
                                        },
                                    }
                                },
                            }
                        },
                    }
                },
            }
        },
    }


def cache_name(brand_key: str) -> str:
    safe = brand_key.replace(" ", "_")
    return f"IT_{safe}_bev_Zr"


def load_brand_zr(brand_key: str, *, use_cache: bool) -> dict:
    return eea.load_or_fetch(
        cache_name(brand_key),
        electric_range_payload(brand_key),
        use_cache=use_cache,
    )


def parse_zr_index(wrap: dict, brand_key: str) -> dict[tuple[str, int], dict]:
    """
    (model_merge_key, year) → {
      'F': {zr: {n, whs: {wh: n}, kws: {kw: n}}},
      'P': {...},
      'cn_raws': set
    }
    """
    resp = wrap.get("response", wrap)
    out: dict[tuple[str, int], dict] = {}
    for mb in resp.get("aggregations", {}).get("models", {}).get("buckets", []) or []:
        cn_raw = str(mb.get("key") or "")
        if not eea.model_accepted_for_brand(cn_raw, brand_key):
            # model_accepted may be strict for JLR etc.; for pure BEV brands allow all
            if brand_key in {"JAGUAR", "LAND ROVER", "ALFA ROMEO", "JEEP"}:
                continue
        merge = eea.model_name_merge_key(cn_raw, brand_key) or eea.norm_alnum(cn_raw)
        if not merge:
            continue
        for yb in mb.get("years", {}).get("buckets", []) or []:
            year = int(yb.get("key"))
            cell = out.setdefault((merge, year), {"F": {}, "P": {}, "cn_raws": set()})
            cell["cn_raws"].add(cn_raw)
            for sb in yb.get("status", {}).get("buckets", []) or []:
                status = str(sb.get("key") or "").upper()
                if status not in {"F", "P"}:
                    continue
                bucket = cell[status]
                for zb in sb.get("zr", {}).get("buckets", []) or []:
                    try:
                        zr = int(zb.get("key"))
                    except (TypeError, ValueError):
                        continue
                    if zr <= 0:
                        continue
                    n = float((zb.get("sum_r") or {}).get("value") or zb.get("doc_count") or 0)
                    entry = bucket.setdefault(zr, {"n": 0.0, "whs": defaultdict(float), "kws": defaultdict(float)})
                    entry["n"] += n
                    for whb in zb.get("wh", {}).get("buckets", []) or []:
                        try:
                            wh = float(whb.get("key"))
                        except (TypeError, ValueError):
                            continue
                        entry["whs"][wh] += float((whb.get("sum_r") or {}).get("value") or 0)
                    for kwb in zb.get("kw", {}).get("buckets", []) or []:
                        try:
                            kw = float(kwb.get("key"))
                        except (TypeError, ValueError):
                            continue
                        entry["kws"][kw] += float((kwb.get("sum_r") or {}).get("value") or 0)
    return out


def preferred_status_map(cell: dict) -> tuple[str, dict]:
    """Return (status, zr_map) preferring F when it has any Zr."""
    if cell.get("F"):
        return "F", cell["F"]
    return "P", cell.get("P") or {}


def kw_matches(catalog_kw: float, eea_kw: float) -> bool:
    if catalog_kw <= 0 or eea_kw <= 0:
        return False
    if abs(catalog_kw - eea_kw) <= KW_TOL_ABS:
        return True
    return abs(catalog_kw - eea_kw) / catalog_kw <= KW_TOL_REL


def wh_matches(catalog_wh: float, eea_wh: float) -> bool:
    return abs(catalog_wh - eea_wh) <= WH_TOL


def bev_model_keys(seed_model: str, eea_keys: set[str], brand_key: str) -> list[str]:
    """
    Exact Cn merge-key first; else family of trim keys that share the seed prefix
    (e.g. ID.3 → ID3PRO150KW / ID3PURE110KW; i4 → I4EDRIVE40 / I4M50).
    Never invent a key; empty list means no EEA Cn for this year.
    """
    seed_merge = eea.model_name_merge_key(seed_model, brand_key) or eea.norm_alnum(seed_model)
    sn = eea.clean_model_norm(seed_model) or eea.norm_alnum(seed_model)
    for cand in (seed_merge, sn):
        if cand and cand in eea_keys:
            return [cand]

    family: set[str] = set()
    for cand in (seed_merge, sn):
        if not cand or len(cand) < 2:
            continue
        for em in eea_keys:
            if em == cand:
                family.add(em)
            elif em.startswith(cand):
                rest = em[len(cand) :]
                # Trim/power suffix must start with a letter (I4→I4EDRIVE40; IX↛IX3).
                if rest and rest[0].isalpha():
                    family.add(em)
    if family:
        return sorted(family)

    fuzzy = eea.match_model(seed_model, eea_keys, for_ice=False)
    return [fuzzy] if fuzzy else []


def merge_cells(cells: list[dict]) -> dict:
    """Union F/P Zr maps and cn_raws across family Cn keys for one year."""
    out: dict = {"F": {}, "P": {}, "cn_raws": set()}
    for cell in cells:
        out["cn_raws"] |= set(cell.get("cn_raws") or [])
        for status in ("F", "P"):
            for zr, meta in (cell.get(status) or {}).items():
                dest = out[status].setdefault(
                    zr, {"n": 0.0, "whs": defaultdict(float), "kws": defaultdict(float)}
                )
                dest["n"] += float(meta.get("n") or 0)
                for wh, n in (meta.get("whs") or {}).items():
                    dest["whs"][wh] += float(n)
                for kw, n in (meta.get("kws") or {}).items():
                    dest["kws"][kw] += float(n)
    return out


def resolve_zr_for_row(
    row: dict,
    index: dict[tuple[str, int], dict],
    brand_key: str,
) -> dict | None:
    year = int(row.get("year") or 0)
    if year < 2017 or year > 2025:
        return {
            "id": row.get("id"),
            "result": "skip",
            "reason": f"year {year} outside EEA IT Zr window 2017–2025",
        }

    model_raw = str(row.get("model") or "")
    eea_keys = {mk for (mk, y) in index if y == year}
    matched_keys = bev_model_keys(model_raw, eea_keys, brand_key)
    if not matched_keys:
        return {
            "id": row.get("id"),
            "result": "skip",
            "reason": "no EEA Cn match for model/year",
            "model": model_raw,
            "year": year,
        }

    cells = [index[(mk, year)] for mk in matched_keys if (mk, year) in index]
    if not cells:
        return {
            "id": row.get("id"),
            "result": "skip",
            "reason": "matched key missing in index",
            "eea_model": matched_keys[0],
            "year": year,
        }

    cell = merge_cells(cells) if len(cells) > 1 else cells[0]
    status, zr_map = preferred_status_map(cell)
    if not zr_map:
        return {
            "id": row.get("id"),
            "result": "skip",
            "reason": "no Zr under preferred Status",
            "eea_model": ",".join(matched_keys),
            "year": year,
            "status": status,
        }

    candidates = dict(zr_map)
    energy = row.get("energyConsumptionKWhPerKm")
    catalog_wh = float(energy) * 1000.0 if energy and float(energy) > 0 else None
    catalog_kw = float(row["powerKw"]) if row.get("powerKw") not in (None, "", 0) else None
    eea_model_label = matched_keys[0] if len(matched_keys) == 1 else ",".join(matched_keys)

    # Unique Zr for this model/year → take it (Wh/kW only for disambiguation).
    if len(candidates) == 1:
        zr = next(iter(candidates))
        meta = candidates[zr]
        return {
            "id": row["id"],
            "result": "fill",
            "wltpRangeKm": int(zr),
            "eea_brand": brand_key,
            "eea_model": eea_model_label,
            "eea_cn_raws": sorted(cell.get("cn_raws") or []),
            "eea_year": year,
            "status": status,
            "n": meta.get("n"),
            "catalog_wh": catalog_wh,
            "catalog_kw": catalog_kw,
            "source": "EEA co2cars IT Zr",
            "fetched_note": "Status F preferred; P only if F has no Zr for this Cn/year",
        }

    # Disambiguate: power first (user rule), then Wh/km. Never hard-fail on a miss —
    # only narrow when the filter still leaves ≥1 candidate.
    if catalog_kw is not None:
        kw_filtered = {
            zr: meta
            for zr, meta in candidates.items()
            if any(kw_matches(catalog_kw, float(kw)) for kw in (meta.get("kws") or {}))
        }
        if kw_filtered:
            candidates = kw_filtered

    if len(candidates) > 1 and catalog_wh is not None:
        wh_filtered = {
            zr: meta
            for zr, meta in candidates.items()
            if any(wh_matches(catalog_wh, float(wh)) for wh in (meta.get("whs") or {}))
        }
        if wh_filtered:
            candidates = wh_filtered

    if len(candidates) != 1:
        return {
            "id": row.get("id"),
            "result": "skip",
            "reason": "ambiguous Zr (multiple versions; cannot uniquely match)",
            "eea_model": eea_model_label,
            "year": year,
            "status": status,
            "candidate_zr": sorted(candidates.keys()),
            "cn_raws": sorted(cell.get("cn_raws") or []),
            "catalog_wh": catalog_wh,
            "catalog_kw": catalog_kw,
        }

    zr = next(iter(candidates))
    meta = candidates[zr]
    return {
        "id": row["id"],
        "result": "fill",
        "wltpRangeKm": int(zr),
        "eea_brand": brand_key,
        "eea_model": eea_model_label,
        "eea_cn_raws": sorted(cell.get("cn_raws") or []),
        "eea_year": year,
        "status": status,
        "n": meta.get("n"),
        "catalog_wh": catalog_wh,
        "catalog_kw": catalog_kw,
        "source": "EEA co2cars IT Zr",
        "fetched_note": "Status F preferred; P only if F has no Zr for this Cn/year",
    }


def bump_metadata(rows: list[dict]) -> None:
    eea.bump_seed_version(NEW_SEED_VERSION)
    raw = eea.SEED_PATH.read_bytes()
    cdn = json.loads(eea.CDN_PATH.read_text(encoding="utf-8"))
    cdn["seedVersion"] = NEW_SEED_VERSION
    cdn["rows"] = len(rows)
    cdn["bytes"] = len(raw)
    cdn["updatedAt"] = datetime.now(timezone.utc).isoformat()
    cdn["note"] = (
        f"seedVersion {NEW_SEED_VERSION}: BEV wltpRangeKm from EEA IT Zr "
        "(F preferred; unique match via Cn + Wh/km and/or kW; no averages)."
    )
    eea.CDN_PATH.write_text(json.dumps(cdn, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--refresh", action="store_true", help="re-fetch brand Zr caches")
    args = ap.parse_args()

    rows: list[dict] = json.loads(eea.SEED_PATH.read_text(encoding="utf-8"))
    missing = [r for r in rows if r.get("powertrain") == "ev" and not r.get("wltpRangeKm")]
    before_with = sum(1 for r in rows if r.get("powertrain") == "ev" and r.get("wltpRangeKm"))
    before_total = sum(1 for r in rows if r.get("powertrain") == "ev")

    by_brand: dict[str, list[dict]] = defaultdict(list)
    for r in missing:
        by_brand[brand_key_for_row(r)].append(r)

    fills: list[dict] = []
    skips: list[dict] = []
    indexes: dict[str, dict] = {}
    fetched_at: dict[str, str] = {}

    for i, brand_key in enumerate(sorted(by_brand)):
        print(f"[{i+1}/{len(by_brand)}] Zr cache {brand_key}…", flush=True)
        wrap = load_brand_zr(brand_key, use_cache=not args.refresh)
        indexes[brand_key] = parse_zr_index(wrap, brand_key)
        fetched_at[brand_key] = str(wrap.get("_fetched_at") or "")
        time.sleep(0.15)

    for brand_key, brand_rows in by_brand.items():
        index = indexes.get(brand_key) or {}
        for r in brand_rows:
            decision = resolve_zr_for_row(r, index, brand_key)
            if not decision:
                continue
            if decision.get("result") == "fill":
                decision["eea_data_fetched_at"] = fetched_at.get(brand_key) or None
                fills.append(decision)
            else:
                skips.append(decision)

    if not args.dry_run:
        by_id = {d["id"]: d for d in fills}
        changed = 0
        for r in rows:
            d = by_id.get(r.get("id"))
            if not d:
                continue
            r["wltpRangeKm"] = int(d["wltpRangeKm"])
            changed += 1
        eea.SEED_PATH.write_text(
            json.dumps(rows, ensure_ascii=False, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
        bump_metadata(rows)
        refs = {
            "seedVersion": NEW_SEED_VERSION,
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            "source": "EEA co2cars IT field Zr (Electric range km)",
            "rules": [
                "Status F preferred; P only if F has no Zr",
                "Cn match via fill_catalog_fuels_from_eea.match_model / merge keys",
                "Disambiguate multi-Zr with catalog Wh/km then powerKw",
                "Never average; leave nil if ambiguous or year outside 2017–2025",
            ],
            "fills": fills,
            "skips": skips,
        }
        eea.CACHE_DIR.mkdir(parents=True, exist_ok=True)
        REFS_PATH.write_text(json.dumps(refs, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if FIXTURE_REFS.parent.is_dir():
            FIXTURE_REFS.write_text(json.dumps(refs, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    after_rows = rows if not args.dry_run else [
        {**r, "wltpRangeKm": next((f["wltpRangeKm"] for f in fills if f["id"] == r["id"]), r.get("wltpRangeKm"))}
        for r in rows
    ]
    after_with = sum(1 for r in after_rows if r.get("powertrain") == "ev" and r.get("wltpRangeKm"))
    report = {
        "dry_run": args.dry_run,
        "seedVersion": NEW_SEED_VERSION,
        "bev_total": before_total,
        "with_range_before": before_with,
        "with_range_after": after_with,
        "filled": len(fills),
        "skipped": len(skips),
        "skip_reasons": {},
        "examples": {
            "tesla-model-3-2026": next((s for s in skips + fills if s.get("id") == "tesla-model-3-2026"), None),
            "tesla-model-3-2025": next((s for s in skips + fills if s.get("id") == "tesla-model-3-2025"), None),
            "tesla-model-3-2024": next((s for s in skips + fills if s.get("id") == "tesla-model-3-2024"), None),
        },
        "fill_sample": fills[:30],
    }
    for s in skips:
        reason = s.get("reason") or "unknown"
        report["skip_reasons"][reason] = report["skip_reasons"].get(reason, 0) + 1

    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"BEV {before_total}: with_range {before_with}→{after_with} "
        f"filled={len(fills)} skipped={len(skips)} dry={args.dry_run}"
    )
    print("skip_reasons", report["skip_reasons"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
