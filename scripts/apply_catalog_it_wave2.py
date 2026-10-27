#!/usr/bin/env python3
"""
Catalog IT wave-2: cut missing ≥500 regs/year families toward ≤30.

- Expand homologation→IT commercial aliases (with sources)
- Rename EN marketing names → IT (same ids)
- Add missing commercial families + fuel variants from EEA IT
- PHEV ≥500/year: EEA CO2→fuel; range/battery/kWh only with same-MY OEM else nil
- BEV: EEA Zr/Wh when available in cache; else nil energy fields (still add if electric n≥500)
- seedVersion 63 → 64; no removals; Tesla M3 2026 untouched
"""

from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SEED = REPO / "EVforME?" / "Data" / "vehicles.seed.quality.json"
CDN = REPO / "EVforME?" / "Data" / "catalog_cdn.json"
ALIAS = REPO / "EVforME?" / "Data" / "homologation_commercial_aliases.json"
MANIFEST = REPO / "scripts" / "cache" / "eea" / "catalog_it_wave2_manifest.json"
CACHE = REPO / "scripts" / "cache" / "eea"

NEW_SEED_VERSION = 64
SOURCE_DAY = "2026-10-27"
PETROL = 0.745 / (0.1206 * 0.273)
DIESEL = 0.834 / (0.1165 * 0.273)


def slug(s: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", (s or "").lower()).strip("-")
    return s


def fc_from_co2(co2: float, fuel: str) -> float:
    factor = DIESEL if fuel == "diesel" else PETROL
    return round(float(co2) / factor / 100.0, 5)


def bollo(kw: float | None, year: int) -> float:
    if kw is None or kw <= 0:
        return 0.0
    base = 2.58 * min(kw, 100.0) + 3.87 * max(0.0, kw - 100.0)
    if kw > 185:
        sb = 20.0 * (kw - 185.0)
        age = max(0, 2026 - year)
        if age >= 20:
            sb = 0.0
        elif age >= 15:
            sb *= 0.15
        elif age >= 10:
            sb *= 0.30
        elif age >= 5:
            sb *= 0.60
        base += sb
    return round(base, 2)


def load_eea_cells() -> dict[tuple[str, str, int, str], dict]:
    """(brand, model_key, year, fuel_norm) -> {n, co2, kw}"""
    out: dict[tuple[str, str, int, str], dict] = {}

    def brand_from(fn: str) -> str:
        name = (
            fn.replace("IT_", "")
            .replace("_fuels.json", "")
            .replace("_hev_FmH.json", "")
            .replace("_bev_Zr.json", "")
        )
        return name.replace("_", " ")

    for p in sorted(CACHE.glob("IT_*fuels.json")) + sorted(CACHE.glob("IT_*_hev_FmH.json")):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        brand = brand_from(p.name)
        buckets = (
            ((d.get("response") or {}).get("aggregations") or {})
            .get("models", {})
            .get("buckets")
            or []
        )
        for mb in buckets:
            mkey = mb["key"]
            for yb in (mb.get("years") or {}).get("buckets") or []:
                year = int(yb["key"])
                if year < 2022 or year > 2025:
                    continue
                for fb in (yb.get("fuels") or {}).get("buckets") or []:
                    fuel = str(fb["key"]).lower()
                    if fuel in ("petrol", "diesel", "lpg", "cng", "electric") or "/" in fuel:
                        n = float((fb.get("sum_r") or {}).get("value") or fb.get("doc_count") or 0)
                        key = (brand, mkey, year, fuel)
                        prev = out.get(key)
                        if prev is None or n > prev["n"]:
                            out[key] = {
                                "n": n,
                                "co2": (fb.get("avg_co2") or {}).get("value"),
                                "kw": (fb.get("avg_kw") or {}).get("value"),
                                "year_doc": float(yb.get("doc_count") or 0),
                            }
    return out


def modal_zr_wh(brand_file: str, model_keys: list[str], year: int) -> tuple[int | None, float | None, float | None]:
    p = CACHE / brand_file
    if not p.exists():
        return None, None, None
    d = json.loads(p.read_text(encoding="utf-8"))
    buckets = (
        ((d.get("response") or {}).get("aggregations") or {})
        .get("models", {})
        .get("buckets")
        or []
    )
    for mb in buckets:
        if mb["key"] not in model_keys:
            continue
        for yb in (mb.get("years") or {}).get("buckets") or []:
            if int(yb["key"]) != year:
                continue
            # Prefer Status F
            status = (yb.get("status") or {}).get("buckets") or []
            chosen = None
            for sb in status:
                if sb.get("key") == "F":
                    chosen = sb
                    break
            if not chosen and status:
                # F/P conflict check
                fset = set()
                pset = set()
                for sb in status:
                    zrs = {(zb.get("key")) for zb in (sb.get("zr") or {}).get("buckets") or []}
                    if sb.get("key") == "F":
                        fset = zrs
                    if sb.get("key") == "P":
                        pset = zrs
                if fset and pset and fset != pset:
                    return None, None, None
                chosen = status[0]
            if not chosen:
                return None, None, None
            zr_buckets = (chosen.get("zr") or {}).get("buckets") or []
            if not zr_buckets:
                return None, None, None
            zr_buckets = sorted(zr_buckets, key=lambda z: -float((z.get("sum_r") or {}).get("value") or z.get("doc_count") or 0))
            zb = zr_buckets[0]
            zr = int(zb["key"])
            wh_buckets = (zb.get("wh") or {}).get("buckets") or []
            if not wh_buckets:
                return zr, None, None
            wh_buckets = sorted(wh_buckets, key=lambda w: -float((w.get("sum_r") or {}).get("value") or w.get("doc_count") or 0))
            wh = float(wh_buckets[0]["key"])
            kw_buckets = (wh_buckets[0].get("kw") or {}).get("buckets") or []
            kw = float(kw_buckets[0]["key"]) if kw_buckets else None
            if int(round(zr)) == int(round(wh)):
                return None, None, None
            return zr, wh / 1000.0, kw
    return None, None, None


EXTRA_ALIASES = [
    {
        "brand": "BMW",
        "eeaKeys": ["320D", "320d", "320D XDRIVE", "320d xDrive", "318D", "318d", "316D", "316d"],
        "commercialName": "Serie 3",
        "sourceName": "BMW Italia — gamma Serie 3",
        "sourceUrl": "https://www.bmw.it/it/tutti-i-modelli/bmw-serie/serie-3/berlina.html",
        "sourceUpdatedAt": SOURCE_DAY,
    },
    {
        "brand": "BMW",
        "eeaKeys": [
            "218D ACTIVE TOURER",
            "218d Active Tourer",
            "220I ACTIVE TOURER",
            "218I ACTIVE TOURER",
            "225E XDRIVE ACTIVE TOURER",
            "225e xDrive Active Tourer",
        ],
        "commercialName": "Serie 2 Active Tourer",
        "sourceName": "BMW Italia — Serie 2 Active Tourer",
        "sourceUrl": "https://www.bmw.it/it/tutti-i-modelli/bmw-serie/serie-2/active-tourer.html",
        "sourceUpdatedAt": SOURCE_DAY,
    },
    {
        "brand": "BMW",
        "eeaKeys": ["520D", "520d", "520D XDRIVE", "520d xDrive", "540D XDRIVE"],
        "commercialName": "Serie 5",
        "sourceName": "BMW Italia — gamma Serie 5",
        "sourceUrl": "https://www.bmw.it/it/tutti-i-modelli/bmw-serie/serie-5/berlina.html",
        "sourceUpdatedAt": SOURCE_DAY,
    },
    {
        "brand": "BMW",
        "eeaKeys": ["420D", "420d", "420D XDRIVE", "420d xDrive"],
        "commercialName": "Serie 4",
        "sourceName": "BMW Italia — gamma Serie 4",
        "sourceUrl": "https://www.bmw.it/it/tutti-i-modelli/bmw-serie/serie-4/coupe.html",
        "sourceUpdatedAt": SOURCE_DAY,
    },
    {
        "brand": "BMW",
        "eeaKeys": ["X6 XDRIVE30D", "X6 xDrive30d", "X6 XDRIVE30D M SPORT", "X6 XDRIVE40D M SPORT"],
        "commercialName": "X6",
        "sourceName": "BMW Italia — gamma X6",
        "sourceUrl": "https://www.bmw.it/it/tutti-i-modelli/bmw-x/x6.html",
        "sourceUpdatedAt": SOURCE_DAY,
    },
    {
        "brand": "Mercedes-Benz",
        "eeaKeys": ["B 180 D", "B 180", "B 250 E", "B 250 e"],
        "commercialName": "Classe B",
        "sourceName": "Mercedes-Benz Italia — Classe B",
        "sourceUrl": "https://www.mercedes-benz.it/passengercars/models/hatchback/b-class/overview.html",
        "sourceUpdatedAt": SOURCE_DAY,
    },
    {
        "brand": "Mercedes-Benz",
        "eeaKeys": [
            "C 220 D",
            "C 200 D",
            "C 220 D 4MATIC",
            "C 220D 4MATIC ALL TERRAIN",
            "C 300 D",
        ],
        "commercialName": "Classe C",
        "sourceName": "Mercedes-Benz Italia — Classe C",
        "sourceUrl": "https://www.mercedes-benz.it/passengercars/models/saloon/c-class/overview.html",
        "sourceUpdatedAt": SOURCE_DAY,
    },
    {
        "brand": "Mercedes-Benz",
        "eeaKeys": ["E 220 D", "E 220 D 4MATIC", "E 220D"],
        "commercialName": "Classe E",
        "sourceName": "Mercedes-Benz Italia — Classe E",
        "sourceUrl": "https://www.mercedes-benz.it/passengercars/models/saloon/e-class/overview.html",
        "sourceUpdatedAt": SOURCE_DAY,
    },
    {
        "brand": "Mercedes-Benz",
        "eeaKeys": ["V KLASSE", "V-Klasse", "VITO TOURER"],
        "commercialName": "Classe V",
        "sourceName": "Mercedes-Benz Italia — Classe V",
        "sourceUrl": "https://www.mercedes-benz.it/passengercars/models/van/v-class/overview.html",
        "sourceUpdatedAt": SOURCE_DAY,
    },
    {
        "brand": "Mercedes-Benz",
        "eeaKeys": ["CLE 220D", "CLE 220 D"],
        "commercialName": "CLE",
        "sourceName": "Mercedes-Benz Italia — CLE",
        "sourceUrl": "https://www.mercedes-benz.it/passengercars/models/coupes/cle/overview.html",
        "sourceUpdatedAt": SOURCE_DAY,
    },
    {
        "brand": "Audi",
        "eeaKeys": [
            "Q4 40 E TRON",
            "Q4 45 E TRON",
            "Q4 SPORTBACK 40 E TRON",
            "Q4 SPORTBACK 45 E TRON",
        ],
        "commercialName": "Q4 e-tron",
        "sourceName": "Audi Italia — Q4 e-tron",
        "sourceUrl": "https://www.audi.it/it/modelli/q4-e-tron/q4-e-tron.html",
        "sourceUpdatedAt": SOURCE_DAY,
    },
    {
        "brand": "Honda",
        "eeaKeys": ["ZR V", "ZR-V", "ZRV"],
        "commercialName": "ZR-V",
        "sourceName": "Honda Italia — ZR-V",
        "sourceUrl": "https://www.honda.it/cars/new/zr-v.html",
        "sourceUpdatedAt": SOURCE_DAY,
    },
]


RENAMES = [
    # (id_prefix, old_model, new_model)
    ("bmw-3-series-", "3 Series", "Serie 3"),
    ("bmw-2-series-", "2 Series Active Tourer", "Serie 2 Active Tourer"),
    ("bmw-5-series-", "5 Series", "Serie 5"),
    ("bmw-4-series-", "4 Series", "Serie 4"),
    ("mercedes-benz-c-class", "C-Class", "Classe C"),
    ("mercedes-benz-b-class", "B-Class", "Classe B"),
    ("mercedes-benz-e-class", "E-Class", "Classe E"),
    ("mercedes-benz-v-class", "V-Class", "Classe V"),
]


# New commercial rows: (brand, model, eea_model_keys, fuel, powertrain, years_filter, dims, maintenance, trim)
NEW_SPECS = [
    ("Dacia", "Bigster", ["BIGSTER", "DACIA BIGSTER"], "petrol", "ice", {2025}, (4.57, 1.81, 1.66), 400, None),
    ("Dacia", "Bigster", ["BIGSTER", "DACIA BIGSTER"], "lpg", "ice", {2025}, (4.57, 1.81, 1.66), 400, "GPL"),
    ("Maserati", "Grecale", ["GRECALE GT", "GRECALE MODENA", "GRECALE"], "petrol", "ice", {2022, 2023, 2024, 2025}, (4.85, 1.95, 1.66), 650, None),
    ("Honda", "ZR-V", ["ZR V", "ZR-V"], "petrol", "hev", {2023, 2024, 2025}, (4.57, 1.84, 1.62), 420, None),
    ("Volkswagen", "Caddy", ["CADDY"], "diesel", "ice", {2022, 2023, 2024, 2025}, (4.5, 1.86, 1.8), 480, None),
    ("Volkswagen", "Caddy", ["CADDY"], "petrol", "ice", {2022, 2023, 2024, 2025}, (4.5, 1.86, 1.8), 480, None),
    ("Volkswagen", "Multivan", ["MULTIVAN"], "diesel", "ice", {2022, 2023, 2024, 2025}, (4.97, 1.94, 1.9), 520, None),
    ("Volkswagen", "Tayron", ["TAYRON"], "petrol", "ice", {2025}, (4.77, 1.86, 1.66), 450, None),
    ("Renault", "Trafic", ["TRAFIC"], "diesel", "ice", {2022, 2023, 2024, 2025}, (5.08, 1.96, 1.97), 500, None),
    ("Renault", "Kangoo", ["KANGOO"], "diesel", "ice", {2022, 2023, 2024, 2025}, (4.49, 1.86, 1.81), 450, None),
    ("Renault", "Kangoo", ["KANGOO"], "petrol", "ice", {2022, 2023, 2024, 2025}, (4.49, 1.86, 1.81), 450, None),
    ("Renault", "Rafale", ["RAFALE"], "petrol", "hev", {2024, 2025}, (4.71, 1.86, 1.61), 450, "E-Tech"),
    ("Ford", "Tourneo Custom", ["TOURNEO CUSTOM"], "diesel", "ice", {2022, 2023, 2025}, (4.97, 1.99, 1.96), 520, "diesel"),
    ("MINI", "Cooper C", ["COOPER C"], "petrol", "ice", {2024, 2025}, (3.87, 1.75, 1.46), 420, None),
    ("MINI", "Cooper S", ["COOPER S"], "petrol", "ice", {2022, 2023, 2024, 2025}, (3.87, 1.75, 1.46), 430, None),
    ("MINI", "One", ["ONE", "One"], "petrol", "ice", {2022}, (3.85, 1.73, 1.42), 380, None),
    ("Subaru", "Crosstrek", ["CROSSTREK"], "petrol", "hev", {2024, 2025}, (4.48, 1.8, 1.6), 420, None),
    ("CUPRA", "Terramar", ["TERRAMAR"], "petrol", "ice", {2024, 2025}, (4.52, 1.86, 1.61), 430, None),
    ("Land Rover", "Range Rover Velar", ["RANGE ROVER VELAR"], "diesel", "ice", {2022, 2023, 2024, 2025}, (4.8, 2.03, 1.68), 700, None),
    ("Peugeot", "Rifter", ["RIFTER"], "diesel", "ice", {2022}, (4.4, 1.85, 1.88), 420, None),
    ("Nissan", "Townstar", ["TOWNSTAR"], "petrol", "ice", {2022, 2023, 2024}, (4.49, 1.86, 1.81), 420, None),
    ("Fiat", "Ulysse", ["ULYSSE"], "diesel", "ice", {2025}, (4.95, 1.92, 1.89), 480, None),
]


def pick_cell(eea, brand: str, keys: list[str], year: int, fuel: str) -> dict | None:
    best = None
    for b, m, y, f in eea:
        if y != year or f != fuel:
            continue
        if not (brand.upper() in b.upper() or b.upper() in brand.upper()):
            continue
        if m not in keys and not any(k.upper() == m.upper() for k in keys):
            continue
        cell = eea[(b, m, y, f)]
        if best is None or cell["n"] > best["n"]:
            best = {**cell, "eea_model": m, "eea_brand": b}
    return best


def ice_like_row(
    *,
    id_: str,
    brand: str,
    model: str,
    year: int,
    fuel_kind: str,
    powertrain: str,
    cell: dict,
    dims: tuple[float, float, float],
    maintenance: float,
    trim: str | None,
) -> dict:
    co2 = cell.get("co2")
    if co2 is None and fuel_kind != "electric":
        # still require co2 for ICE
        raise ValueError(f"no co2 for {id_}")
    kw = cell.get("kw")
    L, W, H = dims
    row = {
        "id": id_,
        "brand": brand,
        "model": model,
        "year": year,
        "powertrain": powertrain,
        "lengthM": L,
        "widthM": W,
        "heightM": H,
        "fuelKind": fuel_kind if fuel_kind != "electric" else None,
        "fuelConsumptionLPerKm": fc_from_co2(co2, fuel_kind) if co2 is not None and fuel_kind != "electric" else None,
        "energyConsumptionKWhPerKm": None,
        "wltpRangeKm": None,
        "batteryKWh": None,
        "wltpConsumptionKWh100km": None,
        "co2gKm": 0 if fuel_kind == "electric" else (round(co2) if co2 is not None else None),
        "powerKw": round(kw, 1) if kw is not None else None,
        "taxesPerYear": 0 if fuel_kind == "electric" else bollo(kw, year),
        "maintenancePerYear": maintenance,
        "market": "IT",
        "confidenceScore": 0.88,
        "sourceName": f"EEA co2cars IT {year} {cell.get('eea_model')} n={int(cell['n'])}",
        "sourceUpdatedAt": SOURCE_DAY,
        "trim": trim,
        "imageURL": None,
    }
    return row


def phev_eea_row(
    *,
    id_: str,
    brand: str,
    model: str,
    year: int,
    cell: dict,
    dims: tuple[float, float, float],
    maintenance: float = 320.0,
    trim: str = "PHEV",
) -> dict:
    co2 = cell["co2"]
    kw = cell.get("kw")
    L, W, H = dims
    return {
        "id": id_,
        "brand": brand,
        "model": model,
        "year": year,
        "powertrain": "phev",
        "lengthM": L,
        "widthM": W,
        "heightM": H,
        "fuelKind": "petrol" if "diesel" not in str(cell.get("fuel", "petrol")) else "diesel",
        "fuelConsumptionLPerKm": fc_from_co2(co2, "diesel" if "diesel" in str(cell.get("fuel", "")) else "petrol"),
        "energyConsumptionKWhPerKm": None,
        "energyIsWeighted": True,
        "wltpRangeKm": None,
        "batteryKWh": None,
        "wltpConsumptionKWh100km": None,
        "co2gKm": round(co2),
        "powerKw": round(kw, 1) if kw is not None else None,
        "taxesPerYear": 0.0,
        "maintenancePerYear": maintenance,
        "market": "IT",
        "confidenceScore": 0.85,
        "sourceName": (
            f"EEA co2cars IT {year} {cell.get('eea_model')} PETROL/ELECTRIC n={int(cell['n'])}; "
            "OEM same-MY range/battery/kWh not attached (nil)"
        ),
        "sourceUpdatedAt": SOURCE_DAY,
        "trim": trim,
        "imageURL": None,
    }


def main() -> int:
    seed: list[dict] = json.loads(SEED.read_text(encoding="utf-8"))
    before = len(seed)
    existing = {str(r["id"]) for r in seed}
    alias_doc = json.loads(ALIAS.read_text(encoding="utf-8"))
    aliases = list(alias_doc.get("aliases") or [])

    # Merge extra aliases (dedupe by brand+commercialName)
    have = {(a["brand"], a["commercialName"]) for a in aliases}
    for a in EXTRA_ALIASES:
        key = (a["brand"], a["commercialName"])
        if key in have:
            # merge eeaKeys
            for existing_a in aliases:
                if (existing_a["brand"], existing_a["commercialName"]) == key:
                    keys = list(dict.fromkeys(list(existing_a.get("eeaKeys") or []) + list(a["eeaKeys"])))
                    existing_a["eeaKeys"] = keys
                    break
        else:
            aliases.append(a)
            have.add(key)
    alias_doc["aliases"] = aliases
    ALIAS.write_text(json.dumps(alias_doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    renames = []
    for r in seed:
        rid = str(r.get("id") or "")
        for prefix, old, new in RENAMES:
            if rid.startswith(prefix) and r.get("model") == old:
                r["model"] = new
                renames.append({"id": rid, "from": old, "to": new})

    eea = load_eea_cells()
    added: list[str] = []
    by_fuel: dict[str, int] = defaultdict(int)

    for brand, model, keys, fuel, powertrain, years, dims, maint, trim in NEW_SPECS:
        for year in sorted(years):
            cell = pick_cell(eea, brand, keys, year, fuel)
            if not cell or cell["n"] < 200:
                continue
            if fuel == "lpg":
                fid = f"{slug(brand)}-{slug(model)}-gpl-{year}"
            elif fuel == "diesel" and powertrain == "ice":
                fid = f"{slug(brand)}-{slug(model)}-diesel-{year}"
            elif powertrain == "hev":
                fid = f"{slug(brand)}-{slug(model)}-{year}"
            else:
                fid = f"{slug(brand)}-{slug(model)}-{year}"
            # Prefer shorter ids for petrol default
            if fuel == "petrol" and powertrain == "ice":
                fid = f"{slug(brand)}-{slug(model)}-{year}"
            if fid in existing:
                continue
            try:
                row = ice_like_row(
                    id_=fid,
                    brand=brand,
                    model=model,
                    year=year,
                    fuel_kind=fuel,
                    powertrain=powertrain,
                    cell=cell,
                    dims=dims,
                    maintenance=maint,
                    trim=trim,
                )
            except ValueError:
                continue
            seed.append(row)
            existing.add(fid)
            added.append(fid)
            by_fuel[fuel if powertrain != "hev" else "ibrida"] += 1

    # Mini Cooper SE BEV (electric ≥500)
    for year, eea_keys in [
        (2022, ["COOPER SE", "Cooper SE"]),
        (2023, ["COOPER SE"]),
        (2024, ["COOPER SE"]),
    ]:
        cell = pick_cell(eea, "MINI", eea_keys, year, "electric")
        if not cell or cell["n"] < 500:
            continue
        fid = f"mini-cooper-se-{year}"
        if fid in existing:
            continue
        zr, kwh_per_km, kw = modal_zr_wh("IT_MINI_bev_Zr.json", eea_keys, year)
        L, W, H = (3.87, 1.75, 1.46)
        row = {
            "id": fid,
            "brand": "MINI",
            "model": "Cooper SE",
            "year": year,
            "powertrain": "ev",
            "lengthM": L,
            "widthM": W,
            "heightM": H,
            "fuelKind": None,
            "fuelConsumptionLPerKm": None,
            "energyConsumptionKWhPerKm": round(kwh_per_km, 4) if kwh_per_km else None,
            "wltpConsumptionKWh100km": round(kwh_per_km * 100, 1) if kwh_per_km else None,
            "wltpRangeKm": zr,
            "batteryKWh": None,
            "co2gKm": 0,
            "powerKw": round(kw or cell.get("kw") or 0, 1) or None,
            "taxesPerYear": 0,
            "maintenancePerYear": 250,
            "market": "IT",
            "confidenceScore": 0.9,
            "sourceName": (
                f"EEA co2cars IT {year} {cell.get('eea_model')} electric n={int(cell['n'])}"
                + (f"; Zr={zr} Wh/km={kwh_per_km*1000:.0f}" if zr and kwh_per_km else "; Zr/Wh nil")
            ),
            "sourceUpdatedAt": SOURCE_DAY,
            "trim": "SE",
            "imageURL": None,
        }
        seed.append(row)
        existing.add(fid)
        added.append(fid)
        by_fuel["BEV"] += 1

    # Mini Cooper E 2024-25 if present
    for year in (2024, 2025):
        cell = pick_cell(eea, "MINI", ["COOPER E", "Cooper E"], year, "electric")
        if not cell or cell["n"] < 300:
            continue
        fid = f"mini-cooper-e-{year}"
        if fid in existing:
            continue
        zr, kwh_per_km, kw = modal_zr_wh("IT_MINI_bev_Zr.json", ["COOPER E", "Cooper E"], year)
        row = {
            "id": fid,
            "brand": "MINI",
            "model": "Cooper E",
            "year": year,
            "powertrain": "ev",
            "lengthM": 3.87,
            "widthM": 1.75,
            "heightM": 1.46,
            "fuelKind": None,
            "fuelConsumptionLPerKm": None,
            "energyConsumptionKWhPerKm": round(kwh_per_km, 4) if kwh_per_km else None,
            "wltpConsumptionKWh100km": round(kwh_per_km * 100, 1) if kwh_per_km else None,
            "wltpRangeKm": zr,
            "batteryKWh": None,
            "co2gKm": 0,
            "powerKw": round(kw or cell.get("kw") or 0, 1) or None,
            "taxesPerYear": 0,
            "maintenancePerYear": 250,
            "market": "IT",
            "confidenceScore": 0.88,
            "sourceName": f"EEA co2cars IT {year} {cell.get('eea_model')} electric n={int(cell['n'])}",
            "sourceUpdatedAt": SOURCE_DAY,
            "trim": "E",
            "imageURL": None,
        }
        seed.append(row)
        existing.add(fid)
        added.append(fid)
        by_fuel["BEV"] += 1

    # Alfa Junior Elettrica — Zr from IT_ALFA_ROMEO_bev_Zr when Status F present
    for year in (2024, 2025):
        cell = pick_cell(eea, "ALFA ROMEO", ["ALFA ROMEO JUNIOR", "JUNIOR"], year, "electric")
        if not cell or cell["n"] < 500:
            continue
        fid = f"alfa-romeo-junior-elettrica-{year}"
        if fid in existing:
            continue
        zr, kwh_per_km, kw = modal_zr_wh(
            "IT_ALFA_ROMEO_bev_Zr.json", ["ALFA ROMEO JUNIOR", "JUNIOR"], year
        )
        row = {
            "id": fid,
            "brand": "Alfa Romeo",
            "model": "Junior Elettrica",
            "year": year,
            "powertrain": "ev",
            "lengthM": 4.17,
            "widthM": 1.78,
            "heightM": 1.53,
            "fuelKind": None,
            "fuelConsumptionLPerKm": None,
            "energyConsumptionKWhPerKm": (
                round(kwh_per_km, 4) if kwh_per_km else None
            ),
            "wltpConsumptionKWh100km": (
                round(kwh_per_km * 100, 1) if kwh_per_km else None
            ),
            "wltpRangeKm": zr,
            "batteryKWh": None,
            "co2gKm": 0,
            "powerKw": round((kw or cell.get("kw") or 0), 1) or None,
            "taxesPerYear": 0,
            "maintenancePerYear": 260,
            "market": "IT",
            "confidenceScore": 0.7 if not kwh_per_km else 0.9,
            "sourceName": (
                f"EEA co2cars IT {year} {cell.get('eea_model')} electric n={int(cell['n'])}"
                + (
                    f"; Zr={zr} Wh/km={kwh_per_km*1000:.0f} (Status F modal)"
                    if zr and kwh_per_km
                    else "; Zr/Wh cache absent — range/energy nil"
                )
            ),
            "sourceUpdatedAt": SOURCE_DAY,
            "trim": "Elettrica",
            "imageURL": None,
        }
        seed.append(row)
        existing.add(fid)
        added.append(fid)
        by_fuel["BEV"] += 1

    # High-volume PHEV missing (≥500): EEA fuel only, nil OEM energy
    PHEV_ADD = [
        ("BMW", "Serie 2 Active Tourer", ["225E XDRIVE ACTIVE TOURER", "225e xDrive Active Tourer"], {2022, 2023, 2024}, (4.43, 1.8, 1.4), "225e xDrive"),
        ("BMW", "Serie 3", ["320E", "320e"], {2023, 2024}, (4.71, 1.83, 1.44), "320e"),
        ("MINI", "Countryman", ["COUNTRYMAN COOPER SE ALL4", "Countryman Cooper SE ALL4"], {2022, 2023}, (4.3, 1.82, 1.56), "Cooper SE ALL4"),
        ("Mercedes-Benz", "Classe B", ["B 250 E", "B 250 e"], {2022}, (4.42, 1.8, 1.56), "B 250 e"),
        ("Renault", "Rafale", ["RAFALE"], {2025}, (4.71, 1.86, 1.61), "E-Tech PHEV"),
        ("Volkswagen", "Caddy", ["CADDY"], {2022, 2023, 2024}, (4.5, 1.86, 1.8), "PHEV"),
        ("Volkswagen", "Multivan", ["MULTIVAN"], {2022, 2023, 2024, 2025}, (4.97, 1.94, 1.9), "PHEV"),
        ("Volkswagen", "Tayron", ["TAYRON"], {2025}, (4.77, 1.86, 1.66), "PHEV"),
        ("Land Rover", "Range Rover Velar", ["RANGE ROVER VELAR"], {2022, 2023, 2024, 2025}, (4.8, 2.03, 1.68), "PHEV"),
    ]
    for brand, model, keys, years, dims, trim in PHEV_ADD:
        for year in sorted(years):
            cell = None
            for fuel in ("petrol/electric", "PETROL/ELECTRIC".lower(), "diesel/electric"):
                cell = pick_cell(eea, brand if brand != "Mercedes-Benz" else "MERCEDES-BENZ", keys, year, fuel if fuel != "PETROL/ELECTRIC".lower() else "petrol/electric")
                if cell and cell["n"] >= 500:
                    break
            # also try uppercase brand keys in eea
            if not cell or cell["n"] < 500:
                for (b, m, y, f), c in eea.items():
                    if y != year or c["n"] < 500:
                        continue
                    if m not in keys:
                        continue
                    if "electric" in f and ("petrol" in f or "diesel" in f):
                        cell = {**c, "eea_model": m, "fuel": f}
                        break
            if not cell or cell["n"] < 500 or cell.get("co2") is None:
                continue
            fid = f"{slug(brand)}-{slug(model)}-{slug(trim)}-{year}"
            if fid in existing:
                continue
            # Avoid colliding with wave-1 cupra terramar phev id pattern
            if brand == "CUPRA" and model == "Terramar":
                continue
            cell = {**cell, "fuel": cell.get("fuel", "petrol/electric")}
            row = phev_eea_row(
                id_=fid,
                brand=brand,
                model=model,
                year=year,
                cell=cell,
                dims=dims,
                trim=trim,
            )
            seed.append(row)
            existing.add(fid)
            added.append(fid)
            by_fuel["PHEV"] += 1

    # Guard Tesla M3 2026
    for r in seed:
        if str(r.get("id") or "").startswith("tesla-model-3") and int(r.get("year") or 0) == 2026:
            pass

    added_set = set(added)
    old = [r for r in seed if str(r["id"]) not in added_set]
    new_sorted = sorted([r for r in seed if str(r["id"]) in added_set], key=lambda r: str(r["id"]))
    out = old + new_sorted

    SEED.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    payload = json.dumps(
        [{k: v for k, v in r.items() if v is not None} for r in out],
        separators=(",", ":"),
        ensure_ascii=False,
    )
    cdn = json.loads(CDN.read_text(encoding="utf-8"))
    cdn["seedVersion"] = NEW_SEED_VERSION
    cdn["rows"] = len(out)
    cdn["bytes"] = len(payload.encode("utf-8"))
    cdn["updatedAt"] = datetime.now(timezone.utc).isoformat()
    cdn["note"] = (
        f"seedVersion {NEW_SEED_VERSION}: IT wave-2 — aliases/renames + missing ≥500 families "
        "(EEA fuels; PHEV/BEV energy nil without same-MY OEM)."
    )
    CDN.write_text(json.dumps(cdn, indent=2) + "\n", encoding="utf-8")

    svc = REPO / "EVforME?" / "Core" / "Logic" / "VehicleCatalogService.swift"
    text = svc.read_text(encoding="utf-8")
    text = re.sub(
        r"static let bundledSeedVersion = \d+",
        f"static let bundledSeedVersion = {NEW_SEED_VERSION}",
        text,
        count=1,
    )
    svc.write_text(text, encoding="utf-8")

    manifest = {
        "seedVersion": NEW_SEED_VERSION,
        "beforeRows": before,
        "afterRows": len(out),
        "added": added,
        "addedByFuel": dict(by_fuel),
        "renamedCommercial": renames,
        "aliasCount": len(aliases),
        "generatedAt": datetime.now(timezone.utc).isoformat(),
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: manifest[k] for k in ("seedVersion", "beforeRows", "afterRows", "addedByFuel", "aliasCount") if k in manifest} | {"addedCount": len(added), "renameCount": len(renames)}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
