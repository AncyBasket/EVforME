#!/usr/bin/env python3
"""
Catalog truth follow-up (PR #16 review) → seedVersion 44.

1. Drop remaining ghost models (Mercedes 500 aggregate, Nissan 350Z, …).
2. Pre-2010 rows must not claim EEA (co2cars IT starts 2010).
3. Propagate corrected 2025 → 2026 estimates (same fuel / powertrain).
4. Restore wrongly dropped real cars (BMW N Series, Doblò, Trax, Genesis, …)
   via volume-first EEA series mapping, else low-confidence stima.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import fill_catalog_fuels_from_eea as eea
import fix_catalog_truth as truth

NEW_SEED_VERSION = 44
EEA_DATA_START_YEAR = 2010
REPORT_PATH = truth.CACHE_DIR / "catalog_truth_v44_report.json"

# Explicit restores requested in review (plus closely related Genesis SUVs).
RESTORE_ID_PREFIXES = (
    "bmw-1-series-",
    "bmw-2-series-",
    "bmw-3-series-",
    "bmw-4-series-",
    "bmw-5-series-",
    "fiat-doblo-",
    "chevrolet-trax-",
    "genesis-g70-",
    "genesis-g80-",
    "genesis-gv70-",
    "genesis-gv80-",
)

# Additional dead / aggregate-only names (extend v43 list).
EXTRA_DEAD: list[tuple[str, re.Pattern[str], int]] = [
    ("MERCEDES", re.compile(r"^500$", re.I), 2010),  # G 500 + S 500 mashed
    ("NISSAN", re.compile(r"^350Z$", re.I), 2010),  # out of production ~2009
]


def is_extra_dead(row: dict) -> bool:
    b = truth.brand_u(row).replace("-", "").replace(" ", "")
    model = str(row.get("model", "")).strip()
    year = int(row.get("year") or 0)
    for brand_sub, pat, min_year in EXTRA_DEAD:
        if brand_sub.replace("-", "") not in b:
            continue
        if year >= min_year and pat.search(model):
            return True
    return False


def series_digit(model: str) -> int | None:
    m = re.match(r"^(\d)\s*series$", (model or "").strip(), re.I)
    return int(m.group(1)) if m else None


def best_hit_for_bmw_series(
    ice_map: dict, digit: int, year: int
) -> tuple[str, str, dict] | None:
    """Max-sum_r among Cn like 118D / 320DXDRIVE for that series digit."""
    candidates: list[tuple[float, str, str, dict]] = []
    pat = re.compile(rf"^{digit}\d{{2}}")
    for (mn, y, ft), cell in ice_map.items():
        if y != year:
            continue
        if "ELECTRIC" in ft:
            continue
        if not pat.match(mn):
            continue
        # Soft-penalize M / performance trims.
        n = float(cell.get("n") or 0)
        if n <= 0:
            continue
        penalty = 0.0
        if mn.endswith("M") or "MCOMPETITION" in mn or "M40" in mn or "M50" in mn:
            penalty = n * 0.4
        candidates.append((n - penalty, mn, ft, cell))
    if not candidates:
        return None
    candidates.sort(key=lambda t: -t[0])
    _, mn, ft, cell = candidates[0]
    return mn, ft, cell


def resolve_restore_hit(
    row: dict, ice_maps: dict, hev_maps: dict
) -> tuple[str, str, dict, int] | None:
    """EEA hit for restored rows — series-aware for BMW N Series."""
    brand = truth.brand_u(row)
    year = int(row.get("year") or 0)
    years_try = [year] + ([y for y in range(year - 1, 2016, -1)] if year >= 2025 else [])
    ice_map = ice_maps.get(brand) or {}
    digit = series_digit(str(row.get("model") or ""))
    if brand == "BMW" and digit is not None:
        for y in years_try:
            if y < 2017:
                break
            hit = best_hit_for_bmw_series(ice_map, digit, y)
            if hit:
                mn, ft, cell = hit
                return mn, ft, cell, y
        return None
    # Genesis: fuzzy Cn contains G70 / G80 / GV70…
    model_u = truth.family_prefix(str(row.get("model") or ""))
    if brand in ("GENESIS", "HYUNDAI") and model_u:
        # Prefer GENESIS map; also scan HYUNDAI (EEA sometimes files under Mk=HYUNDAI).
        for bkey in ("GENESIS", "HYUNDAI"):
            mmap = ice_maps.get(bkey) or {}
            for y in years_try:
                if y < 2017:
                    break
                best = truth.best_hit_for_family(mmap, model_u, y, thermal_only=True)
                if best and float(best[2].get("n") or 0) >= 1:
                    # Also accept Cn that merely contain the model token.
                    return best[0], best[1], best[2], y
                # Fallback: any Cn containing model token.
                cands = []
                for (mn, yy, ft), cell in mmap.items():
                    if yy != y or "ELECTRIC" in ft:
                        continue
                    if model_u in mn:
                        cands.append((float(cell.get("n") or 0), mn, ft, cell))
                if cands:
                    cands.sort(reverse=True)
                    n, mn, ft, cell = cands[0]
                    if n >= 1:
                        return mn, ft, cell, y
    return truth.resolve_eea_hit(row, ice_maps, hev_maps, volume_first=True)


def load_main_seed() -> list[dict]:
    raw = subprocess.check_output(
        ["git", "show", "main:EVforME?/Data/vehicles.seed.quality.json"],
        cwd=str(truth.REPO),
    )
    return json.loads(raw)


def relabel_pre2010(rows: list[dict]) -> int:
    n = 0
    for r in rows:
        year = int(r.get("year") or 0)
        if year >= EEA_DATA_START_YEAR:
            continue
        sn = str(r.get("sourceName") or "")
        sl = sn.lower()
        if "seed+eea" in sl or sl.startswith("eea") or "co2cars" in sl:
            # Do not keep "EEA" in the label — Come calcoliamo must not offer the EEA link.
            r["sourceName"] = "stima (pre-2010; dati consumi non da co2cars IT)"
            r["confidenceScore"] = 0.3
            n += 1
    return n


def propagate_2026_from_2025(rows: list[dict]) -> list[dict]:
    by_id = {r["id"]: r for r in rows if r.get("id")}
    changes = []
    for r in rows:
        if int(r.get("year") or 0) != 2026:
            continue
        rid = str(r.get("id") or "")
        if not rid.endswith("-2026"):
            continue
        sib_id = rid[:-4] + "2025"
        sib = by_id.get(sib_id)
        if not sib:
            continue
        sn = str(sib.get("sourceName") or "").lower()
        # Sibling must be EEA-backed (co2cars, Wh/km audit, or seed+EEA with real n).
        if not (
            "eea" in sn
            or "co2cars" in sn
            or "wh/km" in sn
            or sn.startswith("seed+eea")
        ):
            continue
        # Skip bare stima siblings.
        if sn.startswith("stima"):
            continue
        pt = (r.get("powertrain") or "").lower()
        ch: dict = {"id": rid, "from": sib_id}
        if pt == "ev":
            old = r.get("energyConsumptionKWhPerKm")
            new = sib.get("energyConsumptionKWhPerKm")
            if isinstance(new, (int, float)) and new > 0:
                if not isinstance(old, (int, float)) or abs(float(old) - float(new)) / float(new) > 0.001:
                    ch["kwh100_from"] = round(float(old) * 100, 2) if isinstance(old, (int, float)) else None
                    ch["kwh100_to"] = round(float(new) * 100, 2)
                    r["energyConsumptionKWhPerKm"] = new
                    if isinstance(sib.get("wltpConsumptionKWh100km"), (int, float)):
                        r["wltpConsumptionKWh100km"] = sib["wltpConsumptionKWh100km"]
                    elif isinstance(new, (int, float)):
                        r["wltpConsumptionKWh100km"] = round(float(new) * 100, 2)
        else:
            old = r.get("fuelConsumptionLPerKm")
            new = sib.get("fuelConsumptionLPerKm")
            if isinstance(new, (int, float)) and new > 0:
                if not isinstance(old, (int, float)) or abs(float(old) - float(new)) / float(new) > 0.001:
                    ch["l100_from"] = round(float(old) * 100, 2) if isinstance(old, (int, float)) else None
                    ch["l100_to"] = round(float(new) * 100, 2)
                    r["fuelConsumptionLPerKm"] = new
            if sib.get("fuelKind"):
                r["fuelKind"] = sib["fuelKind"]
            if isinstance(sib.get("co2gKm"), (int, float)):
                r["co2gKm"] = sib["co2gKm"]
            if isinstance(sib.get("powerKw"), (int, float)):
                r["powerKw"] = sib["powerKw"]
                tax, _ = eea.national_bollo_eur(
                    float(sib["powerKw"]), 2026, fuel_kind=sib.get("fuelKind") or "petrol"
                )
                r["taxesPerYear"] = tax
        r["sourceName"] = "stima (da EEA IT 2025 stessa variante)"
        r["confidenceScore"] = 0.4
        r["sourceUpdatedAt"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if len(ch) > 2:
            changes.append(ch)
    return changes


def restore_rows(
    current: list[dict], ice_maps: dict, hev_maps: dict
) -> tuple[list[dict], dict]:
    main_rows = load_main_seed()
    by_main = {r["id"]: r for r in main_rows}
    have = {r["id"] for r in current}
    stats = {"restored_eea": [], "restored_stima": [], "skipped_dead": []}

    for rid, row in by_main.items():
        if rid in have:
            continue
        if not any(rid.startswith(p) for p in RESTORE_ID_PREFIXES):
            continue
        if truth.is_dead_model(row) or is_extra_dead(row):
            stats["skipped_dead"].append(rid)
            continue
        # Fresh copy
        r = json.loads(json.dumps(row))
        hit = resolve_restore_hit(r, ice_maps, hev_maps)
        if hit and float(hit[2].get("n") or 0) >= 30:
            mn, ft, cell, ey = hit
            truth.apply_hit_to_row(
                r, mn, ft, cell, ey, force=True, update_consumption=True, allow_fuel_change=True
            )
            stats["restored_eea"].append({"id": rid, "eea_model": mn, "ft": ft, "n": cell.get("n"), "eea_year": ey})
        else:
            r["sourceName"] = "stima (ripristinata; nessun match EEA IT affidabile)"
            r["confidenceScore"] = 0.35
            # Clear orphan high kW that won't match bollo.
            if isinstance(r.get("powerKw"), (int, float)) and float(r["powerKw"]) > 0:
                expect, _ = eea.national_bollo_eur(
                    float(r["powerKw"]), int(r.get("year") or 2026), fuel_kind=r.get("fuelKind") or "petrol"
                )
                if abs(float(r.get("taxesPerYear") or 0) - expect) > 2:
                    r["powerKw"] = None
            stats["restored_stima"].append(rid)
        current.append(r)
        have.add(rid)

    current.sort(key=lambda x: (str(x.get("brand") or ""), str(x.get("model") or ""), int(x.get("year") or 0), str(x.get("id") or "")))
    return current, stats


def drop_ghosts(rows: list[dict]) -> tuple[list[dict], list[str]]:
    kept: list[dict] = []
    removed: list[str] = []
    for r in rows:
        if is_extra_dead(r):
            removed.append(str(r.get("id")))
            continue
        kept.append(r)
    return kept, removed


def bump_metadata(rows: list[dict], report: dict) -> None:
    eea.bump_seed_version(NEW_SEED_VERSION)
    raw = truth.SEED_PATH.read_bytes()
    cdn = json.loads(truth.CDN_PATH.read_text(encoding="utf-8"))
    cdn["seedVersion"] = NEW_SEED_VERSION
    cdn["rows"] = len(rows)
    cdn["bytes"] = len(raw)
    cdn["updatedAt"] = datetime.now(timezone.utc).isoformat()
    cdn["note"] = (
        f"seedVersion {NEW_SEED_VERSION}: catalog truth follow-up — drop 500/350Z ghosts; "
        f"pre-2010 stima (no EEA); 2026←2025; restore series/Doblo/Trax/Genesis."
    )
    truth.CDN_PATH.write_text(json.dumps(cdn, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report["seedVersion"] = NEW_SEED_VERSION
    report["rows"] = len(rows)
    report["bytes"] = len(raw)


def rebuild_refs(rows: list[dict], ice_maps: dict, hev_maps: dict) -> list[dict]:
    return truth.build_refs(rows, ice_maps, hev_maps)


def main() -> int:
    rows: list[dict] = json.loads(truth.SEED_PATH.read_text(encoding="utf-8"))
    before = len(rows)
    ice_maps = truth.load_ice_maps()
    hev_maps = truth.load_hev_maps()

    report: dict = {
        "before": before,
        "removed_ghosts": [],
        "pre2010_relabeled": 0,
        "propagated_2026": [],
        "restored_eea": [],
        "restored_stima": [],
    }

    rows, ghosts = drop_ghosts(rows)
    report["removed_ghosts"] = ghosts

    report["pre2010_relabeled"] = relabel_pre2010(rows)
    report["propagated_2026"] = propagate_2026_from_2025(rows)

    rows, restore_stats = restore_rows(rows, ice_maps, hev_maps)
    report["restored_eea"] = restore_stats["restored_eea"]
    report["restored_stima"] = restore_stats["restored_stima"]
    report["skipped_dead"] = restore_stats["skipped_dead"]

    # Re-run pre-2010 on restored (none expected) and 2026 prop again after restore.
    report["pre2010_relabeled"] = relabel_pre2010(rows)
    # Second pass 2026 in case restored 2025/2026 pairs.
    more = propagate_2026_from_2025(rows)
    seen = {c["id"] for c in report["propagated_2026"]}
    for c in more:
        if c["id"] not in seen:
            report["propagated_2026"].append(c)

    report["after"] = len(rows)
    refs = rebuild_refs(rows, ice_maps, hev_maps)

    print(
        f"catalog_truth_v44: {before} → {len(rows)} "
        f"(ghosts={len(ghosts)} pre2010={report['pre2010_relabeled']} "
        f"2026prop={len(report['propagated_2026'])} "
        f"restore_eea={len(report['restored_eea'])} restore_stima={len(report['restored_stima'])})"
    )

    truth.SEED_PATH.write_text(
        json.dumps(rows, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8"
    )
    truth.REFS_PATH.write_text(json.dumps(refs, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    bump_metadata(rows, report)
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote seedVersion={NEW_SEED_VERSION} refs={len(refs)} report={REPORT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
