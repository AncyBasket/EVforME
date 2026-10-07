#!/usr/bin/env python3
"""
Igiene catalogo: fuelKind, consumi ICE realistici, drop junk NHTSA.

Allinea le euristiche a VehicleCatalogItem (Swift) e applica un uplift
WLTP → uso reale (specie diesel SUV / auto più vecchie).

Uso:
  python3 scripts/hygiene_catalog_fuel_and_consumption.py
  python3 scripts/hygiene_catalog_fuel_and_consumption.py --path EVforME?/Data/vehicles.seed.quality.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

DIESEL_LEAN = {
    "ateca",
    "tiguan",
    "touareg",
    "qashqai",
    "x-trail",
    "sportage",
    "sorento",
    "tucson",
    "santa fe",
    "kuga",
    "mondeo",
    "passat",
    "superb",
    "octavia",
    "3008",
    "5008",
    "508",
    "c5 aircross",
    "kadjar",
    "koleos",
    "outlander",
    "asx",
    "rav4",
    "land cruiser",
    "discovery",
    "discovery sport",
    "range rover evoque",
    "range rover sport",
    "defender",
    "glc",
    "gle",
    "x3",
    "x5",
    "q5",
    "q7",
    "a4",
    "a6",
    "3 series",
    "5 series",
    "c-class",
    "e-class",
    "vito",
    "transporter",
    "tarraco",
    "formentor",
    "karoq",
    "kodiaq",
    "tucson",
}

PETROL_LEAN = {
    "panda",
    "500",
    "500l",
    "500x",
    "punto",
    "twingo",
    "clio",
    "micra",
    "aygo",
    "yaris",
    "i10",
    "i20",
    "picanto",
    "rio",
    "up!",
    "polo",
    "corsa",
    "208",
    "108",
    "107",
    "c1",
    "c3",
    "ibiza",
    "fabia",
    "mii",
}

JUNK_NEEDLES = (
    "radiator",
    "trailer",
    "manufacturing",
    " llc",
    " inc",
    " ltd",
    "company",
    "chassis",
    "incomplete",
    "motorhome",
    "cutaway",
)

# Floor L/km (uso reale, non solo WLTP) per segmento grezzo da lunghezza.
FLOORS_PETROL = {"small": 0.052, "compact": 0.058, "medium": 0.062, "suv": 0.068}
FLOORS_DIESEL = {"small": 0.048, "compact": 0.055, "medium": 0.068, "suv": 0.074}

DEFAULT_PATHS = [
    REPO / "EVforME?" / "Data" / "vehicles.seed.json",
    REPO / "EVforME?" / "Data" / "vehicles.seed.quality.json",
    REPO / "EVforME?" / "Data" / "vehicles.seed.nhtsa_enriched.json",
    REPO / "EVforME?" / "Data" / "vehicles.seed.nhtsa_enriched.with_images.json",
    REPO / "EVforME?" / "Data" / "vehicles.seed.wltp_enriched.json",
    REPO / "api" / "static" / "vehicles.catalog.json",
    REPO / "api" / "static" / "vehicles.catalog.min.json",
]


def is_junk(row: dict) -> bool:
    blob = f"{row.get('brand', '')} {row.get('model', '')}".lower()
    return any(n in blob for n in JUNK_NEEDLES)


def segment_from_length(length_m: float | None) -> str:
    if length_m is None:
        return "compact"
    if length_m < 4.0:
        return "small"
    if length_m < 4.35:
        return "compact"
    if length_m < 4.7:
        return "medium"
    return "suv"


def infer_fuel_kind(row: dict) -> str | None:
    pt = (row.get("powertrain") or "").lower()
    if pt == "ev":
        return None
    if pt == "phev":
        # PHEV tipicamente benzina+elettrico in IT.
        return "petrol"
    if pt != "ice":
        return None

    existing = row.get("fuelKind")
    if existing in ("petrol", "diesel"):
        return existing

    model = (row.get("model") or "").lower()
    trim = (row.get("trim") or "").lower()
    blob = f"{model} {trim}"
    year = int(row.get("year") or 2020)

    if any(
        x in blob
        for x in (
            "diesel",
            "tdi",
            "tdci",
            " dci",
            "hdi",
            "jtd",
            "crd",
            "skyactiv-d",
            "bluehdi",
        )
    ):
        return "diesel"
    if any(
        x in blob
        for x in (
            "benzina",
            "petrol",
            "tsi",
            "tfsi",
            "tce",
            "mpi",
            "gdi",
            "skyactiv-g",
        )
    ):
        return "petrol"
    if model in PETROL_LEAN:
        return "petrol"
    if model in DIESEL_LEAN and 2010 <= year <= 2021:
        return "diesel"
    if model in DIESEL_LEAN and year >= 2022:
        return "petrol"
    return "petrol"


def realistic_ice_consumption(row: dict, fuel_kind: str) -> float | None:
    raw = row.get("fuelConsumptionLPerKm")
    if raw is None:
        return None
    try:
        cons = float(raw)
    except (TypeError, ValueError):
        return None
    if cons <= 0:
        return None

    year = int(row.get("year") or 2020)
    age = max(0, 2026 - year)
    seg = segment_from_length(row.get("lengthM"))

    # WLTP → real-world: diesel SUV/family spesso ~+12–18%; benzina ~+8–12%.
    if fuel_kind == "diesel":
        uplift = 1.12 + min(age, 12) * 0.006  # usata diesel: più sete
        floor = FLOORS_DIESEL[seg]
    else:
        uplift = 1.08 + min(age, 12) * 0.004
        floor = FLOORS_PETROL[seg]

    adjusted = max(cons * uplift, floor)
    # Cap assurdo (non trasformare citycar in Hummer).
    adjusted = min(adjusted, 0.14)
    return round(adjusted, 4)


def hygiene_rows(rows: list[dict]) -> tuple[list[dict], dict]:
    kept: list[dict] = []
    stats = {
        "in": len(rows),
        "junk_dropped": 0,
        "fuel_kind_set": 0,
        "consumption_bumped": 0,
        "diesel": 0,
        "petrol": 0,
    }
    for row in rows:
        if is_junk(row):
            stats["junk_dropped"] += 1
            continue
        out = dict(row)
        fk = infer_fuel_kind(out)
        if fk:
            out["fuelKind"] = fk
            stats["fuel_kind_set"] += 1
            stats[fk] = stats.get(fk, 0) + 1
        elif "fuelKind" in out:
            out.pop("fuelKind", None)

        if (out.get("powertrain") or "").lower() == "ice" and fk:
            new_cons = realistic_ice_consumption(out, fk)
            old = out.get("fuelConsumptionLPerKm")
            if new_cons is not None and (old is None or abs(float(old) - new_cons) >= 0.00005):
                out["fuelConsumptionLPerKm"] = new_cons
                stats["consumption_bumped"] += 1

        kept.append(out)
    stats["out"] = len(kept)
    return kept, stats


def write_catalog(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.name.endswith(".min.json"):
        compact = [{k: v for k, v in row.items() if v is not None} for row in rows]
        path.write_text(
            json.dumps(compact, separators=(",", ":"), ensure_ascii=False),
            encoding="utf-8",
        )
    else:
        path.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def process(path: Path) -> dict:
    rows = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        raise SystemExit(f"{path}: expected JSON array")
    kept, stats = hygiene_rows(rows)
    write_catalog(path, kept)
    stats["path"] = str(path.relative_to(REPO))
    return stats


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", type=Path, action="append", help="Catalog JSON (repeatable)")
    args = ap.parse_args()
    paths = args.path or [p for p in DEFAULT_PATHS if p.exists()]
    if not paths:
        print("no catalog files found", file=sys.stderr)
        return 1

    for path in paths:
        if not path.is_absolute():
            path = REPO / path
        stats = process(path)
        print(
            f"{stats['path']}: {stats['in']} → {stats['out']} "
            f"(junk -{stats['junk_dropped']}, fuelKind {stats['fuel_kind_set']}, "
            f"cons↑ {stats['consumption_bumped']}, diesel {stats.get('diesel', 0)}, "
            f"petrol {stats.get('petrol', 0)})"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
