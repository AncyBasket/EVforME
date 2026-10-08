#!/usr/bin/env python3
"""
Igiene catalogo: fuelKind, consumi ICE/EV/PHEV realistici, drop junk NHTSA.

- ICE: uplift WLTP→uso reale (idempotente se già in fascia)
- EV/PHEV: clamp kWh/100 fuori fascia; BEV range: mai flat 350 passeggeri (pack÷energy o default segmento)
- Sync energyConsumptionKWhPerKm ↔ wltpConsumptionKWh100km; ripara batteryKWh/range placeholder

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
    # Unico seed bundlato a runtime (Fase 1).
    REPO / "EVforME?" / "Data" / "vehicles.seed.quality.json",
    REPO / "api" / "static" / "vehicles.catalog.json",
    REPO / "api" / "static" / "vehicles.catalog.min.json",
]

# Range produzione EU noti (subset) — fuori range = errore hygiene.
KNOWN_EU_YEAR_RANGES = {
    ("tesla", "model 3"): (2019, 2026),
    ("tesla", "model y"): (2021, 2026),
    ("seat", "ateca"): (2016, 2026),
    ("dacia", "spring"): (2021, 2026),
    ("fiat", "500e"): (2020, 2026),
}

BANNED_NON_EU_MODELS = {
    ("tesla", "roadster"),
    ("tesla", "semi"),
    ("tesla", "cybertruck"),
}

# Brand/model needles that must never be powertrain ICE.
KNOWN_EV_ICE_FORBIDDEN = (
    ("tesla", None),
    ("polestar", None),
    ("cupra", "born"),
    ("volkswagen", "id."),
    ("nissan", "ariya"),
    ("peugeot", "e-208"),
    ("citroen", "ë-c3"),
    ("citroën", "ë-c3"),
    ("citroen", "e-c3"),
    ("citroën", "e-c3"),
    ("mg", "mg4"),
    ("mg", "4"),
    ("byd", "dolphin"),
    ("leapmotor", None),
    ("fiat", "500e"),
    ("fiat", "600e"),
)


def _is_forbidden_ice_ev(brand: str, model: str) -> bool:
    for b, m in KNOWN_EV_ICE_FORBIDDEN:
        if b in brand and (m is None or m in model):
            # MG "4" is noisy — require mg4 / mg 4 / model starts with 4 electric-ish
            if b == "mg" and m == "4":
                compact = model.replace(" ", "")
                if "mg4" in compact or model.strip() in {"4", "mg4"}:
                    return True
                continue
            return True
    return False


def _constant_step_ranges(year_range_pairs: list[tuple[int, int]]) -> bool:
    if len(year_range_pairs) < 3:
        return False
    rows = sorted(year_range_pairs)
    if any(rows[i + 1][0] - rows[i][0] != 1 for i in range(len(rows) - 1)):
        return False
    deltas = [rows[i + 1][1] - rows[i][1] for i in range(len(rows) - 1)]
    return len(set(deltas)) == 1 and deltas[0] != 0


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


# BEV range defaults (km). Never invent flat 350 for passenger cars.
# Vans may legitimately sit near 250–350.
EV_DEFAULT_RANGE_KM = {"small": 330, "compact": 500, "medium": 460, "suv": 440}
EV_RANGE_BAND_KM = {
    "small": (280, 380),
    "compact": (450, 580),
    "medium": (380, 520),
    "suv": (380, 520),
}
VAN_DEFAULT_RANGE_KM = 300
VAN_RANGE_BAND_KM = (250, 360)
PLACEHOLDER_RANGE_KM = {350, 351}
USABLE_BATTERY_FRAC = 0.88  # usable ~0.85–0.92 of pack
PHEV_DEFAULT_RANGE_KM = 55


def is_placeholder_bev_range(rng: float | None, row: dict) -> bool:
    """True when range is missing or the old flat-350 hygiene placeholder (passenger only)."""
    if rng is None or rng <= 0:
        return True
    if is_van_like(row):
        return False
    return int(round(rng)) in PLACEHOLDER_RANGE_KM


def battery_looks_derived_from_placeholder(row: dict, kwh_per_km: float) -> bool:
    """True when batteryKWh ≈ energy × 350 (legacy hygiene artifact)."""
    bat = _as_float(row.get("batteryKWh"))
    if bat is None or kwh_per_km is None or kwh_per_km <= 0:
        return True
    for placeholder in PLACEHOLDER_RANGE_KM:
        implied = kwh_per_km * float(placeholder)
        if implied > 0 and abs(bat - implied) / implied < 0.08:
            return True
    rng = _as_float(row.get("wltpRangeKm"))
    if rng is not None and int(round(rng)) in PLACEHOLDER_RANGE_KM:
        implied = kwh_per_km * rng
        if implied > 0 and abs(bat - implied) / implied < 0.08:
            return True
    return False


def model_range_hint_km(row: dict) -> int | None:
    """Known efficient / class anchors so Model 3 / Q4 land in sensible bands."""
    model = (row.get("model") or "").lower()
    brand = (row.get("brand") or "").lower()
    blob = f"{brand} {model}"
    if "model 3" in blob:
        return 520
    if "model y" in blob:
        return 500
    if "model s" in blob:
        return 560
    if "model x" in blob:
        return 480
    if "q4" in model and "tron" in model:
        return 450
    if "ioniq 6" in blob or model == "ioniq 6":
        return 520
    if "ioniq 5" in blob or model == "ioniq 5":
        return 460
    if "leaf" in model:
        return 320
    if "zoe" in model:
        return 340
    if "500e" in model or model in ("500e", "500 electric"):
        return 300
    if "e-up" in model or "e-up!" in model:
        return 260
    if "id.3" in model or model == "id.3":
        return 420
    if "id.4" in model or model == "id.4":
        return 450
    if "enyaq" in model:
        return 450
    if "polestar 2" in blob:
        return 480
    if "mach-e" in model or "mach e" in model:
        return 450
    return None


def default_bev_range_km(row: dict) -> int:
    year = int(row.get("year") or 2020)
    # Mild year drift so the catalog is not another flat spike.
    year_bump = max(-24, min(40, (year - 2020) * 6))
    if is_van_like(row):
        return int(VAN_DEFAULT_RANGE_KM + year_bump // 3)

    hint = model_range_hint_km(row)
    if hint is not None:
        base = hint
        # Keep model anchors inside their class band (city cars stay lower).
        if hint <= 340:
            lo, hi = 250, 380
        elif hint >= 500:
            lo, hi = 450, 620
        else:
            lo, hi = 380, 560
    else:
        seg = segment_from_length(row.get("lengthM"))
        base = EV_DEFAULT_RANGE_KM[seg]
        lo, hi = EV_RANGE_BAND_KM[seg]

    value = int(min(max(base + year_bump, lo), hi))
    # Never re-land passenger cars on the old flat placeholder spike.
    if value in PLACEHOLDER_RANGE_KM:
        value = 345 if value == 350 else 355
        value = int(min(max(value, lo), hi))
        if value in PLACEHOLDER_RANGE_KM:
            value = lo + 5
    return value


def realistic_bev_range_km(row: dict, kwh_per_km: float) -> int:
    """Passenger BEV range: replace placeholder 350; pack÷energy only when range missing."""
    rng = _as_float(row.get("wltpRangeKm"))
    bat = _as_float(row.get("batteryKWh"))

    if is_van_like(row):
        if rng is not None and VAN_RANGE_BAND_KM[0] <= rng <= VAN_RANGE_BAND_KM[1]:
            return int(rng)
        return default_bev_range_km(row)

    # Keep non-placeholder ranges already in a sane band.
    if not is_placeholder_bev_range(rng, row) and rng is not None and 200 <= rng <= 700:
        return int(rng)

    # Exact/clustered placeholder (350): prefer model/segment defaults.
    # Pack values were often derived from earlier energy×350 and are not trustworthy.
    if rng is not None and int(round(rng)) in PLACEHOLDER_RANGE_KM:
        return default_bev_range_km(row)

    # Missing range: try trustworthy pack, else defaults.
    if (
        bat is not None
        and 20 <= bat <= 120
        and not battery_looks_derived_from_placeholder(row, kwh_per_km)
        and kwh_per_km > 0
    ):
        computed = (USABLE_BATTERY_FRAC * bat) / kwh_per_km
        seg = segment_from_length(row.get("lengthM"))
        lo, hi = EV_RANGE_BAND_KM.get(seg, (380, 520))
        lo, hi = max(200, lo - 40), min(700, hi + 60)
        value = int(round(min(max(computed, lo), hi)))
        if value in PLACEHOLDER_RANGE_KM:
            value = default_bev_range_km(row)
        return value

    return default_bev_range_km(row)


def sync_ev_energy_fields(row: dict, kwh_per_km: float) -> bool:
    """Sync energy twins + fix BEV placeholder range/battery. Returns True if range changed."""
    row["energyConsumptionKWhPerKm"] = round(kwh_per_km, 4)
    row["wltpConsumptionKWh100km"] = round(kwh_per_km * 100.0, 1)

    pt = (row.get("powertrain") or "").lower()
    old_rng = _as_float(row.get("wltpRangeKm"))
    bat = _as_float(row.get("batteryKWh"))
    range_changed = False

    if pt == "phev":
        # PHEV electric-only range is short; never invent BEV 350/defaults.
        if old_rng is None or old_rng <= 0:
            row["wltpRangeKm"] = PHEV_DEFAULT_RANGE_KM
            range_changed = True
        rng = float(row["wltpRangeKm"])
        implied = kwh_per_km * rng
        if bat is None or bat < 5 or bat > 40 or (implied > 0 and abs(bat - implied) / implied > 0.55):
            row["batteryKWh"] = round(min(max(implied, 8.0), 30.0), 1)
        return range_changed

    # BEV (and any other electrified row routed here). Snapshot before mutating range.
    was_placeholder = is_placeholder_bev_range(old_rng, row)
    derived_from_placeholder = battery_looks_derived_from_placeholder(row, kwh_per_km)

    new_rng = realistic_bev_range_km(row, kwh_per_km)
    if old_rng is None or int(old_rng) != int(new_rng):
        range_changed = True
    row["wltpRangeKm"] = int(new_rng)

    implied = kwh_per_km * float(new_rng)
    if is_van_like(row) and not range_changed:
        # Vans may keep ~250–350; bat ≈ energy×range is consistent, not a bug.
        needs_bat = (
            bat is None
            or bat < 15
            or bat > 120
            or (implied > 0 and abs(bat - implied) / implied > 0.45)
        )
    else:
        # Leaving a placeholder range: always re-derive pack (stale bat often from older energy×350).
        needs_bat = (
            bat is None
            or bat < 15
            or bat > 120
            or (was_placeholder and range_changed)
            or derived_from_placeholder
            or (implied > 0 and abs(bat - implied) / implied > 0.45)
        )

    if needs_bat:
        cap = 120.0 if is_van_like(row) else 100.0
        row["batteryKWh"] = round(min(max(implied, 20.0), cap), 1)
    return range_changed


def hygiene_rows(rows: list[dict]) -> tuple[list[dict], dict]:
    kept: list[dict] = []
    stats = {
        "in": len(rows),
        "junk_dropped": 0,
        "fuel_kind_set": 0,
        "ice_consumption_fixed": 0,
        "ev_energy_fixed": 0,
        "ev_range_fixed": 0,
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

        if pt in ("ice", "hev") and fk:
            new_cons = realistic_ice_consumption(out, fk)
            old = _as_float(out.get("fuelConsumptionLPerKm"))
            # HEV: non alzare i consumi sopra ~6 L/100 se già realistici.
            if pt == "hev" and old is not None and 0.035 <= old <= 0.060:
                new_cons = old
            if new_cons is not None and (old is None or abs(old - new_cons) >= 0.00005):
                out["fuelConsumptionLPerKm"] = new_cons
                stats["ice_consumption_fixed"] += 1

        elif pt == "ev":
            old = resolve_raw_ev_kwh_per_km(out)
            new_e = realistic_ev_energy(out)
            energy_changed = old is None or abs(old - new_e) >= 0.00005
            range_changed = sync_ev_energy_fields(out, new_e)
            if energy_changed:
                stats["ev_energy_fixed"] += 1
            if range_changed:
                stats["ev_range_fixed"] += 1

        elif pt == "phev":
            old_e = resolve_raw_ev_kwh_per_km(out)
            new_e = realistic_ev_energy(out)
            energy_changed = old_e is None or abs(old_e - new_e) >= 0.00005
            # Always sync twins / missing PHEV range; never apply BEV 350 defaults.
            sync_ev_energy_fields(out, new_e)
            if energy_changed:
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


def validate_catalog(rows: list[dict]) -> list[str]:
    """Check hard invariants (fuelKind, consumo, years, ids, no ICE-as-EV, no +N range interpolations)."""
    errors: list[str] = []
    seen_ids: set[str] = set()
    ev_ranges: dict[tuple[str, str], list[tuple[int, int]]] = {}
    for r in rows:
        rid = r.get("id")
        if not rid:
            errors.append("missing id")
            continue
        if rid in seen_ids:
            errors.append(f"duplicate id {rid}")
        seen_ids.add(rid)
        brand = str(r.get("brand", "")).lower()
        model = str(r.get("model", "")).lower()
        pt = str(r.get("powertrain", "")).lower()
        fk = r.get("fuelKind")
        yr = int(r.get("year") or 0)
        if yr > 2026:
            errors.append(f"year beyond 2026: {rid}")
        if (brand, model) in BANNED_NON_EU_MODELS:
            errors.append(f"banned non-EU model still present: {rid}")
        if "corolla matrix" in model or rid.startswith("toyota-corolla-matrix-"):
            errors.append(f"non-existent Corolla Matrix still present: {rid}")
        rng = KNOWN_EU_YEAR_RANGES.get((brand, model))
        if rng and (yr < rng[0] or yr > rng[1]):
            errors.append(f"year out of EU range {rid}: {yr} not in {rng}")
        if pt == "ice" and _is_forbidden_ice_ev(brand, model):
            errors.append(f"known EV classified as ICE: {rid}")
        if pt == "ev":
            if fk in ("petrol", "diesel", "lpg", "cng"):
                errors.append(f"EV with liquid fuelKind {rid}: {fk}")
            e = r.get("energyConsumptionKWhPerKm") or (
                (r.get("wltpConsumptionKWh100km") or 0) / 100.0
            )
            k100 = float(e or 0) * 100
            # Passenger tipico 12–28; van/SUV grandi fino a ~32.
            if not (12.0 <= k100 <= 32.0):
                errors.append(f"EV energy out of band {rid}: {k100:.1f} kWh/100")
            if r.get("wltpRangeKm") is not None:
                ev_ranges.setdefault((brand, model), []).append((yr, int(r["wltpRangeKm"])))
        if pt == "ice":
            l100 = float(r.get("fuelConsumptionLPerKm") or 0) * 100
            if fk == "cng":
                # kg/100
                if not (2.5 <= l100 <= 8.0):
                    errors.append(f"CNG kg/100 out of band {rid}: {l100:.1f}")
            elif not (3.5 <= l100 <= 15.0):
                # 12 L tipico; fino a 15 L per sport/SUV USA ancora in catalogo.
                errors.append(f"ICE L/100 out of band {rid}: {l100:.1f}")
        if pt == "hev":
            l100 = float(r.get("fuelConsumptionLPerKm") or 0) * 100
            if not (3.5 <= l100 <= 6.0):
                errors.append(f"HEV L/100 out of band {rid}: {l100:.1f}")
        if pt == "phev":
            l100 = float(r.get("fuelConsumptionLPerKm") or 0) * 100
            e100 = float(
                r.get("energyConsumptionKWhPerKm")
                or ((r.get("wltpConsumptionKWh100km") or 0) / 100.0)
                or 0
            ) * 100
            if l100 and not (1.0 <= l100 <= 14.0):
                errors.append(f"PHEV fuel out of band {rid}: {l100:.1f}")
            if e100 and not (10.0 <= e100 <= 32.0):
                errors.append(f"PHEV energy out of band {rid}: {e100:.1f}")
    for (brand, model), pairs in ev_ranges.items():
        if _constant_step_ranges(pairs):
            step = sorted(pairs)[1][1] - sorted(pairs)[0][1]
            errors.append(
                f"EV range grows by constant +{step} km/year (interpolated): {brand} {model}"
            )
    return errors


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", type=Path, action="append", help="Catalog JSON (repeatable)")
    ap.add_argument("--check-only", action="store_true", help="Validate without rewriting")
    args = ap.parse_args()
    paths = args.path or [p for p in DEFAULT_PATHS if p.exists()]
    if not paths:
        print("no catalog files found", file=sys.stderr)
        return 1

    exit_code = 0
    for path in paths:
        if not path.is_absolute():
            path = REPO / path
        rows = json.loads(path.read_text(encoding="utf-8"))
        if args.check_only:
            errs = validate_catalog(rows)
            print(f"{path.relative_to(REPO)}: {len(rows)} rows, {len(errs)} errors")
            for e in errs[:40]:
                print("  -", e)
            if len(errs) > 40:
                print(f"  … {len(errs) - 40} more")
            if errs:
                exit_code = 1
            continue
        stats = process(path)
        print(
            f"{stats['path']}: {stats['in']} → {stats['out']} "
            f"(junk -{stats['junk_dropped']}, fuelKind {stats['fuel_kind_set']}, "
            f"ice↑ {stats['ice_consumption_fixed']}, ev↑ {stats['ev_energy_fixed']}, "
            f"evRange↑ {stats['ev_range_fixed']}, "
            f"phevE↑ {stats['phev_energy_fixed']}, phevF↑ {stats['phev_fuel_fixed']})"
        )
        errs = validate_catalog(json.loads(path.read_text(encoding="utf-8")))
        if errs:
            print(f"  validate: {len(errs)} issues (first: {errs[0]})")
            exit_code = 1
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
