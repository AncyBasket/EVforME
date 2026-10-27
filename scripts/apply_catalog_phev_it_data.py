#!/usr/bin/env python3
"""
Complete incomplete IT PHEV rows where same-MY official OEM EU/UK sources
publish CS L/100 + CD (non-weighted) kWh + range + battery.

Seed +1; no removals; Tesla Model 3 2026 untouched.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SEED = REPO / "EVforME?" / "Data" / "vehicles.seed.quality.json"
CDN = REPO / "EVforME?" / "Data" / "catalog_cdn.json"
CACHE = REPO / "scripts" / "cache" / "eea"
MANIFEST = CACHE / "catalog_phev_it_data_manifest.json"
SOURCE_DAY = "2026-10-27"

# Completions: only when ALL of CS (>=3), CD unweighted, range, battery are on
# the same-MY official cite (or pair of cites for the same MY).
COMPLETIONS: list[dict] = [
    {
        "id": "ford-kuga-phev-2024",
        "year": 2024,
        "eeaPowerKw": 111.4,
        "oemIceKw": 112.0,  # must match EEA ep__KW_ (±2)
        "fuelConsumptionLPerKm": 0.061,  # 6.1 L/100 prudent (band 6.1–5.2)
        "energyConsumptionKWhPerKm": 0.209,  # 20.9 kWh/100 rein elektrisch (band 20.9–18.4)
        "energyIsWeighted": False,
        "weightedFuelConsumptionLPerKm": 0.012,  # 1.2 (band 1.2–0.9 Preisliste MY24.5)
        "weightedEnergyConsumptionKWhPerKm": 0.175,  # 17.5 (band 17.5–16.2)
        "wltpRangeKm": 60,  # min of 60–68
        "batteryKWh": 14.4,
        "sourceName": (
            "Ford DE EnVKV Kuga 2,5 l Duratec PHEV 178 kW (ICE 112 kW): "
            "Kraftstoffverbrauch bei entladener Batterie 6,1–5,2 L/100; "
            "Stromverbrauch bei rein elektrischem Betrieb kombiniert 20,9–18,4 kWh/100; "
            "EAER 60–68 km — https://www.ford.de/hybrid-elektrisch/energie; "
            "Preisliste MY24.5 gültig ab 01.05.2024 (CS + weighted) — "
            "https://www.ford.de/content/dam/guxeu/de/documents/price-list/cars/new-kuga/"
            "der-Ford-Kuga_gültig_ab_01_05_2024.pdf; "
            "Technische Daten Ford Kuga: Batterie 14,4 kWh installiert; "
            "rein elektrisch 20,9–18,4; CS 6,1–5,2; range 60–68 — "
            "https://www.ford.de/content/dam/guxeu/de/documents/price-list/cars/new-kuga/"
            "Technische_Daten_des_Ford_Kuga.pdf"
        ),
        "sourceHost": "ford.de",
        "sourceUrl": "https://www.ford.de/hybrid-elektrisch/energie",
    },
]


def main() -> None:
    seed = json.loads(SEED.read_text(encoding="utf-8"))
    by_id = {r["id"]: r for r in seed}
    m3_before = {
        r["id"]: json.dumps(r, sort_keys=True)
        for r in seed
        if r["id"].startswith("tesla-model-3") and r.get("year") == 2026
    }

    ids_before = [r["id"] for r in seed]
    before_complete = sum(
        1
        for r in seed
        if r.get("powertrain") == "phev"
        and not r.get("parentId")
        and not r.get("catalogDataIncomplete")
    )

    completed: list[dict] = []
    for c in COMPLETIONS:
        rid = c["id"]
        if rid not in by_id:
            raise SystemExit(f"missing id {rid}")
        r = by_id[rid]
        if int(r.get("year") or 0) != c["year"]:
            raise SystemExit(f"year mismatch {rid}")
        eea_kw = float(r.get("powerKw") or 0)
        if abs(eea_kw - c["oemIceKw"]) > 2.0:
            raise SystemExit(
                f"power mismatch {rid}: eea={eea_kw} oem_ice={c['oemIceKw']}"
            )
        if float(c["fuelConsumptionLPerKm"]) * 100 < 3.0:
            raise SystemExit(f"CS too thin {rid}")
        if c["energyIsWeighted"]:
            raise SystemExit(f"CD must not be weighted {rid}")

        r["fuelConsumptionLPerKm"] = c["fuelConsumptionLPerKm"]
        r["energyConsumptionKWhPerKm"] = c["energyConsumptionKWhPerKm"]
        r["energyIsWeighted"] = False
        r["weightedFuelConsumptionLPerKm"] = c["weightedFuelConsumptionLPerKm"]
        r["weightedEnergyConsumptionKWhPerKm"] = c[
            "weightedEnergyConsumptionKWhPerKm"
        ]
        r["wltpRangeKm"] = c["wltpRangeKm"]
        r["batteryKWh"] = c["batteryKWh"]
        r["catalogDataIncomplete"] = False
        r["confidenceScore"] = 0.9
        r["sourceName"] = c["sourceName"]
        r["sourceUpdatedAt"] = SOURCE_DAY
        r["market"] = "IT"
        completed.append(
            {
                "id": rid,
                "host": c["sourceHost"],
                "year": c["year"],
                "url": c["sourceUrl"],
            }
        )

    for r in seed:
        if r["id"] in m3_before and json.dumps(r, sort_keys=True) != m3_before[r["id"]]:
            raise SystemExit(f"M3 2026 altered: {r['id']}")

    cdn = json.loads(CDN.read_text(encoding="utf-8"))
    new_ver = int(cdn.get("seedVersion") or 66) + 1
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
    after_complete = sum(1 for r in parents if not r.get("catalogDataIncomplete"))
    after_incomplete = sum(1 for r in parents if r.get("catalogDataIncomplete"))

    man = {
        "seedVersion": new_ver,
        "ids_before": ids_before,
        "phev_complete_before": before_complete,
        "phev_complete_after": after_complete,
        "phev_incomplete_after": after_incomplete,
        "completed": completed,
        "completed_count": len(completed),
    }
    MANIFEST.write_text(json.dumps(man, indent=2) + "\n")
    print(json.dumps(man, indent=2))


if __name__ == "__main__":
    main()
