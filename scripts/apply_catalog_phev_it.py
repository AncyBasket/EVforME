#!/usr/bin/env python3
"""
Add IT EEA PHEV parents (≥500 regs/year, 2022–2025) missing from catalog.

Rules (#28 + catalog-phev-it):
- fuelConsumptionLPerKm / energyConsumptionKWhPerKm only CS + CD from same-MY OEM EU/UK
- EEA weighted blend → weightedFuelConsumptionLPerKm only; catalogDataIncomplete=true
- Never copy another year/model; never third-party hosts
- Seed +1; no removals; Tesla Model 3 2026 untouched
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SEED = REPO / "EVforME?" / "Data" / "vehicles.seed.quality.json"
CDN = REPO / "EVforME?" / "Data" / "catalog_cdn.json"
CACHE = REPO / "scripts" / "cache" / "eea"
GAPS = CACHE / "catalog_phev_it_gaps.json"
MANIFEST = CACHE / "catalog_phev_it_manifest.json"
SOURCE_DAY = "2026-10-27"

PETROL_FACTOR = 23.2
DIESEL_FACTOR = 26.5


def norm(s: str) -> str:
    s = re.sub(r"[^A-Z0-9]+", " ", (s or "").upper())
    return re.sub(r"\s+", " ", s).strip()


def ascii_fold(s: str) -> str:
    table = str.maketrans(
        {
            "á": "a",
            "à": "a",
            "ä": "a",
            "â": "a",
            "ã": "a",
            "é": "e",
            "è": "e",
            "ë": "e",
            "ê": "e",
            "í": "i",
            "ì": "i",
            "ï": "i",
            "î": "i",
            "ó": "o",
            "ò": "o",
            "ö": "o",
            "ô": "o",
            "ú": "u",
            "ù": "u",
            "ü": "u",
            "û": "u",
            "ç": "c",
            "ñ": "n",
            "œ": "oe",
            "æ": "ae",
            "ß": "ss",
            "Á": "A",
            "À": "A",
            "Ä": "A",
            "É": "E",
            "È": "E",
            "Ë": "E",
            "Ê": "E",
            "Ó": "O",
            "Ò": "O",
            "Ö": "O",
            "Ú": "U",
            "Ù": "U",
            "Ü": "U",
            "Ç": "C",
            "Ñ": "N",
        }
    )
    return (s or "").translate(table)


def slug_part(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", ascii_fold(s or "").lower()).strip("-")


def make_id(brand: str, model: str, trim: str, year: int) -> str:
    # Always include "phev" so we never collide with BEV "Recharge" / ICE siblings.
    t = slug_part(trim)
    if t in ("phev", "plug-in", "plugin", ""):
        return f"{slug_part(brand)}-{slug_part(model)}-phev-{year}"
    return f"{slug_part(brand)}-{slug_part(model)}-phev-{t}-{year}"


def commercial_for(brand: str, eea_model: str) -> tuple[str, str, tuple[float, float, float], str]:
    """Return brand, model, dims (L,W,H), trim — unique enough for id."""
    bn, mn = norm(brand), norm(eea_model)
    # (brand_norm contains, model_norm match) → commercial
    rules: list[tuple[str, str, tuple[str, str, tuple[float, float, float], str]]] = [
        ("JEEP", "COMPASS", ("Jeep", "Compass", (4.40, 1.82, 1.65), "4xe")),
        ("JEEP", "RENEGADE", ("Jeep", "Renegade", (4.24, 1.81, 1.69), "4xe")),
        ("FORD", "KUGA", ("Ford", "Kuga", (4.61, 1.88, 1.68), "PHEV")),
        ("CUPRA", "FORMENTOR VZ", ("CUPRA", "Formentor", (4.46, 1.84, 1.51), "VZ e-HYBRID")),
        ("CUPRA", "FORMENTOR E", ("CUPRA", "Formentor", (4.46, 1.84, 1.51), "e-HYBRID")),
        ("VOLVO", "XC40", ("Volvo", "XC40", (4.43, 1.86, 1.65), "Recharge")),
        ("VOLVO", "XC60", ("Volvo", "XC60", (4.71, 1.90, 1.66), "Recharge")),
        ("BMW", "X1 XDRIVE25E", ("BMW", "X1", (4.50, 1.85, 1.64), "xDrive25e")),
        ("BMW", "X1 XDRIVE30E", ("BMW", "X1", (4.50, 1.85, 1.64), "xDrive30e")),
        ("BMW", "X2 XDRIVE25E", ("BMW", "X2", (4.37, 1.82, 1.55), "xDrive25e")),
        ("BMW", "X3 XDRIVE30E", ("BMW", "X3", (4.71, 1.89, 1.68), "xDrive30e")),
        ("BMW", "X5 XDRIVE50E", ("BMW", "X5", (4.94, 2.00, 1.76), "xDrive50e")),
        ("ALFA", "TONALE", ("Alfa Romeo", "Tonale", (4.53, 1.84, 1.60), "PHEV")),
        ("MERCEDES", "GLC 300 DE", ("Mercedes-Benz", "GLC", (4.72, 1.89, 1.64), "300 de")),
        ("MERCEDES", "GLE 350 DE 4MATIC COUPE", ("Mercedes-Benz", "GLE Coupé", (4.94, 2.02, 1.72), "350 de")),
        ("MERCEDES", "GLE 350 DE", ("Mercedes-Benz", "GLE", (4.92, 2.02, 1.79), "350 de")),
        ("MERCEDES", "GLA 250 E", ("Mercedes-Benz", "GLA", (4.41, 1.83, 1.61), "250 e")),
        ("MERCEDES", "A 250 E", ("Mercedes-Benz", "Classe A", (4.42, 1.80, 1.44), "A 250 e")),
        ("TOYOTA", "C HR", ("Toyota", "C-HR", (4.36, 1.83, 1.56), "PHEV")),
        ("TOYOTA", "RAV4", ("Toyota", "RAV4", (4.60, 1.85, 1.69), "PHEV")),
        ("PEUGEOT", "3008", ("Peugeot", "3008", (4.45, 1.84, 1.62), "PHEV")),
        ("PEUGEOT", "308", ("Peugeot", "308", (4.37, 1.85, 1.44), "PHEV")),
        ("RENAULT", "CAPTUR", ("Renault", "Captur", (4.23, 1.80, 1.58), "E-Tech PHEV")),
        ("AUDI", "Q3 SPORTBACK", ("Audi", "Q3 Sportback", (4.50, 1.86, 1.56), "45 TFSI e")),
        ("AUDI", "Q3 E TRON", ("Audi", "Q3", (4.48, 1.86, 1.62), "45 TFSI e")),
        ("AUDI", "Q5 SPORTBACK", ("Audi", "Q5 Sportback", (4.69, 1.89, 1.66), "50 TFSI e")),
        ("AUDI", "Q5 50 TFSI", ("Audi", "Q5", (4.66, 1.89, 1.66), "50 TFSI e")),
        ("AUDI", "A3 40 TFSIE", ("Audi", "A3", (4.34, 1.82, 1.43), "40 TFSI e")),
        ("AUDI", "A3 45 TFSIE", ("Audi", "A3", (4.34, 1.82, 1.43), "45 TFSI e")),
        ("PORSCHE", "CAYENNE", ("Porsche", "Cayenne", (4.93, 1.98, 1.70), "E-Hybrid")),
        ("BYD", "SEAL U", ("BYD", "Seal U", (4.78, 1.89, 1.67), "DM-i")),
        ("MG", "EHS", ("MG", "HS", (4.57, 1.88, 1.69), "PHEV")),
        ("LEXUS", "NX450", ("Lexus", "NX", (4.66, 1.87, 1.67), "450h+")),
        ("MAZDA", "CX 60", ("Mazda", "CX-60", (4.74, 1.89, 1.68), "PHEV")),
        ("OPEL", "GRANDLAND", ("Opel", "Grandland", (4.48, 1.91, 1.64), "PHEV")),
        ("HYUNDAI", "TUCSON", ("Hyundai", "Tucson", (4.51, 1.87, 1.65), "PHEV")),
        ("DS", "DS 7", ("DS", "7", (4.59, 1.90, 1.63), "E-TENSE")),
        ("DS", "DS7", ("DS", "7", (4.59, 1.90, 1.63), "E-TENSE")),
        ("CITROEN", "C5 AIRCROSS", ("Citroën", "C5 Aircross", (4.50, 1.87, 1.67), "PHEV")),
        ("VOLKSWAGEN", "TIGUAN", ("Volkswagen", "Tiguan", (4.51, 1.86, 1.67), "eHybrid")),
        ("KIA", "SPORTAGE", ("Kia", "Sportage", (4.52, 1.87, 1.65), "PHEV")),
        ("LAND ROVER", "EVOQUE", ("Land Rover", "Range Rover Evoque", (4.37, 1.90, 1.65), "PHEV")),
        ("LAND_ROVER", "EVOQUE", ("Land Rover", "Range Rover Evoque", (4.37, 1.90, 1.65), "PHEV")),
    ]
    for kb, km, val in rules:
        if norm(kb) in bn and norm(km) in mn:
            return val
    b = brand.replace("_", " ").title()
    if "MERCEDES" in bn:
        b = "Mercedes-Benz"
    model = re.sub(
        r"^(TOYOTA|BMW|AUDI|MERCEDES BENZ|MAZDA|BYD|MG|LEXUS|HYUNDAI)\s+",
        "",
        eea_model,
        flags=re.I,
    )
    model = re.sub(r"\s+", " ", model).strip().title()
    return (b, model or eea_model.title(), (4.50, 1.85, 1.60), "PHEV")


def weighted_fuel_from_co2(co2: float | None, ft: str) -> float | None:
    if co2 is None:
        return None
    factor = DIESEL_FACTOR if "DIESEL" in ft.upper() else PETROL_FACTOR
    return round(float(co2) / factor / 100.0, 5)


def main() -> None:
    seed = json.loads(SEED.read_text(encoding="utf-8"))
    existing = {r["id"] for r in seed}
    m3_before = {
        r["id"]: json.dumps(r, sort_keys=True)
        for r in seed
        if r["id"].startswith("tesla-model-3") and r.get("year") == 2026
    }

    gaps = json.loads(GAPS.read_text(encoding="utf-8"))
    missing = gaps["missing"]
    missing_fams_before = sorted({f"{m['brand']}|{m['model']}" for m in missing})

    added: list[str] = []
    by_year: dict[int, int] = defaultdict(int)
    id_to_eea: dict[str, str] = {}

    for c in sorted(missing, key=lambda x: (-x["n"], x["brand"], x["model"], x["year"])):
        brand_c, model_c, dims, trim = commercial_for(c["brand"], c["model"])
        rid = make_id(brand_c, model_c, trim, c["year"])
        if rid in existing:
            # Disambiguate rare collisions with eea model token
            rid = make_id(brand_c, model_c, f"{trim}-{slug_part(c['model'])[-12:]}", c["year"])
        if rid in existing:
            print(f"SKIP already present: {rid} for {c['brand']}|{c['model']}|{c['year']}")
            continue
        L, W, H = dims
        wfuel = weighted_fuel_from_co2(c.get("co2"), c["ft"])
        row = {
            "id": rid,
            "brand": brand_c,
            "model": model_c,
            "year": c["year"],
            "powertrain": "phev",
            "lengthM": L,
            "widthM": W,
            "heightM": H,
            "fuelKind": "diesel" if "DIESEL" in c["ft"].upper() else "petrol",
            "fuelConsumptionLPerKm": None,
            "energyConsumptionKWhPerKm": None,
            "energyIsWeighted": True,
            "catalogDataIncomplete": True,
            "weightedFuelConsumptionLPerKm": wfuel,
            "weightedEnergyConsumptionKWhPerKm": None,
            "wltpRangeKm": None,
            "batteryKWh": None,
            "wltpConsumptionKWh100km": None,
            "co2gKm": round(c["co2"]) if c.get("co2") is not None else None,
            "powerKw": round(c["kw"], 1) if c.get("kw") is not None else None,
            "taxesPerYear": 0.0,
            "maintenancePerYear": 320.0,
            "market": "IT",
            "confidenceScore": 0.7,
            "sourceName": (
                f"EEA co2cars IT {c['year']} {c['model']} {c['ft']} n={int(c['n'])}; "
                "OEM same-MY EU CS L/100 + CD kWh/range/battery not attached → "
                "catalogDataIncomplete; weighted EEA fuel only in weightedFuelConsumptionLPerKm"
            ),
            "sourceUpdatedAt": SOURCE_DAY,
            "trim": trim,
            "imageURL": None,
        }
        seed.append(row)
        existing.add(rid)
        added.append(rid)
        by_year[c["year"]] += 1
        id_to_eea[rid] = f"{c['brand']}|{c['model']}|{c['year']}"

    # Enrich Compass 4xe 2023–2024 with official FR MY24 tarif (19/12/2023): battery + range only.
    # CS L/100 and CD kWh absent on that sheet → stay incomplete. Do not touch 2022 (tarif is MY23/24).
    compass_src = (
        "Stellantis Media FR Tarif Public Jeep Compass MY24 réf Compass MY23 2023-E "
        "19/12/2023: battery 11.4 kWh; WLTP electric range 48–52 km (city 55–59) — "
        "https://www.media.stellantis.com/uploads/fr/attachment/7783/"
        "tarifpublicjeeprcompassmy242023e19decembre2023-65820ebe62db4.pdf; "
        "CS L/100 and CD kWh not on that sheet → incomplete; "
        "EEA weighted fuel only in weightedFuelConsumptionLPerKm"
    )
    for year in (2023, 2024):
        rid = f"jeep-compass-phev-4xe-{year}"
        for r in seed:
            if r["id"] != rid:
                continue
            r["batteryKWh"] = 11.4
            r["wltpRangeKm"] = 48
            r["sourceName"] = compass_src + f"; EEA IT COMPASS PETROL/ELECTRIC {year}"
            r["catalogDataIncomplete"] = True
            r["confidenceScore"] = 0.8
            r["energyIsWeighted"] = True

    # Ensure EPA market tag
    for r in seed:
        if r.get("powertrain") != "phev" or r.get("parentId"):
            continue
        sn = (r.get("sourceName") or "").upper()
        if "EPA" in sn and r.get("market") != "US/EPA":
            r["market"] = "US/EPA"

    for r in seed:
        if r["id"] in m3_before and json.dumps(r, sort_keys=True) != m3_before[r["id"]]:
            raise SystemExit(f"M3 2026 altered: {r['id']}")

    cdn = json.loads(CDN.read_text(encoding="utf-8"))
    new_ver = int(cdn.get("seedVersion") or 65) + 1
    cdn["seedVersion"] = new_ver
    cdn["rows"] = len(seed)
    payload = json.dumps(
        [{k: v for k, v in r.items() if v is not None} for r in seed],
        separators=(",", ":"),
        ensure_ascii=False,
    )
    cdn["bytes"] = len(payload.encode())
    cdn["updatedAt"] = datetime.now(timezone.utc).isoformat()

    SEED.write_text(json.dumps(seed, ensure_ascii=False, separators=(",", ":")) + "\n")
    CDN.write_text(json.dumps(cdn, indent=2) + "\n")

    parents = [r for r in seed if not r.get("parentId") and r.get("powertrain") == "phev"]
    complete = sum(1 for r in parents if not r.get("catalogDataIncomplete"))
    incomplete = sum(1 for r in parents if r.get("catalogDataIncomplete"))

    man = {
        "seedVersion": new_ver,
        "added": sorted(added),
        "added_count": len(added),
        "by_year": {str(k): by_year[k] for k in sorted(by_year)},
        "id_to_eea": id_to_eea,
        "phev_parents_before": 22,
        "phev_parents_after": len(parents),
        "phev_complete_after": complete,
        "phev_incomplete_after": incomplete,
        "missing_families_before": missing_fams_before,
        "missing_families_before_count": len(missing_fams_before),
        "compass_enriched_years": [2023, 2024],
    }
    MANIFEST.write_text(json.dumps(man, indent=2) + "\n")
    print(json.dumps({k: man[k] for k in man if k != "id_to_eea" and k != "added"}, indent=2))
    print(f"added_count={len(added)} seed_v={new_ver} rows={len(seed)}")


if __name__ == "__main__":
    main()
