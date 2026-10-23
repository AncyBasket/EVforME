#!/usr/bin/env python3
"""
Catalog truth pass (audit PR fix/catalog-truth).

1. Drop fake / no-EEA-IT rows (placeholder bollo 210, dead model names).
2. Re-anchor high bollo (>€2000) to the most-registered EEA IT variant (max sum_r).
3. Relabel pre-2018 NEDC; mark 2025/2026 without EEA year as estimate.
4. Align ICE/HEV (±20% vs EEA CO₂→FC) and listed EV outliers when EEA Wh/km is available.
5. Bump seedVersion + catalog_cdn metadata; write EEA refs for Swift hygiene tests.

Usage:
  python3 scripts/fix_catalog_truth.py
  python3 scripts/fix_catalog_truth.py --dry-run
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

import fill_catalog_fuels_from_eea as eea

REPO = eea.REPO
SEED_PATH = eea.SEED_PATH
CDN_PATH = eea.CDN_PATH
CACHE_DIR = eea.CACHE_DIR
CATALOG_SERVICE = eea.CATALOG_SERVICE
REFS_PATH = CACHE_DIR / "catalog_truth_eea_refs.json"
REPORT_PATH = CACHE_DIR / "catalog_truth_report.json"

NEW_SEED_VERSION = 43
PLACEHOLDER_TAX = 210.0
TAX_HIGH = 2000.0
CONS_TOLERANCE = 0.20
WLTP_ERA_START = 2018
# Below this EEA n we refuse to invent bollo/kW (leave unknown → UI asks kW).
MIN_EEA_N_FOR_TAX = 30
# Consumption alignment / refs require a stronger volume signal.
MIN_EEA_N_FOR_CONS = 100

# Dead / US-only / nonsense names that must not appear as recent EU passenger cars.
DEAD_MODEL_PATTERNS: list[tuple[str, re.Pattern[str], int]] = [
    # (brand_norm_substring, model regex, min_year_to_drop)
    ("AUDI", re.compile(r"^(100|200|80|90|4000|5000)$", re.I), 2000),
    ("MERCEDES", re.compile(r"^(190|200|220|230|240|250|260|280|300|380|420|500|560|600)$", re.I), 2010),
    ("BMW", re.compile(r"^(228|323I|323)$", re.I), 2015),
    ("FORD", re.compile(r"(bradford|affordable\s*aluminum|b-?750)", re.I), 0),
    ("KIA", re.compile(r"^miami$", re.I), 0),
    ("NISSAN", re.compile(r"^axxess$", re.I), 0),
    ("NISSAN", re.compile(r"^350z$", re.I), 2010),  # real car through ~2009
    ("PEUGEOT", re.compile(r"^405$", re.I), 2010),
    ("HYUNDAI", re.compile(r"^(genesis|excel)$", re.I), 2015),
]


def brand_u(row: dict) -> str:
    b = str(row.get("brand", "")).upper().replace("É", "E")
    return eea.BRAND_TO_EEA_MK.get(b, b)


def is_dead_model(row: dict) -> bool:
    b = brand_u(row).replace("-", "").replace(" ", "")
    model = str(row.get("model", "")).strip()
    year = int(row.get("year") or 0)
    for brand_sub, pat, min_year in DEAD_MODEL_PATTERNS:
        if brand_sub.replace("-", "") not in b:
            continue
        if year >= min_year and pat.search(model):
            return True
    return False


def load_ice_maps(use_cache: bool = True) -> dict[str, dict]:
    maps: dict[str, dict] = {}
    for path in sorted(CACHE_DIR.glob("IT_*_fuels.json")):
        if "_hev_" in path.name:
            continue
        brand = path.name[len("IT_") : -len("_fuels.json")].replace("_", " ")
        brand = brand.replace("MERCEDES-BENZ", "MERCEDES-BENZ")
        wrap = json.loads(path.read_text(encoding="utf-8"))
        # Mk in cache query
        mk = (wrap.get("_query") or {}).get("query", {}).get("bool", {}).get("must", [])
        brand_key = brand_u({"brand": brand})
        for term in mk:
            if "term" in term and "Mk" in term["term"]:
                brand_key = str(term["term"]["Mk"]).upper()
        maps[brand_key] = eea.parse_brand_aggs(wrap, brand_key)
    return maps


def load_hev_maps() -> dict[str, dict]:
    maps: dict[str, dict] = {}
    for path in sorted(CACHE_DIR.glob("IT_*_hev_FmH.json")):
        wrap = json.loads(path.read_text(encoding="utf-8"))
        brand_key = path.name[len("IT_") : -len("_hev_FmH.json")].replace("_", " ").upper()
        for term in (wrap.get("_query") or {}).get("query", {}).get("bool", {}).get("must", []):
            if "term" in term and "Mk" in term["term"]:
                brand_key = str(term["term"]["Mk"]).upper()
        maps[brand_key] = eea.parse_brand_aggs(wrap, brand_key)
    return maps


def family_prefix(model_raw: str) -> str:
    """Normalize seed model to a family prefix used for EEA Cn matching."""
    clean = eea.clean_model_norm(model_raw) or eea.norm_alnum(model_raw)
    # Keep leading family tokens (GLE, RANGEROVERSPORT, DEFENDER, …).
    return clean


def best_hit_for_family(
    ice_map: dict,
    family: str,
    year: int,
    *,
    prefer_ft: str | None = None,
    thermal_only: bool = False,
) -> tuple[str, str, dict] | None:
    """
    Among EEA cells for `year` whose model_norm starts with `family`, pick max sum_r.
    Prefer non-AMG / non-performance when n is close; always take absolute max n.
    Returns (model_norm, ft, cell).
    """
    if not family or len(family) < 2:
        return None
    candidates: list[tuple[float, str, str, dict]] = []
    for (mn, y, ft), cell in ice_map.items():
        if y != year:
            continue
        if not (mn == family or mn.startswith(family)):
            continue
        if thermal_only and ("ELECTRIC" in ft or ft == "ELECTRIC"):
            continue
        n = float(cell.get("n") or 0)
        if n <= 0:
            continue
        # Soft penalty for AMG / performance trims so volume GLE 300 D wins over rare 63 S
        # unless the AMG really has more registrations.
        penalty = 0.0
        if "AMG" in mn or "63S" in mn:
            penalty = n * 0.15
        candidates.append((n - penalty, mn, ft, cell))
    if not candidates:
        return None
    if prefer_ft:
        pref = [c for c in candidates if c[2] == prefer_ft]
        if not pref:
            return None
        candidates = pref
    candidates.sort(key=lambda t: -t[0])
    _, mn, ft, cell = candidates[0]
    return mn, ft, cell


def resolve_eea_hit(
    row: dict,
    ice_maps: dict[str, dict],
    hev_maps: dict[str, dict],
    *,
    prefer_seed_fuel: bool = True,
    volume_first: bool = False,
) -> tuple[str, str, dict, int] | None:
    """Return (eea_model, ft, cell, eea_year) or None.

    `volume_first`: ignore seed fuelKind and take the max-sum_r EEA variant
    in the model family (used for bollo repair — e.g. GLE → GLE 300 d).
    """
    brand = brand_u(row)
    year = int(row.get("year") or 0)
    pt = (row.get("powertrain") or "").lower()
    ice_map = ice_maps.get(brand) or {}
    hev_map = hev_maps.get(brand) or {}
    model_raw = str(row.get("model", ""))
    locked = seed_fuel_locked(row)
    want = eea.seed_fuel_ft(row) if prefer_seed_fuel and not volume_first else None
    if locked == "diesel":
        want = "DIESEL"
    elif locked == "lpg":
        want = "LPG"
    elif locked == "cng":
        want = "NG"

    # Exact / fuzzy model match first (existing helper).
    eea_models = {k[0] for k in ice_map} | {k[0] for k in hev_map}
    model_n = eea.match_model(model_raw, eea_models, for_ice=(pt == "ice"))
    years_try = [year] + ([y for y in range(year - 1, 2016, -1)] if year >= 2025 else [])
    if year >= 2026:
        years_try = [2025, 2024, 2023] + [y for y in years_try if y not in (2025, 2024, 2023)]

    fam = family_prefix(model_raw)
    for y in years_try:
        if y < 2017:
            break
        if volume_first:
            # ICE/HEV seed rows must not latch onto PHEV EEA Cn (…/ELECTRIC).
            thermal = pt in ("ice", "hev")
            # Locked diesel/LPG/CNG: volume among that fuel only.
            best = best_hit_for_family(ice_map, fam, y, prefer_ft=want, thermal_only=thermal)
            best_h = best_hit_for_family(hev_map, fam, y, prefer_ft=want, thermal_only=thermal)
            pick = None
            if best and best_h:
                pick = best if float(best[2].get("n") or 0) >= float(best_h[2].get("n") or 0) else best_h
            else:
                pick = best or best_h
            if pick:
                mn, ft, cell = pick
                return mn, ft, cell, y
            continue
        if model_n and want:
            hit = ice_map.get((model_n, y, want)) or hev_map.get((model_n, y, want))
            if hit and float(hit.get("n") or 0) >= 1:
                return model_n, want, hit, y
        best = best_hit_for_family(ice_map, fam, y, prefer_ft=want)
        if best:
            mn, ft, cell = best
            return mn, ft, cell, y
        best_h = best_hit_for_family(hev_map, fam, y, prefer_ft=want)
        if best_h:
            mn, ft, cell = best_h
            return mn, ft, cell, y
    return None


def ft_to_fuel_kind(ft: str) -> str:
    ft = (ft or "").upper()
    if ft in ("DIESEL",):
        return "diesel"
    if ft in ("LPG",):
        return "lpg"
    if ft in ("NG", "CNG"):
        return "cng"
    if "DIESEL" in ft and "ELECTRIC" in ft:
        return "diesel"
    return "petrol"


def clear_bollo(row: dict, change: dict, reason: str) -> None:
    change["taxes_from"] = row.get("taxesPerYear")
    row["taxesPerYear"] = 0
    change["taxes_to"] = 0
    change["tax_note"] = reason
    # Drop unreliable high-end kW so the UI can ask the user.
    if isinstance(row.get("powerKw"), (int, float)) and float(row["powerKw"]) > 250:
        change["powerKw_cleared"] = row["powerKw"]
        row["powerKw"] = None


def seed_fuel_locked(row: dict) -> str | None:
    """Preserve explicit diesel/LPG/CNG rows (including `-diesel-` id variants)."""
    fk = (row.get("fuelKind") or "").lower()
    if fk in ("diesel", "lpg", "cng"):
        return fk
    rid = str(row.get("id") or "").lower()
    if "-diesel-" in rid or rid.endswith("-diesel"):
        return "diesel"
    if "-gpl-" in rid or "-lpg-" in rid:
        return "lpg"
    if "-metano-" in rid or "-cng-" in rid:
        return "cng"
    return None


def apply_hit_to_row(
    row: dict,
    eea_model: str,
    ft: str,
    cell: dict,
    eea_year: int,
    *,
    force: bool,
    update_consumption: bool = True,
    update_source: bool = True,
    allow_fuel_change: bool = True,
) -> dict:
    """Update consumption / kw / taxes / source from EEA cell. Returns change dict."""
    change: dict = {"id": row.get("id"), "eea_model": eea_model, "ft": ft, "eea_year": eea_year, "n": cell.get("n")}
    pt = (row.get("powertrain") or "").lower()
    fk = ft_to_fuel_kind(ft)
    locked = seed_fuel_locked(row)
    if locked and not allow_fuel_change:
        fk = locked
    n = float(cell.get("n") or 0)
    kw = cell.get("kw")
    co2 = cell.get("co2")

    update_tax = force  # only bollo-repair paths pass force=True
    if update_tax and n < MIN_EEA_N_FOR_TAX and pt in ("ice", "hev", "phev"):
        # Sparse EEA cell — do not invent bollo from a 2-registration supercar trim.
        clear_bollo(row, change, f"unknown_sparse_n={int(n)}")
    elif update_tax and isinstance(kw, (int, float)) and float(kw) > 0:
        row["powerKw"] = round(float(kw), 1)
        change["powerKw"] = row["powerKw"]
        if pt in ("ice", "hev", "phev"):
            tax, note = eea.national_bollo_eur(float(kw), int(row.get("year") or eea_year), fuel_kind=fk)
            change["taxes_from"] = row.get("taxesPerYear")
            change["taxes_to"] = tax
            change["tax_note"] = note
            row["taxesPerYear"] = tax
            if allow_fuel_change and locked is None:
                row["fuelKind"] = fk
            elif locked:
                row["fuelKind"] = locked
    elif update_tax and pt in ("ice", "hev", "phev") and force:
        clear_bollo(row, change, "unknown_no_kw")

    if (
        update_consumption
        and pt in ("ice", "hev")
        and n >= 1
        and isinstance(co2, (int, float))
        and float(co2) > 0
    ):
        use_fk = locked or fk
        fc100 = eea.co2_to_fuel_per_100km(
            co2, use_fk if use_fk in ("petrol", "diesel", "lpg", "cng") else "petrol"
        )
        if fc100 is not None:
            change["l100_from"] = (
                round(float(row["fuelConsumptionLPerKm"]) * 100, 3)
                if isinstance(row.get("fuelConsumptionLPerKm"), (int, float))
                else None
            )
            row["fuelConsumptionLPerKm"] = round(fc100 / 100.0, 5)
            row["co2gKm"] = int(round(float(co2)))
            if locked:
                row["fuelKind"] = locked
            elif allow_fuel_change:
                row["fuelKind"] = fk
            change["l100_to"] = round(fc100, 3)

    # Source label — only claim "EEA co2cars" when n≥100 (hygiene test).
    if update_source and n >= MIN_EEA_N_FOR_CONS:
        prev = str(row.get("sourceName") or "")
        # Don't clobber curated sources (EV-Database, listino, explicit stima notes).
        if any(tok in prev.lower() for tok in ("ev-database", "listino", "stima(", "+stima")):
            pass
        elif int(row.get("year") or 0) != eea_year:
            row["sourceName"] = f"EEA co2cars IT {eea_year} n={int(n)} (da EEA IT {eea_year})"
            row["confidenceScore"] = 0.45
        else:
            row["sourceName"] = f"EEA co2cars IT {eea_year} n={int(n)}"
            row["confidenceScore"] = 0.8
        row["sourceUpdatedAt"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return change


def is_bare_seed_eea_claim(source_name: str) -> bool:
    """True for generic seed+EEA-WLTP with no other provenance."""
    sl = (source_name or "").strip().lower()
    return sl in ("seed+eea-wltp", "seed+eea-nedc")


def relabel_sources(rows: list[dict]) -> dict:
    stats = {"nedc": 0, "estimate_2026": 0, "estimate_no_eea": 0}
    for r in rows:
        year = int(r.get("year") or 0)
        sn = str(r.get("sourceName") or "")
        sn_l = sn.lower()
        if year < WLTP_ERA_START and ("wltp" in sn_l or sn_l.startswith("seed+eea")):
            # Keep EEA mention but mark NEDC era.
            if "nedc" not in sn_l:
                if sn.startswith("EEA"):
                    r["sourceName"] = sn.replace("WLTP", "NEDC") if "WLTP" in sn else f"{sn};NEDC"
                elif "seed+EEA" in sn:
                    r["sourceName"] = sn.replace("WLTP", "NEDC").replace("wltp", "nedc")
                    if "NEDC" not in r["sourceName"] and "nedc" not in r["sourceName"].lower():
                        r["sourceName"] = "seed+EEA-NEDC"
                else:
                    r["sourceName"] = f"{sn};NEDC"
                stats["nedc"] += 1
            conf = r.get("confidenceScore")
            if isinstance(conf, (int, float)) and conf > 0.7:
                r["confidenceScore"] = 0.65
        # Only relabel bare seed+EEA-WLTP claims (keep EV-Database / listino / stima notes).
        conf = float(r.get("confidenceScore") or 0)
        # High-confidence bare seed+EEA claims with no year-matched EEA → stima.
        if year >= 2026 and is_bare_seed_eea_claim(sn) and conf >= 0.85:
            r["sourceName"] = "stima (ultimo EEA IT disponibile non copre 2026)"
            r["confidenceScore"] = 0.35
            stats["estimate_2026"] += 1
        if year == 2025 and is_bare_seed_eea_claim(sn) and conf >= 0.85:
            r["sourceName"] = "stima (nessun match EEA IT 2025 in cache)"
            r["confidenceScore"] = 0.4
            stats["estimate_no_eea"] += 1
    return stats


# Manual EV Wh/100 corrections from EEA IT (audit list) when cache lacks Wh/km.
EV_EEA_KWH100: dict[str, float] = {
    "mercedes-benz-eqv-2025": 28.2,
    "jaguar-i-pace-2019": 23.5,
    "jaguar-i-pace-2024": 24.0,
    "jaguar-i-pace-2025": 24.7,
    "hyundai-ioniq-5-n-2025": 21.2,
    "kia-ev9-2025": 22.7,
    "renault-zoe-2019": 13.7,
    "mazda-6e-2025": 16.6,
    "cupra-born-2022": 14.2,
    "kia-ev4-2025": 15.3,
}


def align_ev_outliers(rows: list[dict]) -> list[dict]:
    changes = []
    by_id = {r.get("id"): r for r in rows}
    for rid, kwh100 in EV_EEA_KWH100.items():
        r = by_id.get(rid)
        if not r or (r.get("powertrain") or "").lower() != "ev":
            continue
        old = r.get("energyConsumptionKWhPerKm")
        new = round(kwh100 / 100.0, 5)
        # Audit list is authoritative — always apply listed EEA Wh/km.
        if isinstance(old, (int, float)) and abs(float(old) - new) < 1e-9:
            continue
        changes.append(
            {
                "id": rid,
                "kwh100_from": round(float(old) * 100, 2) if isinstance(old, (int, float)) else None,
                "kwh100_to": kwh100,
            }
        )
        r["energyConsumptionKWhPerKm"] = new
        r["wltpConsumptionKWh100km"] = kwh100
        # Avoid "EEA co2cars … n=" hygiene — curated Wh/km from audit, not a sparse co2cars cell.
        r["sourceName"] = f"seed+EEA-WLTP+EEA-Wh/km({kwh100:g})"
        r["confidenceScore"] = 0.75
        r["sourceUpdatedAt"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return changes


def build_refs(rows: list[dict], ice_maps: dict, hev_maps: dict) -> list[dict]:
    refs = []
    for r in rows:
        pt = (r.get("powertrain") or "").lower()
        if pt not in ("ice", "hev"):
            continue
        # Same matching policy as consumption align (prefer seed fuel / locks).
        locked = seed_fuel_locked(r)
        hit = resolve_eea_hit(r, ice_maps, hev_maps, prefer_seed_fuel=True, volume_first=False)
        if not hit and locked is None:
            hit = resolve_eea_hit(r, ice_maps, hev_maps, volume_first=True)
        if not hit:
            continue
        eea_model, ft, cell, eea_year = hit
        n = float(cell.get("n") or 0)
        if n < MIN_EEA_N_FOR_CONS:
            continue
        fk = locked or ft_to_fuel_kind(ft)
        fc100 = eea.co2_to_fuel_per_100km(
            cell.get("co2"), fk if fk in ("petrol", "diesel", "lpg", "cng") else "petrol"
        )
        if fc100 is None:
            continue
        refs.append(
            {
                "id": r.get("id"),
                "eea_l100": round(fc100, 3),
                "n": int(n),
                "eea_year": eea_year,
                "eea_model": eea_model,
                "ft": ft,
                "powerKw": cell.get("kw"),
                "fuelKind": fk,
            }
        )
    for r in rows:
        rid = r.get("id")
        if rid in EV_EEA_KWH100:
            refs.append(
                {
                    "id": rid,
                    "eea_kwh100": EV_EEA_KWH100[rid],
                    "kind": "ev",
                }
            )
    return refs


def bump_metadata(rows: list[dict], report: dict) -> None:
    eea.bump_seed_version(NEW_SEED_VERSION)
    # Override CDN note / rows / bytes after write
    raw = SEED_PATH.read_bytes()
    cdn = json.loads(CDN_PATH.read_text(encoding="utf-8"))
    cdn["seedVersion"] = NEW_SEED_VERSION
    cdn["rows"] = len(rows)
    cdn["bytes"] = len(raw)
    cdn["updatedAt"] = datetime.now(timezone.utc).isoformat()
    cdn["note"] = (
        f"seedVersion {NEW_SEED_VERSION}: catalog truth — drop fake/no-EEA rows; "
        f"bollo from max-sum_r EEA variant; NEDC/estimate labels; ±20% EEA consumption."
    )
    CDN_PATH.write_text(json.dumps(cdn, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    # Ensure Swift comment bump already done by bump_seed_version
    report["seedVersion"] = NEW_SEED_VERSION
    report["rows"] = len(rows)
    report["bytes"] = len(raw)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    rows: list[dict] = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    before = len(rows)
    ice_maps = load_ice_maps()
    hev_maps = load_hev_maps()

    report: dict = {
        "before": before,
        "removed_dead": [],
        "removed_placeholder_210": [],
        "removed_no_eea_claim": [],
        "bollo_fixed": [],
        "bollo_cleared": [],
        "consumption_aligned": [],
        "ev_aligned": [],
        "relabel": {},
    }

    # --- 1. Remove dead models + placeholder 210 without EEA ---
    kept: list[dict] = []
    for r in rows:
        rid = r.get("id")
        tax = float(r.get("taxesPerYear") or 0)
        hit = resolve_eea_hit(r, ice_maps, hev_maps) if (r.get("powertrain") or "").lower() in ("ice", "hev", "phev") else None

        if is_dead_model(r):
            report["removed_dead"].append(rid)
            continue

        if abs(tax - PLACEHOLDER_TAX) < 0.01:
            # Placeholder bollo: keep only if we have a real EEA hit with usable n/kw.
            if not hit or float(hit[2].get("n") or 0) < 30:
                report["removed_placeholder_210"].append(rid)
                continue

        # High-confidence seed+EEA-WLTP on modern years with zero EEA match → fake.
        sn = str(r.get("sourceName") or "")
        year = int(r.get("year") or 0)
        conf = float(r.get("confidenceScore") or 0)
        pt = (r.get("powertrain") or "").lower()
        if (
            pt in ("ice", "hev")
            and year >= 2022
            and conf >= 0.85
            and sn.startswith("seed+EEA")
            and not hit
        ):
            report["removed_no_eea_claim"].append(rid)
            continue

        kept.append(r)

    rows = kept

    def hit_for_row(r: dict, *, volume_first: bool) -> tuple | None:
        locked = seed_fuel_locked(r)
        if locked in ("lpg", "cng"):
            return resolve_eea_hit(r, ice_maps, hev_maps, prefer_seed_fuel=True, volume_first=False)
        if locked == "diesel":
            # Volume among diesel-only; never flip a `-diesel-` row to petrol.
            return resolve_eea_hit(r, ice_maps, hev_maps, volume_first=volume_first, prefer_seed_fuel=True)
        return resolve_eea_hit(r, ice_maps, hev_maps, volume_first=volume_first, prefer_seed_fuel=not volume_first)

    def repair_bollo(r: dict) -> None:
        pt = (r.get("powertrain") or "").lower()
        if pt not in ("ice", "hev", "phev"):
            return
        tax = float(r.get("taxesPerYear") or 0)
        if not (tax > TAX_HIGH or abs(tax - PLACEHOLDER_TAX) < 0.01):
            return
        locked = seed_fuel_locked(r)
        # High bollo → most-registered variant (diesel-locked rows stay diesel).
        vol = hit_for_row(r, volume_first=True)
        if vol:
            eea_model, ft, cell, eea_year = vol
            ch = apply_hit_to_row(
                r,
                eea_model,
                ft,
                cell,
                eea_year,
                force=True,
                update_consumption=True,
                allow_fuel_change=(locked is None),
            )
            report["bollo_fixed"].append(ch)
        else:
            report["bollo_cleared"].append({"id": r.get("id"), "from": tax})
            clear_bollo(r, {"id": r.get("id")}, "unknown_no_eea")

    def clear_incoherent_kw(r: dict) -> None:
        """Drop orphan powerKw that disagrees with catalog bollo (no EEA re-anchor)."""
        pt = (r.get("powertrain") or "").lower()
        if pt not in ("ice", "hev", "phev"):
            return
        kw = r.get("powerKw")
        tax = float(r.get("taxesPerYear") or 0)
        if not isinstance(kw, (int, float)) or kw <= 0 or tax <= 0:
            return
        expect, _ = eea.national_bollo_eur(float(kw), int(r.get("year") or 2026), fuel_kind=r.get("fuelKind") or "petrol")
        if expect and abs(tax - expect) > 2.0:
            r["powerKw"] = None

    # --- 2. Fix high bollo / wrong kW (volume-first) ---
    for r in rows:
        repair_bollo(r)
    for r in rows:
        clear_incoherent_kw(r)

    # --- 4. Align ICE/HEV consumption to EEA when drift >20% ---
    for r in rows:
        pt = (r.get("powertrain") or "").lower()
        if pt not in ("ice", "hev"):
            continue
        locked = seed_fuel_locked(r)
        # Prefer seed fuel; fall back to volume-first only for unlocked petrol rows.
        hit = hit_for_row(r, volume_first=False) or (
            None if locked else hit_for_row(r, volume_first=True)
        )
        if not hit:
            continue
        eea_model, ft, cell, eea_year = hit
        n = float(cell.get("n") or 0)
        if n < 1:
            continue
        use_fk = locked or ft_to_fuel_kind(ft)
        fc100 = eea.co2_to_fuel_per_100km(
            cell.get("co2"), use_fk if use_fk in ("petrol", "diesel", "lpg", "cng") else "petrol"
        )
        if fc100 is None:
            continue
        old = r.get("fuelConsumptionLPerKm")
        if not isinstance(old, (int, float)) or old <= 0:
            continue
        old100 = float(old) * 100
        if abs(old100 - fc100) / fc100 > CONS_TOLERANCE:
            # Consumption only — don't rewrite bollo/source for unlocked high-volume
            # unless n is solid; never flip LPG/CNG/diesel locks.
            ch = apply_hit_to_row(
                r,
                eea_model,
                ft,
                cell,
                eea_year,
                force=False,
                update_consumption=True,
                update_source=(n >= MIN_EEA_N_FOR_CONS),
                allow_fuel_change=(locked is None),
            )
            report["consumption_aligned"].append(ch)

    # Re-check high bollo after consumption.
    for r in rows:
        repair_bollo(r)
    for r in rows:
        clear_incoherent_kw(r)

    report["ev_aligned"] = align_ev_outliers(rows)

    # --- 3. Relabel sources ---
    report["relabel"] = relabel_sources(rows)

    report["after"] = len(rows)
    report["removed_total"] = before - len(rows)

    refs = build_refs(rows, ice_maps, hev_maps)

    print(
        f"catalog_truth: {before} → {len(rows)} "
        f"(−{report['removed_total']}: dead={len(report['removed_dead'])} "
        f"tax210={len(report['removed_placeholder_210'])} "
        f"noEEA={len(report['removed_no_eea_claim'])}); "
        f"bollo_fixed={len(report['bollo_fixed'])} cleared={len(report['bollo_cleared'])}; "
        f"cons={len(report['consumption_aligned'])} ev={len(report['ev_aligned'])}; "
        f"relabel={report['relabel']}"
    )

    if args.dry_run:
        REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"dry-run report → {REPORT_PATH}")
        return 0

    SEED_PATH.write_text(json.dumps(rows, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    REFS_PATH.write_text(json.dumps(refs, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    bump_metadata(rows, report)
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {SEED_PATH} seedVersion={NEW_SEED_VERSION} refs={len(refs)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
