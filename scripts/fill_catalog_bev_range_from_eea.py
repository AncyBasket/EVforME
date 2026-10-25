#!/usr/bin/env python3
"""
Fill BEV `wltpRangeKm` from EEA co2cars IT field `Zr` (Electric range km).

Rules (no invented numbers):
- Prefer Status F; use P only when F has no Zr for that model/year.
- If F and P both exist with different Zr sets for the same Cn/year → leave nil.
- Match all EEA Cn variants of the same model (e-C4 / e-C4 X, …); never merge
  distinct models (Dolphin ≠ Dolphin Surf).
- When EEA has one or more Zr values: fill only if exactly one Zr remains after
  requiring a single EEA version (record) that matches catalog kW (±5) AND
  Wh/km (±1) jointly. Empty filter → nil (never skip a filter). Multiple Zr
  still matching → nil.
- Drop versions where Zr == Wh/km on the same record (misfiled consumption).
- Never average Zr values / copy other years.

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
WH_TOL = 1.0

# Suffixes that mean trim/body/power of the same model — not a different model name.
_VARIANT_SUFFIX_RE = re.compile(
    r"^(?:"
    r"X|GT|GTS|TURBO|TURBOS|S|R|PRO|PURE|PROS|PERFORMANCE|"
    r"CROSSCOUNTRY|CROSS|SPORTBACK|SPORT|COUPE|CABRIO|"
    r"EDRIVE\d*|XDRIVE\d*|M\d*|"
    r"4S|LONG|STANDARD|RWD|AWD|PLUS|"
    r"(?:PRO|PURE|PROS|PERFORMANCE)?\d*KW\d*"
    r")$",
    re.I,
)


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
    try:
        return eea.brand_aliases_for(brand_key)
    except Exception:
        return [brand_key]


def electric_range_payload(brand_key: str) -> dict:
    key_u = (
        "MERCEDES-BENZ"
        if brand_key.upper().replace(" ", "-") == "MERCEDES-BENZ"
        else brand_key.upper()
    )
    if key_u in eea.BRAND_MK_ALIASES or brand_key in eea.BRAND_MK_ALIASES:
        should = eea.brand_mk_should_clauses(
            brand_key if brand_key in eea.BRAND_MK_ALIASES else key_u
        )
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
            cn = {
                "bool": {
                    "should": [{"wildcard": {"Cn": f"*{token}*"}}],
                    "minimum_should_match": 1,
                }
            }
            should.append({"bool": {"must": [{"term": {"Mk": ""}}, cn]}})
            should.append(
                {
                    "bool": {
                        "must": [
                            {"bool": {"must_not": [{"exists": {"field": "Mk"}}]}},
                            cn,
                        ]
                    }
                }
            )
    # Nest kw under wh so each version is a joint (Zr, Wh, kW) record — never
    # combine Wh from one trim with kW from another under the same Zr.
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
                                                "terms": {
                                                    "field": "z__Wh_km_",
                                                    "size": 20,
                                                },
                                                "aggs": {
                                                    "sum_r": {"sum": {"field": "r"}},
                                                    "kw": {
                                                        "terms": {
                                                            "field": "ep__KW_",
                                                            "size": 20,
                                                        },
                                                        "aggs": {
                                                            "sum_r": {
                                                                "sum": {"field": "r"}
                                                            }
                                                        },
                                                    },
                                                },
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
      'F': {zr: {n, pairs: {(wh, kw): n}}},
      'P': {...},
      'cn_raws': set
    }
    """
    resp = wrap.get("response", wrap)
    out: dict[tuple[str, int], dict] = {}
    for mb in resp.get("aggregations", {}).get("models", {}).get("buckets", []) or []:
        cn_raw = str(mb.get("key") or "")
        if not eea.model_accepted_for_brand(cn_raw, brand_key):
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
                    n = float(
                        (zb.get("sum_r") or {}).get("value") or zb.get("doc_count") or 0
                    )
                    entry = bucket.setdefault(
                        zr, {"n": 0.0, "pairs": defaultdict(float)}
                    )
                    entry["n"] += n
                    for whb in zb.get("wh", {}).get("buckets", []) or []:
                        try:
                            wh = float(whb.get("key"))
                        except (TypeError, ValueError):
                            continue
                        kw_buckets = whb.get("kw", {}).get("buckets") or []
                        if not kw_buckets:
                            # Legacy cache without nested kw: cannot form a joint
                            # version — skip (forces --refresh).
                            continue
                        for kwb in kw_buckets:
                            try:
                                kw = float(kwb.get("key"))
                            except (TypeError, ValueError):
                                continue
                            pn = float(
                                (kwb.get("sum_r") or {}).get("value")
                                or kwb.get("doc_count")
                                or 0
                            )
                            entry["pairs"][(wh, kw)] += pn
    return out


def kw_matches(catalog_kw: float, eea_kw: float) -> bool:
    if catalog_kw <= 0 or eea_kw <= 0:
        return False
    return abs(catalog_kw - eea_kw) <= KW_TOL_ABS


def wh_matches(catalog_wh: float, eea_wh: float) -> bool:
    return abs(catalog_wh - eea_wh) <= WH_TOL


def is_same_model_variant(seed_key: str, eea_key: str) -> bool:
    """True if eea_key is seed_key or a trim/power variant — not a different model."""
    if not seed_key or not eea_key:
        return False
    if eea_key == seed_key:
        return True
    if not eea_key.startswith(seed_key):
        return False
    rest = eea_key[len(seed_key) :]
    if not rest:
        return True
    return bool(_VARIANT_SUFFIX_RE.match(rest))


def bev_model_keys(seed_model: str, eea_keys: set[str], brand_key: str) -> list[str]:
    """
    All EEA Cn merge-keys for this catalog model (exact + same-model variants).
    Deterministic sorted order. Empty → no Cn for this year.
    """
    seed_merge = eea.model_name_merge_key(seed_model, brand_key) or eea.norm_alnum(
        seed_model
    )
    sn = eea.clean_model_norm(seed_model) or eea.norm_alnum(seed_model)
    seeds = []
    for cand in (seed_merge, sn):
        if cand and cand not in seeds:
            seeds.append(cand)

    family: set[str] = set()
    for cand in seeds:
        for em in sorted(eea_keys):
            if is_same_model_variant(cand, em):
                family.add(em)

    if family:
        return sorted(family)

    fuzzy = eea.match_model(seed_model, eea_keys, for_ice=False)
    if fuzzy and fuzzy in eea_keys:
        # Expand fuzzy hit to its same-model variants too.
        for em in sorted(eea_keys):
            if is_same_model_variant(fuzzy, em) or is_same_model_variant(em, fuzzy):
                family.add(em)
            # Also: if fuzzy is a longer trim, include other trims sharing the
            # longest seed prefix among seeds.
            for cand in seeds:
                if is_same_model_variant(cand, em):
                    family.add(em)
        if family:
            return sorted(family)
        return [fuzzy]
    return []


def merge_cells(cells: list[dict]) -> dict:
    """Union F/P Zr→pairs and cn_raws across same-model Cn keys for one year."""
    out: dict = {"F": {}, "P": {}, "cn_raws": set()}
    for cell in cells:
        out["cn_raws"] |= set(cell.get("cn_raws") or [])
        for status in ("F", "P"):
            for zr, meta in (cell.get(status) or {}).items():
                dest = out[status].setdefault(
                    zr, {"n": 0.0, "pairs": defaultdict(float)}
                )
                dest["n"] += float(meta.get("n") or 0)
                for pair, n in (meta.get("pairs") or {}).items():
                    dest["pairs"][pair] += float(n)
    return out


def versions_from_zr_map(zr_map: dict) -> list[dict]:
    """Flatten to joint versions; drop Zr==Wh (misfiled consumption as range)."""
    versions: list[dict] = []
    for zr in sorted(zr_map.keys()):
        meta = zr_map[zr]
        for (wh, kw), n in sorted((meta.get("pairs") or {}).items()):
            if int(zr) == int(round(float(wh))):
                # Sanity: Electric range equals Wh/km on the same record.
                continue
            versions.append(
                {"zr": int(zr), "wh": float(wh), "kw": float(kw), "n": float(n)}
            )
    return versions


def preferred_versions(cell: dict) -> tuple[str, list[dict]]:
    """
    Return (status|conflict, versions).
    If both F and P exist with different Zr sets → ('fp_conflict', []).
    """
    f_zrs = set(cell.get("F") or {})
    p_zrs = set(cell.get("P") or {})
    if f_zrs and p_zrs and f_zrs != p_zrs:
        return "fp_conflict", []
    if f_zrs:
        return "F", versions_from_zr_map(cell["F"])
    return "P", versions_from_zr_map(cell.get("P") or {})


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
    status, versions = preferred_versions(cell)
    eea_model_label = (
        matched_keys[0] if len(matched_keys) == 1 else ",".join(matched_keys)
    )

    if status == "fp_conflict":
        return {
            "id": row.get("id"),
            "result": "skip",
            "reason": "F/P conflict: Final and Provisional Zr differ for same model/year",
            "eea_model": eea_model_label,
            "year": year,
            "f_zr": sorted(cell.get("F") or {}),
            "p_zr": sorted(cell.get("P") or {}),
        }

    if not versions:
        # All versions dropped (e.g. every Zr==Wh) or empty status map.
        raw_f = cell.get("F") or {}
        raw_p = cell.get("P") or {}
        if raw_f or raw_p:
            return {
                "id": row.get("id"),
                "result": "skip",
                "reason": "Zr equals Wh/km on EEA record(s) or no joint Wh×kW versions",
                "eea_model": eea_model_label,
                "year": year,
                "status": "F" if raw_f else "P",
            }
        return {
            "id": row.get("id"),
            "result": "skip",
            "reason": "no Zr under preferred Status",
            "eea_model": eea_model_label,
            "year": year,
            "status": status,
        }

    energy = row.get("energyConsumptionKWhPerKm")
    catalog_wh = float(energy) * 1000.0 if energy and float(energy) > 0 else None
    catalog_kw = (
        float(row["powerKw"]) if row.get("powerKw") not in (None, "", 0) else None
    )

    # Both filters are mandatory. Missing catalog field → filter empty → nil.
    if catalog_kw is None or catalog_wh is None:
        return {
            "id": row.get("id"),
            "result": "skip",
            "reason": "missing catalog powerKw and/or Wh/km; cannot jointly match EEA version",
            "eea_model": eea_model_label,
            "year": year,
            "status": status,
            "catalog_wh": catalog_wh,
            "catalog_kw": catalog_kw,
            "candidate_zr": sorted({v["zr"] for v in versions}),
        }

    matched = [
        v
        for v in versions
        if kw_matches(catalog_kw, v["kw"]) and wh_matches(catalog_wh, v["wh"])
    ]
    if not matched:
        return {
            "id": row.get("id"),
            "result": "skip",
            "reason": "no EEA version jointly matches catalog kW (±5) and Wh/km (±1)",
            "eea_model": eea_model_label,
            "year": year,
            "status": status,
            "catalog_wh": catalog_wh,
            "catalog_kw": catalog_kw,
            "candidate_zr": sorted({v["zr"] for v in versions}),
        }

    zrs = sorted({v["zr"] for v in matched})
    if len(zrs) != 1:
        return {
            "id": row.get("id"),
            "result": "skip",
            "reason": "ambiguous Zr (multiple versions jointly match kW+Wh)",
            "eea_model": eea_model_label,
            "year": year,
            "status": status,
            "candidate_zr": zrs,
            "cn_raws": sorted(cell.get("cn_raws") or []),
            "catalog_wh": catalog_wh,
            "catalog_kw": catalog_kw,
        }

    zr = zrs[0]
    meta_n = sum(v["n"] for v in matched if v["zr"] == zr)
    return {
        "id": row["id"],
        "result": "fill",
        "wltpRangeKm": int(zr),
        "eea_brand": brand_key,
        "eea_model": eea_model_label,
        "eea_cn_raws": sorted(cell.get("cn_raws") or []),
        "eea_year": year,
        "status": status,
        "n": meta_n,
        "catalog_wh": catalog_wh,
        "catalog_kw": catalog_kw,
        "matched_versions": [
            {"wh": v["wh"], "kw": v["kw"], "n": v["n"]} for v in matched if v["zr"] == zr
        ],
        "source": "EEA co2cars IT Zr",
        "fetched_note": (
            "Status F preferred; P only if F has no Zr; joint Wh×kW match required; "
            "F/P Zr conflict or Zr==Wh → nil"
        ),
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
        "(F preferred; joint kW±5 & Wh±1 on same record; no averages; "
        "F/P conflict or Zr==Wh → nil)."
    )
    eea.CDN_PATH.write_text(
        json.dumps(cdn, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


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

    for brand_key, brand_rows in sorted(by_brand.items()):
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

    fills.sort(key=lambda d: d.get("id") or "")
    skips.sort(key=lambda d: d.get("id") or "")

    if not args.dry_run:
        by_id = {d["id"]: d for d in fills}
        for r in rows:
            d = by_id.get(r.get("id"))
            if not d:
                continue
            r["wltpRangeKm"] = int(d["wltpRangeKm"])
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
                "F and P with different Zr sets → nil",
                "All same-model Cn variants included before ambiguity check",
                "Fill only if exactly one Zr has a joint Wh×kW version matching catalog (±1 Wh, ±5 kW)",
                "Empty filter → nil; never average; Zr==Wh on record → drop version",
            ],
            "fills": fills,
            "skips": skips,
        }
        eea.CACHE_DIR.mkdir(parents=True, exist_ok=True)
        REFS_PATH.write_text(
            json.dumps(refs, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        if FIXTURE_REFS.parent.is_dir():
            FIXTURE_REFS.write_text(
                json.dumps(refs, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )

    after_rows = (
        rows
        if not args.dry_run
        else [
            {
                **r,
                "wltpRangeKm": next(
                    (f["wltpRangeKm"] for f in fills if f["id"] == r["id"]),
                    r.get("wltpRangeKm"),
                ),
            }
            for r in rows
        ]
    )
    after_with = sum(
        1 for r in after_rows if r.get("powertrain") == "ev" and r.get("wltpRangeKm")
    )
    report = {
        "dry_run": args.dry_run,
        "seedVersion": NEW_SEED_VERSION,
        "bev_total": before_total,
        "with_range_before": before_with,
        "with_range_after": after_with,
        "filled": len(fills),
        "skipped": len(skips),
        "skip_reasons": {},
        "fill_ids": [f["id"] for f in fills],
        "examples": {
            "tesla-model-3-2026": next(
                (s for s in skips + fills if s.get("id") == "tesla-model-3-2026"), None
            ),
            "tesla-model-3-2024": next(
                (s for s in skips + fills if s.get("id") == "tesla-model-3-2024"), None
            ),
            "mazda-mx-30-2020": next(
                (s for s in skips + fills if s.get("id") == "mazda-mx-30-2020"), None
            ),
            "jaguar-i-pace-2021": next(
                (s for s in skips + fills if s.get("id") == "jaguar-i-pace-2021"), None
            ),
        },
    }
    for s in skips:
        reason = s.get("reason") or "unknown"
        report["skip_reasons"][reason] = report["skip_reasons"].get(reason, 0) + 1

    REPORT_PATH.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"BEV {before_total}: with_range {before_with}→{after_with} "
        f"filled={len(fills)} skipped={len(skips)} dry={args.dry_run}"
    )
    print("skip_reasons", report["skip_reasons"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
