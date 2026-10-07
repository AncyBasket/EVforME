#!/usr/bin/env python3
"""
Igiene catalogo: fuelKind, consumi ICE/EV/PHEV realistici, drop junk NHTSA.

- ICE: uplift WLTP→uso reale (idempotente se già in fascia)
- EV/PHEV: clamp kWh/100 fuori fascia (batteria/range placeholder 350 corrompe i dati)
- Sync energyConsumptionKWhPerKm ↔ wltpConsumptionKWh100km; ripara batteryKWh assurdi

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

# EV / PHEV elettrico: kWh/km uso reale (efficienti ~0.12–0.22; SUV/van più alti).
EV_DEFAULT_KWH_PER_KM = {"small": 0.145, "compact": 0.155, "medium": 0.168, "suv": 0.185}
EV_MIN_KWH_PER_KM = {"small": 0.120, "compact": 0.120, "medium": 0.125, "suv": 0.140}
EV_MAX_KWH_PER_KM = {"small": 0.200, "compact": 0.220, "medium": 0.245, "suv": 0.285}

PHEV_FUEL_MIN_L_PER_KM = 0.025  # charge-sustaining floor (non WLTP blended ~1 L/100)
PHEV_FUEL_MAX_L_PER_KM = 0.120
PHEV_FUEL_DEFAULT = {"small": 0.045, "compact": 0.055, "medium": 0.065, "suv": 0.075}

VAN_NEEDLES = (
    "eqv",
    "e-transit",
    "e-crafter",
    "e-berlingo",
    "e-partner",
    "e-vivaro",
    "id. buzz",
    "id buzz",
    "transporter",
    "vito",
)

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


def _as_float(value) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def is_van_like(row: dict) -> bool:
    blob = f"{row.get('brand', '')} {row.get('model', '')} {row.get('trim') or ''}".lower()
    return any(n in blob for n in VAN_NEEDLES)


def realistic_ice_consumption(row: dict, fuel_kind: str) -> float | None:
    cons = _as_float(row.get("fuelConsumptionLPerKm"))
    if cons is None or cons <= 0:
        return None

    year = int(row.get("year") or 2020)
    age = max(0, 2026 - year)
    seg = segment_from_length(row.get("lengthM"))
    floor = FLOORS_DIESEL[seg] if fuel_kind == "diesel" else FLOORS_PETROL[seg]

    # Idempotente: già in fascia realistica → non ri-alzare.
    if floor <= cons <= 0.14:
        return round(cons, 4)

    if fuel_kind == "diesel":
        uplift = 1.12 + min(age, 12) * 0.006
    else:
        uplift = 1.08 + min(age, 12) * 0.004

    adjusted = max(cons * uplift, floor)
    adjusted = min(adjusted, 0.14)
    return round(adjusted, 4)


def resolve_raw_ev_kwh_per_km(row: dict) -> float | None:
    direct = _as_float(row.get("energyConsumptionKWhPerKm"))
    if direct is not None and direct > 0:
        return direct
    wltp100 = _as_float(row.get("wltpConsumptionKWh100km"))
    if wltp100 is not None and wltp100 > 0:
        return wltp100 / 100.0
    return None


def realistic_ev_energy(row: dict) -> float:
    """kWh/km in fascia realistica; fuori banda → default di segmento (non solo clamp al bordo)."""
    seg = segment_from_length(row.get("lengthM"))
    lo = EV_MIN_KWH_PER_KM[seg]
    hi = EV_MAX_KWH_PER_KM[seg]
    default = EV_DEFAULT_KWH_PER_KM[seg]
    if is_van_like(row):
        lo = max(lo, 0.180)
        hi = max(hi, 0.300)
        default = max(default, 0.220)

    raw = resolve_raw_ev_kwh_per_km(row)
    if raw is None or raw <= 0:
        return default
    if lo <= raw <= hi:
        return round(raw, 4)
    return default


def realistic_phev_fuel(row: dict) -> float | None:
    cons = _as_float(row.get("fuelConsumptionLPerKm"))
    seg = segment_from_length(row.get("lengthM"))
    default = PHEV_FUEL_DEFAULT[seg]
    if cons is None or cons <= 0:
        return default
    if cons < PHEV_FUEL_MIN_L_PER_KM:
        # WLTP blended troppo basso per la quota termica del simulatore.
        return default
    if cons > PHEV_FUEL_MAX_L_PER_KM:
        return PHEV_FUEL_MAX_L_PER_KM
    return round(cons, 4)


def sync_ev_energy_fields(row: dict, kwh_per_km: float) -> None:
    row["energyConsumptionKWhPerKm"] = round(kwh_per_km, 4)
    row["wltpConsumptionKWh100km"] = round(kwh_per_km * 100.0, 1)

    rng = _as_float(row.get("wltpRangeKm"))
    bat = _as_float(row.get("batteryKWh"))
    # Range placeholder ~350 ovunque: ripara solo batterie assurde rispetto al consumo.
    if rng is None or rng <= 0:
        rng = 350.0
        row["wltpRangeKm"] = int(rng)

    implied = kwh_per_km * rng
    if bat is None or bat < 15 or bat > 120 or (implied > 0 and abs(bat - implied) / implied > 0.45):
        # Pack realistici passeggeri ~20–100 kWh; van fino a 120.
        cap = 120.0 if is_van_like(row) else 100.0
        row["batteryKWh"] = round(min(max(implied, 20.0), cap), 1)


def hygiene_rows(rows: list[dict]) -> tuple[list[dict], dict]:
    kept: list[dict] = []
    stats = {
        "in": len(rows),
        "junk_dropped": 0,
        "fuel_kind_set": 0,
        "ice_consumption_fixed": 0,
        "ev_energy_fixed": 0,
        "phev_energy_fixed": 0,
        "phev_fuel_fixed": 0,
        "diesel": 0,
        "petrol": 0,
    }
    for row in rows:
        if is_junk(row):
            stats["junk_dropped"] += 1
            continue
        out = dict(row)
        pt = (out.get("powertrain") or "").lower()
        fk = infer_fuel_kind(out)
        if fk:
            out["fuelKind"] = fk
            stats["fuel_kind_set"] += 1
            stats[fk] = stats.get(fk, 0) + 1
        elif "fuelKind" in out:
            out.pop("fuelKind", None)

        if pt == "ice" and fk:
            new_cons = realistic_ice_consumption(out, fk)
            old = _as_float(out.get("fuelConsumptionLPerKm"))
            if new_cons is not None and (old is None or abs(old - new_cons) >= 0.00005):
                out["fuelConsumptionLPerKm"] = new_cons
                stats["ice_consumption_fixed"] += 1

        elif pt == "ev":
            old = resolve_raw_ev_kwh_per_km(out)
            new_e = realistic_ev_energy(out)
            if old is None or abs(old - new_e) >= 0.00005:
                sync_ev_energy_fields(out, new_e)
                stats["ev_energy_fixed"] += 1
            else:
                # Allinea comunque i campi gemelli se manca wltpConsumption.
                if out.get("wltpConsumptionKWh100km") is None:
                    out["wltpConsumptionKWh100km"] = round(new_e * 100.0, 1)

        elif pt == "phev":
            old_e = resolve_raw_ev_kwh_per_km(out)
            new_e = realistic_ev_energy(out)
            if old_e is None or abs(old_e - new_e) >= 0.00005:
                sync_ev_energy_fields(out, new_e)
                stats["phev_energy_fixed"] += 1
            new_f = realistic_phev_fuel(out)
            old_f = _as_float(out.get("fuelConsumptionLPerKm"))
            if new_f is not None and (old_f is None or abs(old_f - new_f) >= 0.00005):
                out["fuelConsumptionLPerKm"] = new_f
                stats["phev_fuel_fixed"] += 1

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
            f"ice↑ {stats['ice_consumption_fixed']}, ev↑ {stats['ev_energy_fixed']}, "
            f"phevE↑ {stats['phev_energy_fixed']}, phevF↑ {stats['phev_fuel_fixed']})"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
