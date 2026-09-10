#!/usr/bin/env python3
"""
Quality gates per catalogo veicoli.
Fail (exit 1) se trova problemi bloccanti.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


def main() -> int:
    repo = Path(__file__).resolve().parents[1]
    candidates = [
        repo / "EVforME?" / "Data" / "vehicles.seed.quality.json",
        repo / "EVforME?" / "Data" / "vehicles.seed.wltp_enriched.json",
        repo / "EVforME?" / "Data" / "vehicles.seed.nhtsa_enriched.with_images.json",
        repo / "EVforME?" / "Data" / "vehicles.seed.nhtsa_enriched.json",
        repo / "EVforME?" / "Data" / "vehicles.seed.json",
    ]
    path = next((p for p in candidates if p.exists()), candidates[-1])

    rows = json.loads(path.read_text(encoding="utf-8"))
    errors: list[str] = []
    warnings: list[str] = []

    seen_ids: set[str] = set()
    suspicious_terms = {"inc", "ltd", "llc", "company", "manufacturing", "radiator", "trailer"}

    for i, r in enumerate(rows):
        rid = r.get("id")
        brand = str(r.get("brand", "")).strip()
        model = str(r.get("model", "")).strip()
        year = int(r.get("year", 0))
        powertrain = r.get("powertrain")

        if not rid or not brand or not model:
            errors.append(f"row {i}: missing required id/brand/model")
            continue
        if rid in seen_ids:
            errors.append(f"duplicate id: {rid}")
        seen_ids.add(rid)

        if powertrain not in {"ice", "ev", "phev"}:
            errors.append(f"{rid}: invalid powertrain {powertrain}")

        if powertrain == "phev":
            fuel = r.get("fuelConsumptionLPerKm")
            energy = r.get("energyConsumptionKWhPerKm")
            if not isinstance(fuel, (int, float)) or float(fuel) <= 0:
                errors.append(f"{rid}: PHEV needs positive fuelConsumptionLPerKm")
            if not isinstance(energy, (int, float)) or float(energy) <= 0:
                errors.append(f"{rid}: PHEV needs positive energyConsumptionKWhPerKm")

        if year < 1980 or year > 2035:
            errors.append(f"{rid}: out-of-range year {year}")

        length = r.get("lengthM")
        width = r.get("widthM")
        height = r.get("heightM")
        if not (isinstance(length, (int, float)) and 2.5 <= float(length) <= 6.5):
            errors.append(f"{rid}: invalid lengthM {length}")
        if not (isinstance(width, (int, float)) and 1.3 <= float(width) <= 2.4):
            errors.append(f"{rid}: invalid widthM {width}")
        if not (isinstance(height, (int, float)) and 1.0 <= float(height) <= 2.6):
            errors.append(f"{rid}: invalid heightM {height}")

        low_model = model.lower()
        if any(t in low_model for t in suspicious_terms):
            warnings.append(f"{rid}: suspicious model name '{model}'")
        if len(model.split()) > 4:
            warnings.append(f"{rid}: long model label '{model}'")
        # Alcuni modelli legittimi sono sigle (TT, X5, XC90, EQE, ecc.), quindi non flagghiamo di default.

    print(f"validated_rows={len(rows)} errors={len(errors)} warnings={len(warnings)} file={path.name}")
    if warnings:
        print("sample_warnings:")
        for w in warnings[:20]:
            print(" -", w)
    if errors:
        print("errors:")
        for e in errors[:50]:
            print(" -", e)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

