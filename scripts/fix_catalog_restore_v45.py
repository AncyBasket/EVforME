#!/usr/bin/env python3
"""
Catalog restore pass → seedVersion 45 (PR fix/catalog-restore).

Restore wrongly-dropped real IT models from pre-#16 seed (954e804), matching
volume-first EEA IT variants (like BMW N Series), else low-confidence stima.
Also rename BMW 2 Series Active Tourer rows.
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
import fix_catalog_truth_v44 as v44

NEW_SEED_VERSION = 45
PRE_TRUTH_REF = "954e804"
REPORT_PATH = truth.CACHE_DIR / "catalog_restore_v45_report.json"
MIN_N = 30

# Exact IDs requested (priority + single-year gaps).
RESTORE_IDS: list[str] = [
    # Mercedes
    *[f"mercedes-benz-c-class-{y}" for y in range(2022, 2027)],
    *[f"mercedes-benz-e-class-{y}" for y in range(2022, 2027)],
    *[f"mercedes-benz-s-class-{y}" for y in range(2022, 2027)],
    "mercedes-benz-a-class-2026",
    "mercedes-benz-b-class-2026",
    # MINI
    *[f"mini-hatch-{y}" for y in range(2022, 2027)],
    *[f"mini-convertible-{y}" for y in range(2022, 2027)],
    # Other priority
    "mazda-cx-60-2022",
    "mazda-cx-60-2026",
    *[f"volkswagen-arteon-{y}" for y in (2022, 2023, 2024)],
    "jeep-grand-cherokee-2023",
    "jeep-grand-cherokee-2024",
    "land-rover-range-rover-evoque-2025",
    "land-rover-range-rover-evoque-2026",
    "toyota-land-cruiser-2022",
    "toyota-land-cruiser-2023",
    *[f"mitsubishi-outlander-{y}" for y in (2022, 2023, 2024)],
    *[f"mitsubishi-asx-{y}" for y in (2022, 2023)],
    *[f"mitsubishi-eclipse-cross-{y}" for y in (2022, 2023, 2024)],
    *[f"nissan-navara-{y}" for y in range(2022, 2027)],
    # Single-year gaps
    "toyota-prius-2024",
    "kia-rio-2024",
    "nissan-micra-2024",
    "renault-scenic-2024",
    "volkswagen-touareg-2024",
    "ds-ds-7-2024",
    "renault-koleos-2023",
    "renault-koleos-2024",
    "lexus-is-2023",
    "lexus-is-2024",
    "suzuki-s-cross-2022",
    "suzuki-s-cross-2023",
    "suzuki-jimny-2023",
    "suzuki-jimny-2024",
    "mg-mg3-2022",
    "mg-mg3-2023",
    "opel-insignia-2022",
    "peugeot-408-2022",
]


def load_seed_at(ref: str) -> dict[str, dict]:
    raw = subprocess.check_output(
        ["git", "show", f"{ref}:EVforME?/Data/vehicles.seed.quality.json"],
        cwd=str(truth.REPO),
    )
    return {r["id"]: r for r in json.loads(raw)}


def mb_class_letter(model: str) -> str | None:
    m = re.match(r"^([A-ES])-?Class$", (model or "").strip(), re.I)
    return m.group(1).upper() if m else None


def best_hit_mercedes_class(
    ice_map: dict, letter: str, year: int
) -> tuple[str, str, dict] | None:
    """Volume among A180/C220D/E220D/S350D — not CLA/CLE/AMG/SPRINTER."""
    pat = re.compile(rf"^{letter}\d")
    cands: list[tuple[float, str, str, dict]] = []
    for (mn, y, ft), cell in ice_map.items():
        if y != year or "ELECTRIC" in ft:
            continue
        if not pat.match(mn):
            continue
        if mn.startswith(("CLA", "CLE", "CLK", "CLS", "AMG", "SPRINTER", "CITAN")):
            continue
        n = float(cell.get("n") or 0)
        if n <= 0:
            continue
        penalty = n * 0.25 if ("AMG" in mn or "MAYBACH" in mn or mn.endswith("S")) else 0.0
        cands.append((n - penalty, mn, ft, cell))
    if not cands:
        return None
    cands.sort(key=lambda t: -t[0])
    _, mn, ft, cell = cands[0]
    return mn, ft, cell


def best_hit_mini_hatch(ice_map: dict, year: int) -> tuple[str, str, dict] | None:
    cands = []
    for (mn, y, ft), cell in ice_map.items():
        if y != year or "ELECTRIC" in ft:
            continue
        if "COUNTRY" in mn or "CLUB" in mn or "CABRIO" in mn or "CONVERT" in mn:
            continue
        if not (mn.startswith("COOPER") or mn.startswith("MINICOOPER") or mn == "JOHNCOOPERWORKS"):
            continue
        n = float(cell.get("n") or 0)
        if n <= 0:
            continue
        cands.append((n, mn, ft, cell))
    if not cands:
        return None
    cands.sort(reverse=True)
    n, mn, ft, cell = cands[0]
    return mn, ft, cell


def best_hit_mini_convertible(ice_map: dict, year: int) -> tuple[str, str, dict] | None:
    cands = []
    for (mn, y, ft), cell in ice_map.items():
        if y != year or "ELECTRIC" in ft:
            continue
        if "CABRIO" not in mn and "CONVERT" not in mn:
            continue
        n = float(cell.get("n") or 0)
        if n <= 0:
            continue
        cands.append((n, mn, ft, cell))
    if not cands:
        return None
    cands.sort(reverse=True)
    return cands[0][1], cands[0][2], cands[0][3]


# clean_model_norm strips "EV" inside EVOQUE → broken family prefix.
SPECIAL_FAMILY: dict[str, str] = {
    "range rover evoque": "RANGEROVEREVOQUE",
    "range rover sport": "RANGEROVERSPORT",
    "grand cherokee": "GRANDCHEROKEE",
    "cx-60": "CX60",
    "land cruiser": "LANDCRUISER",
    "eclipse cross": "ECLIPSECROSS",
}


def family_for_row(row: dict) -> str:
    model = str(row.get("model") or "").strip().lower()
    if model in SPECIAL_FAMILY:
        return SPECIAL_FAMILY[model]
    return truth.family_prefix(str(row.get("model") or ""))


def resolve_hit(row: dict, ice_maps: dict, hev_maps: dict) -> tuple[str, str, dict, int] | None:
    brand = truth.brand_u(row)
    year = int(row.get("year") or 0)
    model = str(row.get("model") or "")
    years_try = [year]
    for y in range(year - 1, 2016, -1):
        years_try.append(y)
    # New nameplates may only appear in later EEA years (e.g. CX-60 2022 PHEV).
    for y in range(year + 1, 2026):
        if y not in years_try:
            years_try.append(y)

    ice_map = ice_maps.get(brand) or {}

    letter = mb_class_letter(model)
    if brand.startswith("MERCEDES") and letter:
        for y in years_try:
            if y < 2017:
                continue
            hit = best_hit_mercedes_class(ice_map, letter, y)
            if hit and float(hit[2].get("n") or 0) >= 1:
                return hit[0], hit[1], hit[2], y
        return None

    if brand == "MINI":
        for y in years_try:
            if y < 2017:
                continue
            if re.search(r"convertible|cabrio", model, re.I) or "convertible" in str(row.get("id") or ""):
                hit = best_hit_mini_convertible(ice_map, y)
            else:
                hit = best_hit_mini_hatch(ice_map, y)
            if hit and float(hit[2].get("n") or 0) >= 1:
                return hit[0], hit[1], hit[2], y
        return None

    digit = v44.series_digit(model)
    if brand == "BMW" and digit is not None:
        for y in years_try:
            if y < 2017:
                continue
            hit = v44.best_hit_for_bmw_series(ice_map, digit, y)
            if hit:
                return hit[0], hit[1], hit[2], y
        return None

    fam = family_for_row(row)
    # Collect candidates across years; prefer n≥MIN_N (don't stop early on a thin prior year).
    found: list[tuple[float, str, str, dict, int]] = []
    for y in years_try:
        if y < 2017:
            continue
        for thermal_only in (True, False):
            best = truth.best_hit_for_family(ice_map, fam, y, thermal_only=thermal_only)
            best_h = truth.best_hit_for_family(hev_maps.get(brand) or {}, fam, y, thermal_only=thermal_only)
            pick = None
            if best and best_h:
                pick = best if float(best[2].get("n") or 0) >= float(best_h[2].get("n") or 0) else best_h
            else:
                pick = best or best_h
            if pick and float(pick[2].get("n") or 0) >= 1:
                found.append((float(pick[2].get("n") or 0), pick[0], pick[1], pick[2], y))
                break  # thermal_only True first
    if found:
        solid = [f for f in found if f[0] >= MIN_N]
        pool = solid or found
        # Prefer same calendar year, then max n.
        pool.sort(key=lambda t: (0 if t[4] == year else 1, -t[0]))
        _, mn, ft, cell, ey = pool[0]
        return mn, ft, cell, ey

    return truth.resolve_eea_hit(row, ice_maps, hev_maps, volume_first=True)


def as_stima(row: dict, reason: str) -> dict:
    row["sourceName"] = f"stima ({reason})"
    row["confidenceScore"] = 0.35
    row["sourceUpdatedAt"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if isinstance(row.get("powerKw"), (int, float)) and float(row["powerKw"]) > 0:
        expect, _ = eea.national_bollo_eur(
            float(row["powerKw"]), int(row.get("year") or 2026), fuel_kind=row.get("fuelKind") or "petrol"
        )
        if abs(float(row.get("taxesPerYear") or 0) - expect) > 2:
            row["powerKw"] = None
    return row


def rename_bmw_2_active_tourer(rows: list[dict]) -> int:
    """IT volume for recent '2 Series' ICE rows is the 218d Active Tourer — name it so."""
    n = 0
    for r in rows:
        rid = str(r.get("id") or "")
        if not rid.startswith("bmw-2-series-"):
            continue
        year = int(r.get("year") or 0)
        if year < 2022:
            continue
        if r.get("model") == "2 Series Active Tourer":
            continue
        sn = str(r.get("sourceName") or "")
        # EEA-backed or YoY copy from that volume cell.
        if sn.startswith("EEA co2cars") or sn.startswith("stima (da EEA"):
            r["model"] = "2 Series Active Tourer"
            n += 1
    return n


def intentional_exclusions(old: dict[str, dict], current_ids: set[str]) -> list[dict]:
    """Document missing pre-truth IDs we deliberately do not restore."""
    out = []
    for rid, row in sorted(old.items()):
        if rid in current_ids:
            continue
        if rid in RESTORE_IDS:
            continue
        year = int(row.get("year") or 0)
        brand = str(row.get("brand") or "")
        model = str(row.get("model") or "")
        reason = None
        if truth.is_dead_model(row) or v44.is_extra_dead(row):
            reason = "modello fantasma / morto (dead-model filter)"
        elif year >= 2010 and re.fullmatch(r"\d{3}", model) and brand.upper().startswith("MERCEDES") and model == "500":
            reason = "aggregate EEA (G 500 + S 500)"
        elif any(
            x in rid
            for x in (
                "ford-aerostar",
                "ford-aspire",
                "ford-bronco",
                "ford-classic",
                "hyundai-accent",
                "hyundai-azera",
                "hyundai-elantra",
                "hyundai-entourage",
                "kia-amanti",
                "kia-borrego",
                "kia-cadenza",
                "kia-forte",
                "nissan-350z",
                "bmw-128i",
                "bmw-1m",
                "bmw-228",
                "bmw-323i",
                "bmw-318ti",
                "bmw-318ic",
                "bmw-318is",
                "hyundai-genesis",
                "audi-100",
                "audi-5000",
            )
        ):
            reason = "US-only / non-IT / fantasma già escluso in catalog-truth"
        elif year < 2010:
            reason = "già in catalogo come stima pre-2010 oppure non richiesto"
        else:
            # skip listing every remaining gap — only notable families
            continue
        if reason:
            out.append({"id": rid, "reason": reason})
    return out


def bump_metadata(rows: list[dict], report: dict) -> None:
    eea.bump_seed_version(NEW_SEED_VERSION)
    raw = truth.SEED_PATH.read_bytes()
    cdn = json.loads(truth.CDN_PATH.read_text(encoding="utf-8"))
    cdn["seedVersion"] = NEW_SEED_VERSION
    cdn["rows"] = len(rows)
    cdn["bytes"] = len(raw)
    cdn["updatedAt"] = datetime.now(timezone.utc).isoformat()
    cdn["note"] = (
        f"seedVersion {NEW_SEED_VERSION}: restore Mercedes/MINI/gaps via EEA volume IT; "
        f"BMW 2 Series Active Tourer rename; catalog load off main thread."
    )
    truth.CDN_PATH.write_text(json.dumps(cdn, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report["seedVersion"] = NEW_SEED_VERSION
    report["rows"] = len(rows)
    report["bytes"] = len(raw)


def main() -> int:
    rows: list[dict] = json.loads(truth.SEED_PATH.read_text(encoding="utf-8"))
    before = len(rows)
    have = {r["id"] for r in rows}
    old = load_seed_at(PRE_TRUTH_REF)
    ice_maps = truth.load_ice_maps()
    hev_maps = truth.load_hev_maps()

    report: dict = {
        "before": before,
        "restored_eea": [],
        "restored_stima": [],
        "missing_in_pre_truth": [],
        "renamed_active_tourer": 0,
        "intentional_exclusions_sample": [],
    }

    for rid in RESTORE_IDS:
        if rid in have:
            continue
        src = old.get(rid)
        if not src:
            report["missing_in_pre_truth"].append(rid)
            continue
        if truth.is_dead_model(src) or v44.is_extra_dead(src):
            report["restored_stima"].append({"id": rid, "reason": "dead_skipped"})
            continue
        r = json.loads(json.dumps(src))
        hit = resolve_hit(r, ice_maps, hev_maps)

        def apply_or_stima_phev(mn: str, ft: str, cell: dict, ey: int) -> str:
            """Return 'eea' or 'stima'. PHEV EEA cells must not invent ICE L/100 from CS CO₂."""
            pt = (r.get("powertrain") or "").lower()
            is_phev_ft = "ELECTRIC" in (ft or "").upper() and ft.upper() != "ELECTRIC"
            if is_phev_ft and pt in ("ice", "hev"):
                # Keep seed litres; cite EEA for presence/kw; low confidence.
                if isinstance(cell.get("kw"), (int, float)) and float(cell["kw"]) > 0 and float(cell.get("n") or 0) >= MIN_N:
                    r["powerKw"] = round(float(cell["kw"]), 1)
                    tax, _ = eea.national_bollo_eur(
                        float(cell["kw"]), int(r.get("year") or ey), fuel_kind=r.get("fuelKind") or "petrol"
                    )
                    r["taxesPerYear"] = tax
                as_stima(
                    r,
                    f"EEA IT {ey} n={int(cell.get('n') or 0)} variante {mn} è PHEV; consumi seed (non CS CO₂)",
                )
                return "stima"
            update_cons = True
            truth.apply_hit_to_row(
                r, mn, ft, cell, ey, force=True, update_consumption=update_cons, allow_fuel_change=True
            )
            if float(cell.get("n") or 0) < MIN_N:
                as_stima(r, f"EEA IT {ey} n={int(cell.get('n') or 0)} troppo basso; consumi da variante {mn}")
                return "stima"
            return "eea"

        if hit and float(hit[2].get("n") or 0) >= 1:
            mn, ft, cell, ey = hit
            kind = apply_or_stima_phev(mn, ft, cell, ey)
            entry = {"id": rid, "eea_model": mn, "ft": ft, "n": cell.get("n"), "eea_year": ey}
            if kind == "eea":
                report["restored_eea"].append(entry)
            else:
                report["restored_stima"].append(entry)
        else:
            as_stima(r, "ripristinata; nessun match EEA IT affidabile")
            report["restored_stima"].append({"id": rid, "reason": "no_eea"})
        rows.append(r)
        have.add(rid)

    report["renamed_active_tourer"] = rename_bmw_2_active_tourer(rows)

    # Propagate 2026 from 2025 for newly restored pairs.
    report["propagated_2026"] = v44.propagate_2026_from_2025(rows)

    rows.sort(
        key=lambda x: (
            str(x.get("brand") or ""),
            str(x.get("model") or ""),
            int(x.get("year") or 0),
            str(x.get("id") or ""),
        )
    )

    report["after"] = len(rows)
    report["intentional_exclusions_sample"] = intentional_exclusions(old, have)[:80]
    report["intentional_exclusions_note"] = (
        "Elenco completo esclusi: US-only, dead/aggregate, e gap non richiesti in questa PR. "
        f"Sample {len(report['intentional_exclusions_sample'])} voci."
    )

    refs = truth.build_refs(rows, ice_maps, hev_maps)
    truth.SEED_PATH.write_text(
        json.dumps(rows, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8"
    )
    truth.REFS_PATH.write_text(json.dumps(refs, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    bump_metadata(rows, report)
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(
        f"catalog_restore_v45: {before} → {len(rows)} "
        f"eea={len(report['restored_eea'])} stima={len(report['restored_stima'])} "
        f"renamed_AT={report['renamed_active_tourer']} "
        f"missing_src={len(report['missing_in_pre_truth'])}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
