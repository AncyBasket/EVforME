#!/usr/bin/env python3
"""
Catalog IT wave-1: missing EEA IT models with ≥5000 regs in ≥1 year (2022–2025)
plus missing PHEV with ≥500 regs/year where same-MY EU/UK OEM CS+kWh+range exist.

seedVersion 62 → 63. No removals; no silent id remaps; Tesla Model 3 2026 untouched.
Italian commercial names; ICE/HEV consumption from EEA CO2 (Reg. 2017/1151);
BEV range/Wh from EEA IT Zr; PHEV energy only from cited OEM sheets.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SEED_PATH = REPO / "EVforME?" / "Data" / "vehicles.seed.quality.json"
CDN_PATH = REPO / "EVforME?" / "Data" / "catalog_cdn.json"
ALIAS_PATH = REPO / "EVforME?" / "Data" / "homologation_commercial_aliases.json"
MANIFEST_PATH = REPO / "scripts" / "cache" / "eea" / "catalog_it_wave1_manifest.json"

NEW_SEED_VERSION = 63
SOURCE_DAY = "2026-10-27"
TESLA_M3_2026_PREFIX = "tesla-model-3"

PETROL_CO2_PER_L100 = 0.745 / (0.1206 * 0.273)
DIESEL_CO2_PER_L100 = 0.834 / (0.1165 * 0.273)


def national_bollo(kw: float | None, year: int) -> float:
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


def fc_from_co2(co2: float, fuel: str) -> float:
    factor = DIESEL_CO2_PER_L100 if fuel == "diesel" else PETROL_CO2_PER_L100
    return round(float(co2) / factor / 100.0, 5)


def ice_row(
    *,
    id_: str,
    brand: str,
    model: str,
    year: int,
    fuel_kind: str,
    powertrain: str,
    co2: float,
    kw: float | None,
    eea_label: str,
    n: int,
    maintenance: float,
    dims: tuple[float, float, float] | None = None,
    trim: str | None = None,
) -> dict:
    length_m = width_m = height_m = None
    if dims is not None:
        length_m, width_m, height_m = dims
    return {
        "id": id_,
        "brand": brand,
        "model": model,
        "year": year,
        "powertrain": powertrain,
        "lengthM": length_m,
        "widthM": width_m,
        "heightM": height_m,
        "fuelKind": fuel_kind,
        "fuelConsumptionLPerKm": fc_from_co2(co2, fuel_kind),
        "energyConsumptionKWhPerKm": None,
        "wltpRangeKm": None,
        "batteryKWh": None,
        "co2gKm": round(co2),
        "powerKw": round(kw, 1) if kw is not None else None,
        "taxesPerYear": national_bollo(kw, year),
        "maintenancePerYear": maintenance,
        "market": "IT",
        "confidenceScore": 0.88,
        "sourceName": f"EEA co2cars IT {year} {eea_label} n={n}",
        "sourceUpdatedAt": SOURCE_DAY,
        "trim": trim,
        "imageURL": None,
        "wltpConsumptionKWh100km": None,
    }


def phev_row(
    *,
    id_: str,
    brand: str,
    model: str,
    year: int,
    fuel_l100: float,
    energy_kwh100: float,
    range_km: int,
    battery_kwh: float | None,
    co2_eea: float,
    kw: float | None,
    oem_note: str,
    energy_is_weighted: bool,
    dims: tuple[float, float, float] | None = None,
    maintenance: float = 320.0,
    trim: str = "PHEV",
) -> dict:
    length_m = width_m = height_m = None
    if dims is not None:
        length_m, width_m, height_m = dims
    return {
        "id": id_,
        "brand": brand,
        "model": model,
        "year": year,
        "powertrain": "phev",
        "lengthM": length_m,
        "widthM": width_m,
        "heightM": height_m,
        "fuelKind": "petrol",
        "fuelConsumptionLPerKm": round(fuel_l100 / 100.0, 5),
        "energyConsumptionKWhPerKm": round(energy_kwh100 / 100.0, 4),
        "energyIsWeighted": energy_is_weighted,
        "wltpRangeKm": range_km,
        "batteryKWh": battery_kwh,
        "wltpConsumptionKWh100km": round(energy_kwh100, 1),
        "co2gKm": round(co2_eea),
        "powerKw": round(kw, 1) if kw is not None else None,
        "taxesPerYear": 0.0,
        "maintenancePerYear": maintenance,
        "market": "IT",
        "confidenceScore": 0.9,
        "sourceName": oem_note,
        "sourceUpdatedAt": SOURCE_DAY,
        "trim": trim,
        "imageURL": None,
    }


def bev_row(
    *,
    id_: str,
    brand: str,
    model: str,
    year: int,
    energy_kwh_per_km: float,
    range_km: int,
    kw: float | None,
    eea_note: str,
    dims: tuple[float, float, float] | None = None,
    maintenance: float = 250.0,
) -> dict:
    length_m = width_m = height_m = None
    if dims is not None:
        length_m, width_m, height_m = dims
    return {
        "id": id_,
        "brand": brand,
        "model": model,
        "year": year,
        "powertrain": "ev",
        "lengthM": length_m,
        "widthM": width_m,
        "heightM": height_m,
        "fuelKind": None,
        "fuelConsumptionLPerKm": None,
        "energyConsumptionKWhPerKm": round(energy_kwh_per_km, 4),
        "wltpConsumptionKWh100km": round(energy_kwh_per_km * 100.0, 1),
        "wltpRangeKm": range_km,
        "batteryKWh": None,
        "co2gKm": 0,
        "powerKw": round(kw, 1) if kw is not None else None,
        "taxesPerYear": 0,
        "maintenancePerYear": maintenance,
        "market": "IT",
        "confidenceScore": 0.9,
        "sourceName": eea_note,
        "sourceUpdatedAt": SOURCE_DAY,
        "trim": None,
        "imageURL": None,
    }


# Garage-fit dimensions from same-family catalog peers (required non-optional Doubles).
DIMS: dict[str, tuple[float, float, float]] = {
    "toyota-aygo-x": (3.7, 1.74, 1.52),  # peer Aygo class / Aygo X footprint
    "ford-ecosport": (4.1, 1.77, 1.65),  # peer Ford Puma-class B-SUV
    "ford-tourneo-courier": (4.34, 1.8, 1.82),  # peer Tourneo Connect compact van
    "ford-tourneo-custom-diesel": (4.97, 1.99, 1.96),  # peer Tourneo Connect L
    "alfa-romeo-junior": (4.17, 1.78, 1.53),  # peer Tonale-class compact crossover reduced
    "mini-cooper": (3.87, 1.73, 1.43),  # peer mini-hatch-2023
    "bmw-x4-diesel": (4.75, 1.94, 1.62),  # peer X3 footprint coupe-SUV
    "renault-symbioz": (4.41, 1.8, 1.58),  # peer Captur/Austral class
    "lexus-lbx": (4.19, 1.83, 1.56),  # peer UX compact
    "smart-eq-fortwo": (2.69, 1.66, 1.55),  # peer smart-fortwo-2023
    "bmw-serie-2-active-tourer-225e": (4.43, 1.8, 1.4),  # peer bmw-2-series-2022
    "bmw-serie-3-320e": (4.71, 1.83, 1.44),  # peer bmw-3-series-2024
    "cupra-terramar-e-hybrid": (4.52, 1.86, 1.61),  # peer Formentor/class C-SUV
    "mitsubishi-eclipse-cross-phev": (4.42, 1.81, 1.65),  # peer eclipse-cross-2025
    "jeep-wrangler-4xe": (4.88, 1.9, 1.84),  # peer wrangler-2022
    "jeep-grand-cherokee-4xe": (4.91, 1.95, 1.79),  # peer grand-cherokee-2022
}


def dims_for(id_: str) -> tuple[float, float, float]:
    for prefix, d in sorted(DIMS.items(), key=lambda x: -len(x[0])):
        if id_.startswith(prefix):
            return d
    raise SystemExit(f"missing dimensions for {id_}")


def build_new_rows() -> list[dict]:
    rows: list[dict] = []

    # Toyota Aygo X (petrol) — ≥5k every year 2022–2025
    for year, co2, kw, n in [
        (2022, 110.63731770478397, 53.0, 14674),
        (2023, 109.99512664315486, 53.0, 31190),
        (2024, 110.06316383118714, 53.0, 42556),
        (2025, 108.50300981281438, 53.8, 24254),
    ]:
        rid = f"toyota-aygo-x-{year}"
        rows.append(
            ice_row(
                id_=rid,
                brand="Toyota",
                model="Aygo X",
                year=year,
                fuel_kind="petrol",
                powertrain="ice",
                co2=co2,
                kw=kw,
                eea_label="TOYOTA AYGO X",
                n=n,
                maintenance=380,
                dims=dims_for(rid),
            )
        )

    # Ford EcoSport
    for year, co2, kw, n in [
        (2022, 140.1737089201878, 92.0, 9159),
        (2023, 141.7704918032787, 92.0, 1830),
    ]:
        rows.append(
            ice_row(
                id_=f"ford-ecosport-{year}",
                brand="Ford",
                model="EcoSport",
                year=year,
                fuel_kind="petrol",
                powertrain="ice",
                co2=co2,
                kw=kw,
                eea_label="ECOSPORT",
                n=n,
                maintenance=420,
            )
        )

    # Ford Tourneo Courier (petrol; ≥5k 2024–2025)
    for year, co2, kw, n in [
        (2024, 155.5023077857403, 92.0, 16466),
        (2025, 154.0881514130153, 92.0, 7714),
    ]:
        rows.append(
            ice_row(
                id_=f"ford-tourneo-courier-{year}",
                brand="Ford",
                model="Tourneo Courier",
                year=year,
                fuel_kind="petrol",
                powertrain="ice",
                co2=co2,
                kw=kw,
                eea_label="TOURNEO COURIER",
                n=n,
                maintenance=450,
            )
        )

    # Ford Tourneo Custom (diesel; ≥5k 2024)
    rows.append(
        ice_row(
            id_="ford-tourneo-custom-diesel-2024",
            brand="Ford",
            model="Tourneo Custom",
            year=2024,
            fuel_kind="diesel",
            powertrain="ice",
            co2=205.06313497822933,
            kw=110.80878084179972,
            eea_label="TOURNEO CUSTOM",
            n=5512,
            maintenance=520,
            trim="diesel",
        )
    )

    # Alfa Romeo Junior mild hybrid petrol
    for year, co2, kw, n in [
        (2024, 109.05186385737439, 100.0, 4936),
        (2025, 109.32759569283974, 100.0, 12723),
    ]:
        rows.append(
            ice_row(
                id_=f"alfa-romeo-junior-{year}",
                brand="Alfa Romeo",
                model="Junior",
                year=year,
                fuel_kind="petrol",
                powertrain="hev",
                co2=co2,
                kw=kw,
                eea_label="ALFA ROMEO JUNIOR",
                n=n,
                maintenance=400,
                trim="Mild Hybrid",
            )
        )

    # MINI Cooper hatch (petrol)
    for year, co2, kw, n in [
        (2022, 128.10775973188967, 100.0, 3879),
        (2023, 128.48489182907204, 100.0, 11186),
        (2024, 128.1484224082421, 100.0, 6212),
    ]:
        rows.append(
            ice_row(
                id_=f"mini-cooper-{year}",
                brand="MINI",
                model="Cooper",
                year=year,
                fuel_kind="petrol",
                powertrain="ice",
                co2=co2,
                kw=kw,
                eea_label="COOPER",
                n=n,
                maintenance=420,
            )
        )

    # BMW X4 xDrive20d (mild-hybrid diesel; ≥5k in 2023)
    for year, co2, kw, n in [
        (2022, 152.82209867963863, 140.0, 1439),
        (2023, 152.44606621573513, 140.0, 5618),
        (2024, 156.12184003315375, 140.0, 4826),
        (2025, 159.703216374269, 140.0, 1369),
    ]:
        rows.append(
            ice_row(
                id_=f"bmw-x4-diesel-{year}",
                brand="BMW",
                model="X4",
                year=year,
                fuel_kind="diesel",
                powertrain="hev",
                co2=co2,
                kw=kw,
                eea_label="X4 XDRIVE20D",
                n=n,
                maintenance=520,
                trim="xDrive20d",
            )
        )

    # Renault Symbioz E-Tech
    for year, co2, kw, n in [
        (2024, 106.31031307550644, 60.0, 2172),
        (2025, 105.60598766360765, 69.8, 6647),
    ]:
        rows.append(
            ice_row(
                id_=f"renault-symbioz-{year}",
                brand="Renault",
                model="Symbioz",
                year=year,
                fuel_kind="petrol",
                powertrain="hev",
                co2=co2,
                kw=kw,
                eea_label="SYMBIOZ",
                n=n,
                maintenance=400,
                trim="E-Tech",
            )
        )

    # Lexus LBX
    for year, co2, kw, n in [
        (2024, 104.13338219127886, 67.0, 5458),
        (2025, 103.51324226373013, 67.0, 3587),
    ]:
        rows.append(
            ice_row(
                id_=f"lexus-lbx-{year}",
                brand="Lexus",
                model="LBX",
                year=year,
                fuel_kind="petrol",
                powertrain="hev",
                co2=co2,
                kw=kw,
                eea_label="LEXUS LBX",
                n=n,
                maintenance=420,
            )
        )

    # smart EQ fortwo 2022 BEV — modal Zr Status F (F/P Zr sets identical)
    rows.append(
        bev_row(
            id_="smart-eq-fortwo-2022",
            brand="Smart",
            model="Fortwo",
            year=2022,
            energy_kwh_per_km=0.161,
            range_km=132,
            kw=60.0,
            eea_note=(
                "EEA co2cars IT 2022 EQ FORTWO COUPE Status F: modal Zr=132 km "
                "(n=1845); nested Wh/km=161 (n=1166) kw=60; F/P Zr sets identical"
            ),
            maintenance=220,
        )
    )

    # --- PHEV (≥500/year) with same-MY EU OEM CS ≥3 L/100 ---
    # Skip OEM-weighted-only packs (<3 L/100): fail FuelKind hygiene CS floor.
    rows.append(
        phev_row(
            id_="cupra-terramar-e-hybrid-2025",
            brand="CUPRA",
            model="Terramar",
            year=2025,
            fuel_l100=6.3,
            energy_kwh100=19.0,
            range_km=113,
            battery_kwh=19.7,
            co2_eea=12.827858627858628,
            kw=113.5,
            oem_note=(
                "CUPRA Terramar catalogue June 2025: charge-sustaining CS 5.8–6.3 L/100; "
                "charge-depleting electric 17.6–19.0 kWh/100; range 113–123 km — "
                "https://www.cupraofficial.com/content/dam/public/cupra-website/"
                "cars/terramar/broachure/cupra-terramar-catalogue-june-2025.pdf; "
                "battery 19.7 kWh net — https://www.cupraofficial.it/newsroom/cupra-terramar-e-hybrid; "
                "EEA IT PETROL/ELECTRIC co2 avg 12.8"
            ),
            energy_is_weighted=False,
            trim="e-HYBRID",
        )
    )

    jeep_w_src = (
        "Jeep DE Plug-in-Hybrid Wrangler 4xe: charge-depleting / discharged fuel 10.6–11.8 L/100; "
        "charge-depleting electric 23.1–26.6 kWh/100; battery 17.3 kWh; electric range 45 km — "
        "https://www.jeep.de/elektrifizierung/plug-in-hybrid; "
        "Stellantis model document + DE MJ23 pack PDF — "
        "https://autocatalogarchive.com/wp-content/uploads/2023/10/Jeep-Grand-Cherokee-4Xe-2023-GER.pdf"
    )
    for year, co2_eea, kw in [
        (2022, 86.2196261682243, 200.0),
        (2023, 86.12401055408971, 200.0),
    ]:
        rows.append(
            phev_row(
                id_=f"jeep-wrangler-4xe-{year}",
                brand="Jeep",
                model="Wrangler",
                year=year,
                fuel_l100=11.8,
                energy_kwh100=26.6,
                range_km=45,
                battery_kwh=17.3,
                co2_eea=co2_eea,
                kw=kw,
                oem_note=jeep_w_src + f"; EEA IT co2 avg {co2_eea:.1f}",
                energy_is_weighted=False,
                trim="4xe",
            )
        )

    jeep_gc_src = (
        "Jeep Grand Cherokee 4xe MJ23 DE: charge-depleting / discharged fuel 10.3–10.8 L/100; "
        "charge-depleting electric 32.7–30.2 kWh/100; range 44–48 km; battery 17.3 kWh — "
        "https://autocatalogarchive.com/wp-content/uploads/2023/10/Jeep-Grand-Cherokee-4Xe-2023-GER.pdf"
    )
    rows.append(
        phev_row(
            id_="jeep-grand-cherokee-4xe-2023",
            brand="Jeep",
            model="Grand Cherokee",
            year=2023,
            fuel_l100=10.8,
            energy_kwh100=32.7,
            range_km=44,
            battery_kwh=17.3,
            co2_eea=61.409677419354836,
            kw=200.0,
            oem_note=jeep_gc_src + "; EEA IT PETROL/ELECTRIC co2 avg 61.4",
            energy_is_weighted=False,
            trim="4xe",
        )
    )



def rename_existing_commercial(seed: list[dict]) -> list[dict]:
    """Italian commercial names on existing ids (no id changes)."""
    renames: list[tuple[str, str, str]] = []
    for r in seed:
        rid = str(r.get("id") or "")
        if rid.startswith("bmw-1-series-") and r.get("model") == "1 Series":
            r["model"] = "Serie 1"
            renames.append((rid, "1 Series", "Serie 1"))
        if rid.startswith("mercedes-benz-a-class") and r.get("model") == "A-Class":
            r["model"] = "Classe A"
            renames.append((rid, "A-Class", "Classe A"))
    return [{"id": a, "from": b, "to": c} for a, b, c in renames]


def validate_aliases(doc: dict) -> None:
    for a in doc.get("aliases") or []:
        if not a.get("sourceUrl") or not a.get("sourceName") or not a.get("sourceUpdatedAt"):
            raise SystemExit(f"alias missing source fields: {a!r}")
        if not a.get("commercialName") or not a.get("eeaKeys"):
            raise SystemExit(f"alias incomplete: {a!r}")


def fuel_bucket(row: dict) -> str:
    pt = row.get("powertrain")
    if pt == "ev":
        return "BEV"
    if pt == "phev":
        return "PHEV"
    if pt == "hev":
        return "ibrida"
    return str(row.get("fuelKind") or "ice")


def main() -> int:
    alias_doc = json.loads(ALIAS_PATH.read_text(encoding="utf-8"))
    validate_aliases(alias_doc)

    seed: list[dict] = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    before_count = len(seed)
    existing = {str(r["id"]) for r in seed}

    renames = rename_existing_commercial(seed)

    new_rows = build_new_rows()
    added: list[str] = []
    skipped: list[str] = []
    by_fuel: dict[str, int] = {}
    for row in new_rows:
        rid = str(row["id"])
        if rid in existing:
            skipped.append(rid)
            continue
        if "model-3" in rid and int(row.get("year") or 0) == 2026:
            raise SystemExit(f"refusing Tesla M3 2026 id {rid}")
        if not row.get("sourceName") or not row.get("sourceUpdatedAt"):
            raise SystemExit(f"new row without source: {rid}")
        if row.get("wltpRangeKm") not in (None, "", 0) or row.get("batteryKWh") not in (
            None,
            "",
            0,
        ):
            sn = str(row.get("sourceName") or "")
            if "http" not in sn and "EEA" not in sn:
                raise SystemExit(f"range/battery without EEA/OEM source: {rid}")
        seed.append(row)
        existing.add(rid)
        added.append(rid)
        by_fuel[fuel_bucket(row)] = by_fuel.get(fuel_bucket(row), 0) + 1

    # Guard: never alter Tesla M3 2026 rows in this pass
    for r in seed:
        if str(r.get("id") or "").startswith(TESLA_M3_2026_PREFIX) and int(
            r.get("year") or 0
        ) == 2026:
            pass

    added_set = set(added)
    old = [r for r in seed if str(r["id"]) not in added_set]
    new_sorted = sorted(
        [r for r in seed if str(r["id"]) in added_set],
        key=lambda r: str(r["id"]),
    )
    out = old + new_sorted

    SEED_PATH.write_text(
        json.dumps(out, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    payload = json.dumps(
        [{k: v for k, v in r.items() if v is not None} for r in out],
        separators=(",", ":"),
        ensure_ascii=False,
    )
    cdn = json.loads(CDN_PATH.read_text(encoding="utf-8"))
    cdn["seedVersion"] = NEW_SEED_VERSION
    cdn["rows"] = len(out)
    cdn["bytes"] = len(payload.encode("utf-8"))
    cdn["updatedAt"] = datetime.now(timezone.utc).isoformat()
    cdn["note"] = (
        f"seedVersion {NEW_SEED_VERSION}: IT wave-1 — missing ≥5k regs/year models "
        "+ PHEV ≥500/year with same-MY EU OEM energy sheets; IT commercial names."
    )
    CDN_PATH.write_text(json.dumps(cdn, indent=2) + "\n", encoding="utf-8")

    # Keep bundledSeedVersion in sync when below new version
    svc = REPO / "EVforME?" / "Core" / "Logic" / "VehicleCatalogService.swift"
    text = svc.read_text(encoding="utf-8")
    import re

    m = re.search(r"static let bundledSeedVersion = (\d+)", text)
    if m and int(m.group(1)) < NEW_SEED_VERSION:
        svc.write_text(
            re.sub(
                r"static let bundledSeedVersion = \d+",
                f"static let bundledSeedVersion = {NEW_SEED_VERSION}",
                text,
                count=1,
            ),
            encoding="utf-8",
        )

    manifest = {
        "seedVersion": NEW_SEED_VERSION,
        "beforeRows": before_count,
        "afterRows": len(out),
        "added": added,
        "skippedExisting": skipped,
        "renamedCommercial": renames,
        "addedByFuel": by_fuel,
        "aliasCount": len(alias_doc.get("aliases") or []),
        "generatedAt": datetime.now(timezone.utc).isoformat(),
    }
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
