#!/usr/bin/env python3
"""
Catalog restore follow-up → seedVersion 46 (PR #17 review).

1. Drop years with no IT EEA registrations (Navara, Outlander, Arteon, …).
2. Drop ICE/HEV rows for PHEV-only EEA years (no CS L/100 + kWh → cannot ship PHEV).
3. Scenic 2024 → EV from EEA ELECTRIC cell.
4. S-Cross 2022/2023 → same-year SX4 EEA (not 2025).
5. S-Class 2025 → EEA label with variant + n (S 450 d 4MATIC, n=54).
6. Relies on dedupe_fuel_buckets max-not-sum; re-apply all year-2022 EEA hits.
7. Replace "anno precedente" with "da EEA IT {year}".
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import fill_catalog_fuels_from_eea as eea
import fix_catalog_truth as truth
import fix_catalog_restore_v45 as v45

NEW_SEED_VERSION = 46
REPORT_PATH = truth.CACHE_DIR / "catalog_restore_v46_report.json"

# Point 1 — no IT EEA registrations that year.
DROP_NO_IT_EEA: list[str] = [
    *[f"nissan-navara-{y}" for y in range(2022, 2027)],
    *[f"mitsubishi-outlander-{y}" for y in (2022, 2023, 2024)],
    *[f"volkswagen-arteon-{y}" for y in (2022, 2023, 2024)],
    "renault-koleos-2023",
    "renault-koleos-2024",
    "lexus-is-2023",
    "lexus-is-2024",
    "nissan-micra-2024",
    "kia-rio-2024",
    "mg-mg3-2022",
    "mg-mg3-2023",
    "mitsubishi-asx-2022",
    "mitsubishi-asx-2023",
    "suzuki-jimny-2023",
    "suzuki-jimny-2024",
]

# Point 2 — EEA only PHEV; no verified CS L/100 + kWh → drop ICE/HEV seed-litre rows.
DROP_PHEV_ONLY_NO_CS: list[str] = [
    "jeep-grand-cherokee-2023",
    "jeep-grand-cherokee-2024",
    "mazda-cx-60-2022",
    *[f"mitsubishi-eclipse-cross-{y}" for y in (2022, 2023, 2024)],
    "toyota-prius-2024",
    "peugeot-408-2022",
]

NO_IT_REASON = "nessuna immatricolazione IT EEA in quell'anno"
PHEV_ONLY_REASON = (
    "solo PHEV in EEA IT quell'anno; senza L/100 charge-sustaining + kWh verificati "
    "(non si lascia ICE/diesel con litri seed)"
)


def pretty_eea_variant(mn: str, model_raw: str | None = None) -> str:
    """Prefer EEA Cn display string; else C220D → C 220 d; S450D4MATIC → S 450 d 4MATIC."""

    def soften_fuel_letters(s: str) -> str:
        # "S 450 D 4MATIC" / "C 220 D" → lowercase lone D/E after the displacement.
        return re.sub(r"(?<=\d)\s*([DdEe])\b", lambda m: " " + m.group(1).lower(), s)

    if model_raw and str(model_raw).strip():
        return soften_fuel_letters(re.sub(r"\s+", " ", str(model_raw).strip()))
    raw = (mn or "").strip()
    if not raw:
        return raw
    # Keep compact codes like SX4 / CX60 readable.
    if re.fullmatch(r"[A-Z]+\d+[A-Z]*", raw) and len(raw) <= 6 and not re.search(r"\d{3}", raw):
        return raw
    s = re.sub(r"([A-Z]+)(\d)", r"\1 \2", raw)
    s = re.sub(r"(\d)([A-Z]+)", r"\1 \2", s)
    parts = s.split()
    out: list[str] = []
    for i, p in enumerate(parts):
        if p.upper() in ("D", "E", "I", "CDI") and i > 0:
            out.append(p.lower())
        elif p.upper() == "4MATIC":
            out.append("4MATIC")
        else:
            out.append(p)
    return soften_fuel_letters(" ".join(out))


def eea_source_label(
    eea_year: int,
    n: float | int,
    variant: str | None = None,
    model_raw: str | None = None,
) -> str:
    n_i = int(n)
    if variant or model_raw:
        return f"EEA co2cars IT {eea_year} {pretty_eea_variant(variant or '', model_raw)} n={n_i}"
    return f"EEA co2cars IT {eea_year} n={n_i}"


def best_sx4_scross(ice_map: dict, year: int) -> tuple[str, str, dict] | None:
    """Volume-first among SX4 / S-CROSS petrol cells for that calendar year."""
    cands: list[tuple[float, str, str, dict]] = []
    for (mn, y, ft), cell in ice_map.items():
        if y != year:
            continue
        if ft != "PETROL":
            continue
        if "ACROSS" in mn and "SCROSS" not in mn and "SX4" not in mn:
            continue
        if not (("SX4" in mn) or mn.startswith("SCROSS") or mn == "SCROSS"):
            continue
        n = float(cell.get("n") or 0)
        if n <= 0:
            continue
        cands.append((n, mn, ft, cell))
    if not cands:
        return None
    cands.sort(key=lambda t: -t[0])
    _, mn, ft, cell = cands[0]
    return mn, ft, cell


def convert_scenic_2024_to_ev(row: dict, ice_maps: dict) -> dict | None:
    ice = ice_maps.get("RENAULT") or {}
    cell = None
    mn = None
    for key, c in ice.items():
        if key[1] != 2024 or key[2] != "ELECTRIC":
            continue
        if "SCENIC" not in key[0]:
            continue
        if cell is None or float(c.get("n") or 0) > float(cell.get("n") or 0):
            cell, mn = c, key[0]
    if not cell or float(cell.get("n") or 0) < 1:
        return None
    # Sibling energy from catalog Scenic E-Tech 2023 when EEA cache has no Wh/km.
    sibling_kwh = 0.1737
    row["powertrain"] = "ev"
    row["model"] = "Scenic E-Tech"
    row["fuelKind"] = None
    row["fuelConsumptionLPerKm"] = None
    row["co2gKm"] = 0
    row["energyConsumptionKWhPerKm"] = sibling_kwh
    row["wltpConsumptionKWh100km"] = round(sibling_kwh * 100, 1)
    if isinstance(cell.get("kw"), (int, float)) and float(cell["kw"]) > 0:
        row["powerKw"] = round(float(cell["kw"]), 1)
    row["taxesPerYear"] = 0.0
    n = float(cell.get("n") or 0)
    raw_name = cell.get("model_raw") or "Scenic E-Tech Electric"
    row["sourceName"] = (
        f"{eea_source_label(2024, n, mn, raw_name)}; "
        f"kWh/100 da Scenic E-Tech 2023 (EEA cache senza Wh/km)"
    )
    row["confidenceScore"] = 0.55
    row["sourceUpdatedAt"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return {"eea_model": mn, "n": n, "kw": row.get("powerKw")}


def fix_s_cross_year(row: dict, ice_maps: dict) -> dict | None:
    year = int(row.get("year") or 0)
    hit = best_sx4_scross(ice_maps.get("SUZUKI") or {}, year)
    if not hit:
        return None
    mn, ft, cell = hit
    truth.apply_hit_to_row(
        row, mn, ft, cell, year, force=True, update_consumption=True, allow_fuel_change=True
    )
    # Same calendar year — force clear "da EEA IT" redundancy and include variant.
    n = float(cell.get("n") or 0)
    row["sourceName"] = eea_source_label(year, n, mn, cell.get("model_raw"))
    row["confidenceScore"] = 0.8 if n >= truth.MIN_EEA_N_FOR_CONS else 0.55
    return {"eea_model": mn, "ft": ft, "n": n, "eea_year": year, "model_raw": cell.get("model_raw")}


def fix_s_class_2025(row: dict, ice_maps: dict) -> dict | None:
    ice = ice_maps.get("MERCEDES-BENZ") or {}
    cell = ice.get(("S450D4MATIC", 2025, "DIESEL"))
    mn = "S450D4MATIC"
    if not cell:
        # volume among S*D*
        hit = v45.best_hit_mercedes_class(ice, "S", 2025)
        if not hit:
            return None
        mn, ft, cell = hit
    else:
        ft = "DIESEL"
    truth.apply_hit_to_row(
        row, mn, ft, cell, 2025, force=True, update_consumption=True, allow_fuel_change=True
    )
    n = float(cell.get("n") or 0)
    # n=54 is below MIN_EEA_N_FOR_CONS — still label explicitly per review.
    row["sourceName"] = eea_source_label(2025, n, mn, cell.get("model_raw") or "S 450 d 4MATIC")
    row["confidenceScore"] = 0.55
    row["sourceUpdatedAt"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return {"eea_model": mn, "ft": ft, "n": n}


def relabel_prior_year_stima(rows: list[dict]) -> int:
    """Point 7: 'anno precedente' → 'da EEA IT {year}' with the real year."""
    n = 0
    pat = re.compile(
        r"(EEA co2cars IT (\d{4}) n=\d+(?:[^)]*)?) \(stima anno precedente\)",
        re.I,
    )
    compact = re.compile(r"stima\(anno precedente\)", re.I)
    plain = re.compile(r"stima anno precedente", re.I)
    for r in rows:
        sn = str(r.get("sourceName") or "")
        if "anno precedente" not in sn.lower():
            continue
        m = pat.search(sn)
        if m:
            r["sourceName"] = pat.sub(rf"\1 (da EEA IT {m.group(2)})", sn)
            n += 1
            continue
        if compact.search(sn):
            # seed+EEA-WLTP+stima(anno precedente) on YoY copies — cite prior calendar year.
            year = int(r.get("year") or 0)
            cite = year - 1 if year >= 2018 else year
            r["sourceName"] = compact.sub(f"stima(da EEA IT {cite})", sn)
            n += 1
            continue
        if plain.search(sn):
            ym = re.search(r"EEA(?: co2cars)? IT (\d{4})", sn, re.I)
            year = ym.group(1) if ym else str(int(r.get("year") or 0) - 1)
            r["sourceName"] = plain.sub(f"da EEA IT {year}", sn)
            n += 1
    return n


def reapply_2022_eea(rows: list[dict], ice_maps: dict, hev_maps: dict) -> list[dict]:
    """
    Fix 2022 source labels that cited doubled Ft case-buckets (DIESEL+diesel).

    Label-only when cited n == 2 × deduped cell n — do not rewrite consumption/bollo
    for the whole catalog. C-Class / Land Cruiser are force-corrected to the volume cell.
    """
    fixed: list[dict] = []
    drop = set(DROP_NO_IT_EEA) | set(DROP_PHEV_ONLY_NO_CS)
    n_pat = re.compile(r"^EEA co2cars IT 2022(?: (.+?))? n=(\d+)")
    for r in rows:
        if int(r.get("year") or 0) != 2022:
            continue
        if r.get("id") in drop:
            continue
        sn = str(r.get("sourceName") or "")
        m = n_pat.match(sn)
        if not m:
            continue
        cited = int(m.group(2))
        hit = truth.resolve_eea_hit(
            r, ice_maps, hev_maps, prefer_seed_fuel=True, volume_first=False
        )
        if not hit:
            hit = truth.resolve_eea_hit(
                r, ice_maps, hev_maps, volume_first=True, prefer_seed_fuel=False
            )
        if not hit:
            continue
        mn, ft, cell, ey = hit
        if ey != 2022:
            continue
        new_n = int(float(cell.get("n") or 0))
        if cited == new_n * 2 and new_n >= 1:
            r["sourceName"] = eea_source_label(2022, new_n, mn, cell.get("model_raw"))
            fixed.append(
                {"id": r.get("id"), "eea_model": mn, "n_from": cited, "n_to": new_n, "halved": True}
            )

    # Force the two review examples onto the correct volume cell (data + label).
    by_id = {str(r.get("id")): r for r in rows}
    for rid, key in (
        ("mercedes-benz-c-class-2022", ("C220D", 2022, "DIESEL")),
        ("toyota-land-cruiser-2022", ("LANDCRUISER150SERIES", 2022, "DIESEL")),
    ):
        r = by_id.get(rid)
        brand = "MERCEDES-BENZ" if "mercedes" in rid else "TOYOTA"
        cell = (ice_maps.get(brand) or {}).get(key)
        if not r or not cell:
            continue
        mn = key[0]
        truth.apply_hit_to_row(
            r, mn, key[2], cell, 2022, force=True, update_consumption=True, allow_fuel_change=True
        )
        r["sourceName"] = eea_source_label(2022, cell.get("n") or 0, mn, cell.get("model_raw"))
        r["confidenceScore"] = 0.8
        fixed.append(
            {
                "id": rid,
                "eea_model": mn,
                "n_from": None,
                "n_to": int(float(cell.get("n") or 0)),
                "halved": True,
                "forced": True,
            }
        )
    return fixed


def bump_metadata(rows: list[dict], report: dict) -> None:
    eea.bump_seed_version(NEW_SEED_VERSION)
    raw = truth.SEED_PATH.read_bytes()
    cdn = json.loads(truth.CDN_PATH.read_text(encoding="utf-8"))
    cdn["seedVersion"] = NEW_SEED_VERSION
    cdn["rows"] = len(rows)
    cdn["bytes"] = len(raw)
    cdn["updatedAt"] = datetime.now(timezone.utc).isoformat()
    cdn["note"] = (
        f"seedVersion {NEW_SEED_VERSION}: catalog-restore follow-up — drop no-IT-EEA years; "
        f"drop PHEV-only ICE seed litres; Scenic 2024 EV; S-Cross same-year; "
        f"Ft case dedupe (no DIESEL+diesel sum); da EEA IT year labels."
    )
    truth.CDN_PATH.write_text(json.dumps(cdn, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report["seedVersion"] = NEW_SEED_VERSION
    report["rows"] = len(rows)
    report["bytes"] = len(raw)


def main() -> int:
    rows: list[dict] = json.loads(truth.SEED_PATH.read_text(encoding="utf-8"))
    before = len(rows)
    ice_maps = truth.load_ice_maps()
    hev_maps = truth.load_hev_maps()

    report: dict = {
        "before": before,
        "dropped_no_it_eea": [],
        "dropped_phev_only": [],
        "scenic_2024_ev": None,
        "s_cross_fixed": [],
        "s_class_2025": None,
        "reapplied_2022": [],
        "relabeled_prior_year": 0,
        "intentional_exclusions": [],
    }

    have_ids = {str(r.get("id") or "") for r in rows}
    # Always document the review exclusions (even on re-run when already absent).
    for rid in DROP_NO_IT_EEA:
        report["intentional_exclusions"].append({"id": rid, "reason": NO_IT_REASON})
        if rid in have_ids:
            report["dropped_no_it_eea"].append({"id": rid, "reason": NO_IT_REASON})
    for rid in DROP_PHEV_ONLY_NO_CS:
        report["intentional_exclusions"].append({"id": rid, "reason": PHEV_ONLY_REASON})
        if rid in have_ids:
            report["dropped_phev_only"].append({"id": rid, "reason": PHEV_ONLY_REASON})

    drop_ids = set(DROP_NO_IT_EEA) | set(DROP_PHEV_ONLY_NO_CS)
    rows = [r for r in rows if str(r.get("id") or "") not in drop_ids]

    # Point 3 — Scenic 2024 EV
    for r in rows:
        if r.get("id") == "renault-scenic-2024":
            report["scenic_2024_ev"] = convert_scenic_2024_to_ev(r, ice_maps)
            break

    # Point 4 — S-Cross 2022/2023
    for r in rows:
        if r.get("id") in ("suzuki-s-cross-2022", "suzuki-s-cross-2023"):
            info = fix_s_cross_year(r, ice_maps)
            if info:
                report["s_cross_fixed"].append({"id": r["id"], **info})

    # Point 5 — S-Class 2025 label + cell
    for r in rows:
        if r.get("id") == "mercedes-benz-s-class-2025":
            report["s_class_2025"] = fix_s_class_2025(r, ice_maps)
            break

    # Point 6 — re-apply 2022 after Ft dedupe fix
    report["reapplied_2022"] = reapply_2022_eea(rows, ice_maps, hev_maps)

    # Point 7 — prior-year wording
    report["relabeled_prior_year"] = relabel_prior_year_stima(rows)

    # Keep Active Tourer rename if any slipped back
    v45.rename_bmw_2_active_tourer(rows)

    rows.sort(
        key=lambda x: (
            str(x.get("brand") or ""),
            str(x.get("model") or ""),
            int(x.get("year") or 0),
            str(x.get("id") or ""),
        )
    )

    refs = truth.build_refs(rows, ice_maps, hev_maps)
    truth.SEED_PATH.write_text(
        json.dumps(rows, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8"
    )
    # Also refresh bundled fixture copy used by unit tests.
    fixture = (
        truth.REPO
        / "EVforME?Tests"
        / "Fixtures"
        / "catalog_truth_eea_refs.json"
    )
    truth.REFS_PATH.write_text(json.dumps(refs, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if fixture.parent.is_dir():
        fixture.write_text(json.dumps(refs, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    bump_metadata(rows, report)
    report["after"] = len(rows)
    report["dropped_total"] = before - len(rows)
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    halved = sum(1 for x in report["reapplied_2022"] if x.get("halved"))
    print(
        f"catalog_restore_v46: {before} → {len(rows)} "
        f"drop_no_it={len(report['dropped_no_it_eea'])} "
        f"drop_phev={len(report['dropped_phev_only'])} "
        f"re2022={len(report['reapplied_2022'])} (halved_n={halved}) "
        f"relabel={report['relabeled_prior_year']}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
