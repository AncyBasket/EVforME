#!/usr/bin/env python3
"""Apply the verified official PHEV source supplement from 2026-11-03.

Only exact year/variant fields supported by official Italian/EU primary sources
are written. Weighted WLTP fuel is kept in weightedFuelConsumptionLPerKm and is
never copied into the charge-sustaining calculation field.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEED = ROOT / "EVforME?" / "Data" / "vehicles.seed.quality.json"
MANIFESTS = [ROOT / "EVforME?" / "Data" / "catalog_cdn.json", ROOT / "api" / "static" / "catalog_cdn.json"]
API_PRETTY = ROOT / "api" / "static" / "vehicles.catalog.json"
API_MIN = ROOT / "api" / "static" / "vehicles.catalog.min.json"
REPORT_JSON = ROOT / "docs" / "audit" / "PHEV_SOURCE_RESEARCH_2026-11-03.json"
PREV_VERSION = 75
NEXT_VERSION = 76
SOURCE_DAY = "2026-11-03"
UPDATED_AT = "2026-11-03T10:08:00+00:00"

# Source metadata is kept with every changed or corroborated field.
BMW_2AT = {
  2022: {
    "url": "https://www.bmw.it/content/dam/bmw/marketIT/bmw_it/Topics/Business/2022/Listini/Listino-BMWSerie2-ActiveTourer-U06.pdf.asset.1656074029722.pdf",
    "title": "Nuova BMW Serie 2 Active Tourer (U06) — listino valido dal 01.06.2022, produzione dal 01.07.2022",
    "date": "2022-06-01", "battery": 14.2, "range_min": 83, "range_max": 92,
    "excerpt": "225e xDrive; batteria 16,3 kWh lorda / 14,2 kWh netta; autonomia elettrica 83–92 km.",
  },
  2023: {
    "url": "https://www.bmw.it/content/dam/bmw/marketIT/bmw_it/Topics/Business/2023/Listini2023/Listino_BMW-Serie2-Active-Tourer_U06_produzione-dal-01.03.2023.pdf.asset.1675070620611.pdf",
    "title": "BMW Serie 2 Active Tourer (U06) — listino valido dal 25.01.2023, produzione dal 01.03.2023",
    "date": "2023-01-25", "battery": 14.2, "range_min": 83, "range_max": 92,
    "excerpt": "225e xDrive; batteria 16,3 kWh lorda / 14,2 kWh netta; autonomia elettrica 83–92 km.",
  },
  2024: {
    "url": "https://www.bmw.it/content/dam/bmw/marketIT/bmw_it/Topics/Business/2024/aprile/Listino%20BMW%20Serie%202%20Active%20Tourer%20(U06)%20da%20prod.%2001.07.2024.pdf.asset.1713250994104.pdf",
    "title": "BMW Serie 2 Active Tourer (U06) — listino valido dal 15.04.2024, produzione dal 01.07.2024",
    "date": "2024-04-15", "battery": 14.2, "range_min": 78, "range_max": 88,
    "excerpt": "225e xDrive; batteria 16,3 kWh lorda / 14,2 kWh netta; autonomia elettrica 78–88 km.",
  },
}
BMW_X3 = {
  2022: {
    "url": "https://www.bmw.it/content/dam/bmw/marketIT/bmw_it/Topics/Business/2022/Listini/Listino-Nuova-BMW-X3-G01.pdf.asset.1656075290702.pdf",
    "title": "Nuova BMW X3 (G01) — listino valido dal 18.05.2022",
    "date": "2022-05-18", "battery": 11.15, "range_min": 45, "range_max": 51,
    "excerpt": "xDrive30e; batteria 12 kWh lorda / 11,15 kWh netta; autonomia elettrica WLTP 45–51 km.",
  },
  2023: {
    "url": "https://www.bmw.it/content/dam/bmw/marketIT/bmw_it/Topics/Business/2023/listini-0423/Listino-BMW-X3-G01-valido-da-prod.01.04.2023.pdf.asset.1676901178092.pdf",
    "title": "BMW X3 (G01) — listino valido dal 16.02.2023, produzione dal 01.04.2023",
    "date": "2023-02-16", "battery": 11.15, "range_min": 45, "range_max": 51,
    "excerpt": "xDrive30e; batteria 12 kWh lorda / 11,15 kWh netta; autonomia elettrica WLTP 45–51 km.",
  },
  2024: {
    "url": "https://www.bmw.it/content/dam/bmw/marketIT/bmw_it/Topics/Business/2024/gennaio/Listino%20BMW%20X3%20(G01)%20valido%20da%20prod.%2001.04.2024.pdf.asset.1706715697138.pdf",
    "title": "BMW X3 (G01) — listino valido dal 31.01.2024, produzione dal 01.04.2024",
    "date": "2024-01-31", "battery": 11.15, "range_min": 45, "range_max": 51,
    "excerpt": "xDrive30e; batteria 12 kWh lorda / 11,15 kWh netta; autonomia elettrica WLTP 45–51 km.",
  },
}
HYUNDAI_TUCSON = {
  "url": "https://hyundai-cyprus.com/wp-content/uploads/admin/2022/07/New-Hyundai-Tucson-FULL-HYBRID-PLUG-IN-HYBRID-AUGUST-22.pdf",
  "title": "Hyundai Tucson MY23 Hybrid & Plug-in Hybrid — scheda tecnica, agosto 2022",
  "date": None,
  "excerpt": "1.6 T-GDi 4x4 Plug-in Hybrid 265 PS; batteria 13,8 kWh; autonomia elettrica WLTP 62 km; Combined WLTP 1,4 l/100 km; CO2 31 g/km.",
}
TOYOTA_23 = {
  "url": "https://newsroom.toyota.it/download/1316286/20230101rav4plug-inhybridmy23schedatecnica.pdf",
  "title": "Toyota Italia — Scheda Tecnica RAV4 Plug-in Hybrid MY23",
  "date": "2023-01-03",
  "excerpt": "Batteria agli ioni di litio 18,1 kWh; ciclo combinato WLTP 1,00 l/100 km e 22 g/km CO2. Autonomia 75 km solo per GR SPORT, non assegnata al record generico.",
}
TOYOTA_24 = {
  "url": "https://www.toyota.it/content/dam/toyota/nmsc/italy/gamma/pdf/scheda-tecnica/RAV4_Plug-in_Hybrid_Scheda_tecnica.pdf",
  "title": "Toyota Italia — RAV4 Plug-in Hybrid, scheda tecnica MY24",
  "date": "2023-06-26",
  "excerpt": "Batteria agli ioni di litio 18,1 kWh; ciclo combinato WLTP 1,00 l/100 km e 22 g/km CO2.",
}
CUPRA_24 = {
  "url": "https://www.cupra.com/content/dam/countries/ie/cupra-website/product-guide/formentor/cars-models-info-KM7-product-guide-Jan-2024.pdf",
  "title": "CUPRA Ireland — Formentor Product Guide, gennaio 2024",
  "date": None,
  "excerpt": "Formentor e-HYBRID 204 hp DSG, codice KM7BUYE: batteria 12,8 kWh e CO2 WLTP 27 g/km. La variante VZ 245 hp è distinta (32 g/km).",
}
VW_TIGUAN_24 = {
  "url": "https://www.volkswagen-newsroom.com/en/press-releases/now-available-to-order-long-range-plug-in-hybrid-drives-for-the-tiguan-from-48655-euro-18182",
  "title": "Volkswagen Newsroom — Now available to order: long-range plug-in hybrid drives for the Tiguan",
  "date": None,
  "excerpt": "Nuova Tiguan eHybrid: batteria netta 19,7 kWh; comunicato europeo include due potenze. Range fino a circa 120 km non assegnato al record non disambiguato.",
}

UPDATES: dict[str, dict] = {}
for year, s in BMW_2AT.items():
    rid = f"bmw-serie-2-active-tourer-225e-xdrive-{year}"
    UPDATES[rid] = {"year": year, "fields": {
        "batteryKWh": s["battery"], "wltpRangeKm": s["range_min"], "wltpRangeKmMax": s["range_max"]},
        "source": s, "source_fields": ["batteryKWh", "wltpRangeKm", "wltpRangeKmMax"],
        "note": "Dati BMW Italia per 225e xDrive; batteria netta 14,2 kWh (16,3 lorda); autonomia min–max WLTP trascritta senza mediare."}
for year, s in BMW_X3.items():
    rid = f"bmw-x3-phev-xdrive30e-{year}"
    UPDATES[rid] = {"year": year, "fields": {
        "batteryKWh": s["battery"], "wltpRangeKm": s["range_min"], "wltpRangeKmMax": s["range_max"]},
        "source": s, "source_fields": ["batteryKWh", "wltpRangeKm", "wltpRangeKmMax"],
        "note": "Dati BMW Italia per xDrive30e; batteria netta 11,15 kWh (12 lorda); autonomia min–max WLTP trascritta senza mediare."}
UPDATES["hyundai-tucson-phev-2023"] = {
    "year": 2023,
    "fields": {"batteryKWh": 13.8, "wltpRangeKm": 62, "weightedFuelConsumptionLPerKm": 0.014},
    "corroborate": {"co2gKm": 31}, "source": HYUNDAI_TUCSON,
    "source_fields": ["batteryKWh", "wltpRangeKm", "weightedFuelConsumptionLPerKm", "co2gKm"],
    "note": "Hyundai Cyprus (UE), scheda ufficiale MY23 1.6 T-GDi 4x4 PHEV 265 PS; capacità 13,8 kWh senza base netta/lorda dichiarata. 1,4 l/100 km è Combined WLTP, solo informativo e mai CS."}
UPDATES["toyota-rav4-phev-2023"] = {
    "year": 2023,
    "fields": {"batteryKWh": 18.1, "weightedFuelConsumptionLPerKm": 0.01},
    "corroborate": {"co2gKm": 22}, "source": TOYOTA_23,
    "source_fields": ["batteryKWh", "weightedFuelConsumptionLPerKm", "co2gKm"],
    "note": "Toyota Italia MY23; capacità 18,1 kWh senza base netta/lorda esplicitata. Consumo 1,00 l/100 km è ciclo combinato WLTP, non charge-sustaining. Autonomia di 75 km solo GR SPORT non assegnata al record generico."}
UPDATES["toyota-rav4-phev-2024"] = {
    "year": 2024,
    "fields": {"batteryKWh": 18.1, "weightedFuelConsumptionLPerKm": 0.01},
    "corroborate": {"co2gKm": 22}, "source": TOYOTA_24,
    "source_fields": ["batteryKWh", "weightedFuelConsumptionLPerKm", "co2gKm"],
    "note": "Toyota Italia MY24; capacità 18,1 kWh senza base netta/lorda esplicitata. Consumo 1,00 l/100 km è ciclo combinato WLTP, non charge-sustaining; la scheda non riporta un'autonomia attribuibile al record generico."}
UPDATES["cupra-formentor-phev-e-hybrid-2024"] = {
    "year": 2024, "fields": {"batteryKWh": 12.8}, "corroborate": {"co2gKm": 27},
    "source": CUPRA_24, "source_fields": ["batteryKWh", "co2gKm"],
    "note": "CUPRA Ireland (UE), Product Guide gennaio 2024; battery 12,8 kWh per e-HYBRID 204 hp DSG. CO2 27 g/km confermato per 204 hp; VZ 245 hp ha CO2 diverso (32). Base netta/lorda non dichiarata."
}
UPDATES["volkswagen-tiguan-phev-ehybrid-2024"] = {
    "year": 2024, "fields": {"batteryKWh": 19.7}, "source": VW_TIGUAN_24,
    "source_fields": ["batteryKWh"],
    "note": "Volkswagen Newsroom, lancio europeo nuova generazione: capacità netta 19,7 kWh. Il dato ‘fino a circa 120 km’ non è assegnato perché il comunicato include due potenze e il record non distingue la variante."
}


def json_compact(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def missing_calc_fields(row: dict) -> list[str]:
    missing: list[str] = []
    cs = row.get("fuelConsumptionLPerKm")
    if cs is None or float(cs) * 100 < 3.0:
        missing.append("fuelConsumptionLPerKm")
    energy = row.get("energyConsumptionKWhPerKm")
    if energy is None or row.get("energyIsWeighted") is True:
        missing.append("energyConsumptionKWhPerKm")
    if row.get("wltpRangeKm") is None:
        missing.append("wltpRangeKm")
    if row.get("batteryKWh") is None:
        missing.append("batteryKWh")
    return missing


def add_source(row: dict, field: str, source: dict, detail: str) -> None:
    sources = dict(row.get("fieldSources") or {})
    dates = dict(row.get("fieldSourceDates") or {})
    sources[field] = f"{source['title']}; {detail}; {source['url']}"
    if source.get("date"):
        dates[field] = source["date"]
    row["fieldSources"] = sources
    if dates:
        row["fieldSourceDates"] = dates


def normalize_source_name(row: dict, update: dict) -> None:
    text = row.get("sourceName") or ""
    text = text.replace(
        "OEM same-MY range/battery/kWh not attached (nil)",
        "OEM supplement per batteria/autonomia registrato in fieldSources",
    )
    text = re.sub(
        r"OEM same-MY EU CS L/100 \+ CD kWh/range/battery not attached → catalogDataIncomplete; weighted EEA fuel only in weightedFuelConsumptionLPerKm",
        "OEM supplement per campi ufficiali registrato in fieldSources; il consumo WLTP ponderato resta distinto da CS",
        text,
    )
    text = text.replace(
        "OEM produktkatalog live / no 2024 archive → fields nil",
        "CUPRA Ireland Product Guide Jan 2024: batteria 12,8 kWh per e-HYBRID 204 hp; CO2 27 g/km; il catalogo facelift dic-2024 non è attribuito al record EEA prior-gen",
    )
    if update["source"]["url"] not in text:
        text = f"{text}; supplemento OEM ufficiale per {', '.join(update['source_fields'])} (dettagli in fieldSources)".strip("; ")
    if "weightedFuelConsumptionLPerKm" in update["fields"]:
        text = text.replace(
            "weighted EEA fuel only in weightedFuelConsumptionLPerKm",
            "weightedFuelConsumptionLPerKm aggiornato dalla scheda OEM WLTP; non è consumo CS",
        )
        text = text.replace(
            "weighted EEA fuel remains only in weightedFuelConsumptionLPerKm",
            "weightedFuelConsumptionLPerKm aggiornato dalla scheda OEM WLTP; non è consumo CS",
        )
    row["sourceName"] = text


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def main() -> None:
    rows = json.loads(SEED.read_text(encoding="utf-8"))
    by_id = {row["id"]: row for row in rows}
    if len(by_id) != len(rows):
        raise SystemExit("duplicate vehicle IDs in seed")
    if len(rows) != 6977:
        raise SystemExit(f"unexpected seed row count: {len(rows)}")
    manifests = [json.loads(path.read_text(encoding="utf-8")) for path in MANIFESTS]
    if any(int(m.get("seedVersion") or 0) != PREV_VERSION for m in manifests):
        raise SystemExit("expected both manifests at seedVersion 75 before applying this wave")
    for rid, update in UPDATES.items():
        if rid not in by_id or int(by_id[rid].get("year", 0)) != update["year"]:
            raise SystemExit(f"missing or mismatched target record: {rid}")

    protected_before = {
        rid: (by_id[rid].get("fuelConsumptionLPerKm"), by_id[rid].get("energyConsumptionKWhPerKm"))
        for rid in UPDATES
    }
    fields_changed = []
    for rid, update in UPDATES.items():
        row = by_id[rid]
        source = update["source"]
        for field, value in update["fields"].items():
            old = row.get(field)
            if old is not None and old != value:
                if field != "weightedFuelConsumptionLPerKm":
                    raise SystemExit(f"refusing unexpected overwrite {rid}.{field}: {old} -> {value}")
            row[field] = value
            add_source(row, field, source, update["note"])
            fields_changed.append({"id": rid, "field": field, "before": old, "value": value, "source": source["url"]})
        for field, value in (update.get("corroborate") or {}).items():
            old = row.get(field)
            if old != value:
                raise SystemExit(f"corroboration differs from current value {rid}.{field}: {old} vs {value}")
            add_source(row, field, source, update["note"])
            fields_changed.append({"id": rid, "field": field, "before": old, "value": value, "source": source["url"], "provenance_only": True})
        normalize_source_name(row, update)
        row["sourceUpdatedAt"] = SOURCE_DAY
        row["missingCalcFields"] = missing_calc_fields(row)
        row["catalogDataIncomplete"] = bool(row["missingCalcFields"])
        # Keep weighted combined fuel out of the charge-sustaining calculation field.
        if row.get("fuelConsumptionLPerKm") != protected_before[rid][0] or row.get("energyConsumptionKWhPerKm") != protected_before[rid][1]:
            raise SystemExit(f"calculation field changed unexpectedly for {rid}")

    for m in manifests:
        m["seedVersion"] = NEXT_VERSION
        m["rows"] = len(rows)
        m["updatedAt"] = UPDATED_AT
        m["note"] = (
            "seedVersion 76: OEM PHEV source supplement for exact MY/variant matches; "
            "weighted fuel remains informational and no CS/CD values were inferred. "
            "See docs/audit/PHEV_SOURCE_RESEARCH_2026-11-03.md."
        )

    # Preserve the project's byte-identical minified seed representation.
    seed_text = json_compact(rows) + "\n"
    write_text(SEED, seed_text)
    for path, manifest in zip(MANIFESTS, manifests):
        manifest["bytes"] = len(seed_text.encode("utf-8"))
        write_text(path, json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    write_text(API_PRETTY, json.dumps(rows, ensure_ascii=False, indent=2) + "\n")
    write_text(API_MIN, json_compact(rows))

    report = {
        "date": SOURCE_DAY,
        "previous_seed_version": PREV_VERSION,
        "seed_version": NEXT_VERSION,
        "seed_rows": len(rows),
        "reviewed_families": 10,
        "reviewed_catalog_records": 30,
        "updated_catalog_records": len(UPDATES),
        "source_field_entries": len(fields_changed),
        "changed_or_corroborated_fields": fields_changed,
        "updated_records": [
            {"id": rid, "year": u["year"], "fields": u["fields"], "corroborated": u.get("corroborate", {}),
             "source": u["source"], "source_fields": u["source_fields"], "note": u["note"]}
            for rid, u in UPDATES.items()
        ],
        "selection_policy": "Only exact year/variant primary-source matches were applied; intervals were represented as min/max only when schema supports it; no midpoint or weighted-to-CS conversion.",
    }
    write_text(REPORT_JSON, json.dumps(report, ensure_ascii=False, indent=2) + "\n")

    # Post-write integrity checks.
    saved = json.loads(SEED.read_text(encoding="utf-8"))
    assert len(saved) == 6977 and len({r["id"] for r in saved}) == 6977
    check = {r["id"]: r for r in saved}
    assert all(check[rid]["catalogDataIncomplete"] for rid in UPDATES)
    for rid in UPDATES:
        miss = check[rid]["missingCalcFields"]
        assert "fuelConsumptionLPerKm" in miss and "energyConsumptionKWhPerKm" in miss
        assert check[rid].get("fuelConsumptionLPerKm") is None
    assert json.loads(MANIFESTS[0].read_text(encoding="utf-8"))["bytes"] == SEED.stat().st_size
    assert json.loads(MANIFESTS[1].read_text(encoding="utf-8"))["seedVersion"] == NEXT_VERSION
    print(f"Applied {len(fields_changed)} source field entries across {len(UPDATES)} records; seed v{NEXT_VERSION}, {SEED.stat().st_size} bytes.")


if __name__ == "__main__":
    main()
