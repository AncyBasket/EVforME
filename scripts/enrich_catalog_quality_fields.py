#!/usr/bin/env python3
"""
Aggiunge campi qualità playbook al seed (senza provider a pagamento).

Input preferito: vehicles.seed.wltp_enriched.json
Output: vehicles.seed.quality.json

Campi:
- market, sourceName, sourceUpdatedAt, confidenceScore
- wltpConsumptionKWh100km / wltpRangeKm (derivati dove possibile)
- batteryKWh (stima grezza EV se manca)
- trim (nil se sconosciuto)
- co2gKm (nil; riservato a EEA detail)
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


def confidence_for(row: dict) -> float:
    score = 0.35
    if row.get("powertrain") in {"ice", "ev", "phev"}:
        score += 0.1
    if row.get("lengthM") and row.get("widthM") and row.get("heightM"):
        score += 0.15
    pt = row.get("powertrain")
    if pt == "ice" and row.get("fuelConsumptionLPerKm"):
        score += 0.25
    if pt in {"ev", "phev"} and row.get("energyConsumptionKWhPerKm"):
        score += 0.25
    if row.get("imageURL"):
        score += 0.1
    return round(min(0.98, score), 2)


def estimate_battery_kwh(row: dict) -> float | None:
    if row.get("powertrain") not in {"ev", "phev"}:
        return None
    if row.get("batteryKWh"):
        return row["batteryKWh"]
    kwh_per_km = row.get("energyConsumptionKWhPerKm")
    if not kwh_per_km:
        return None
    # Ipotesi range utile ~350 km BEV / ~60 km elettrici PHEV.
    range_km = 60.0 if row.get("powertrain") == "phev" else 350.0
    return round(kwh_per_km * range_km, 1)


def enrich(row: dict, source_name: str, updated_at: str) -> dict:
    out = dict(row)
    out.setdefault("trim", None)
    out.setdefault("market", "IT")
    out["sourceName"] = source_name
    out["sourceUpdatedAt"] = updated_at
    out["confidenceScore"] = confidence_for(out)

    energy = out.get("energyConsumptionKWhPerKm")
    if energy:
        out["wltpConsumptionKWh100km"] = round(energy * 100.0, 1)
        # Range grezzo inverso (stessa ipotesi batteria).
        battery = estimate_battery_kwh(out)
        out["batteryKWh"] = battery
        if battery and energy > 0:
            out["wltpRangeKm"] = int(round(battery / energy))
        else:
            out.setdefault("wltpRangeKm", None)
    else:
        out.setdefault("wltpConsumptionKWh100km", None)
        out.setdefault("batteryKWh", None)
        out.setdefault("wltpRangeKm", None)

    out.setdefault("co2gKm", None)
    return out


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    data = root / "EVforME?" / "Data"
    candidates = [
        data / "vehicles.seed.wltp_enriched.json",
        data / "vehicles.seed.nhtsa_enriched.with_images.json",
        data / "vehicles.seed.nhtsa_enriched.json",
        data / "vehicles.seed.json",
    ]
    src = next(p for p in candidates if p.exists())
    updated_at = datetime.now(timezone.utc).isoformat()
    source_name = {
        "vehicles.seed.wltp_enriched.json": "seed+EEA-WLTP",
        "vehicles.seed.nhtsa_enriched.with_images.json": "seed+NHTSA+images",
        "vehicles.seed.nhtsa_enriched.json": "seed+NHTSA",
        "vehicles.seed.json": "seed",
    }.get(src.name, "seed")

    rows = json.loads(src.read_text(encoding="utf-8"))
    enriched = [enrich(r, source_name, updated_at) for r in rows]
    out_path = data / "vehicles.seed.quality.json"
    out_path.write_text(json.dumps(enriched, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # Copia statica per hosting / API file serve.
    static_dir = root / "api" / "static"
    static_dir.mkdir(parents=True, exist_ok=True)
    static_path = static_dir / "vehicles.catalog.json"
    static_path.write_text(json.dumps(enriched, ensure_ascii=False) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "ok": True,
                "source": src.name,
                "rows": len(enriched),
                "output": str(out_path.relative_to(root)),
                "static": str(static_path.relative_to(root)),
                "avgConfidence": round(
                    sum(r["confidenceScore"] for r in enriched) / max(1, len(enriched)), 3
                ),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
