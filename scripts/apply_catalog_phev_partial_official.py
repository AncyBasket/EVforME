#!/usr/bin/env python3
"""
PHEV partial official fields (seed +1):

Fill CS / EAER / battery / unweighted CD when an official same-MY OEM source
(or identical EEA homologation from a non-derived year) publishes them.
Never copy weighted kWh into energyConsumptionKWhPerKm.
Sets fieldSources + missingCalcFields; catalogDataIncomplete = bool(missing).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
SEED = REPO / "EVforME?" / "Data" / "vehicles.seed.quality.json"
CDN = REPO / "EVforME?" / "Data" / "catalog_cdn.json"
CACHE = REPO / "scripts" / "cache" / "eea"
HOMOLOG = CACHE / "catalog_phev_homologation_map.json"
RANK = CACHE / "catalog_phev_it_incomplete_rank.json"
MANIFEST = CACHE / "catalog_phev_partial_official_manifest.json"
SOURCE_DAY = "2026-10-27"

CALC_FIELDS = (
    "fuelConsumptionLPerKm",
    "energyConsumptionKWhPerKm",
    "wltpRangeKm",
    "batteryKWh",
)

# Same-MY official partial fills (prudent: high CS, low range). No unweighted CD here.
SAME_MY_PARTIAL: list[dict[str, Any]] = [
    {
        "id": "bmw-x1-phev-xdrive25e-2024",
        "host": "bmw.de",
        "year": 2024,
        "url": "https://www.bmw.de/content/dam/bmw/marketDE/bmw_de/new-vehicles/pricelists/preisliste-bmwx1.pdf.coredownload.pdf",
        "fields": {
            "fuelConsumptionLPerKm": 0.062,  # within 6,5–6,0
            "wltpRangeKm": 76,  # 76–83
            "batteryKWh": 14.2,  # Netto
        },
        "weighted": {
            "weightedEnergyConsumptionKWhPerKm": 0.138,  # 13,8–13,3 gewichtet
            "weightedFuelConsumptionLPerKm": 0.028,  # 2,8–2,4 gewichtet
        },
        "note": "BMW X1 xDrive25e Preisliste: CS bei entladener Batterie; EAER; Batterie netto; Stromverbrauch nur gewichtet",
    },
    {
        "id": "volvo-xc60-phev-recharge-2024",
        "host": "volvocars.com",
        "year": 2024,
        "url": "https://www.volvocars.com/de/media/press-releases/8C5F873BBE0D5162/",
        "fields": {
            "fuelConsumptionLPerKm": 0.082,  # 8,2–7,0
            "wltpRangeKm": 80,
            "batteryKWh": 18.8,
        },
        "weighted": {
            "weightedEnergyConsumptionKWhPerKm": 0.209,  # 20,9–18,0
            "weightedFuelConsumptionLPerKm": 0.014,  # 1,4–0,9
        },
        "note": "Volvo XC60 Plug-in-Hybrid press 01.06.2024: CS bei entladener Batterie; bis 80 km; 18,8 kWh; Strom nur gewichtet",
    },
    {
        "id": "toyota-c-hr-phev-2024",
        "host": "toyota.de",
        "year": 2024,
        "url": "https://www.toyota.de/content/dam/toyota/nmsc/germany/downloads/toyota-c-hr/Toyota_C-HR_PL_07_24_j.pdf",
        "fields": {
            "fuelConsumptionLPerKm": 0.049,  # 4,9
            "wltpRangeKm": 66,  # 66–67
        },
        "weighted": {
            "weightedEnergyConsumptionKWhPerKm": 0.153,  # 15,1–15,3
            "weightedFuelConsumptionLPerKm": 0.009,  # 0,8–0,9
        },
        "note": "Toyota C-HR Plug-in Preisliste 07/2024: CS bei entladener Batterie; EAER; Strom nur gewichtet",
    },
    {
        "id": "jeep-renegade-phev-4xe-2024",
        "host": "jeep.de",
        "year": 2024,
        "url": "https://www.jeep.de/hybrid-suv",
        "fields": {
            "fuelConsumptionLPerKm": 0.076,  # 6,8–7,6
        },
        "weighted": {
            "weightedEnergyConsumptionKWhPerKm": 0.192,  # 17,4–19,2
            "weightedFuelConsumptionLPerKm": 0.025,  # 2,0–2,5
        },
        "note": "Jeep Renegade 4xe jeep.de: CS bei entladener Batterie; Strom nur gewichtet",
    },
    {
        "id": "jeep-compass-phev-4xe-2024",
        "host": "jeep.de",
        "year": 2024,
        "url": "https://www.jeep.de/jeep-compass/plug-in-hybrid",
        "fields": {
            "fuelConsumptionLPerKm": 0.074,  # within 6,9–7,6
            "wltpRangeKm": 56,
        },
        "weighted": {
            "weightedEnergyConsumptionKWhPerKm": 0.193,  # 17,3–19,3
            "weightedFuelConsumptionLPerKm": 0.024,  # 2–2,4
        },
        "note": "Jeep Compass 4xe jeep.de: CS bei entladener Batterie; fino a 56 km; Strom nur gewichtet",
    },
    {
        "id": "cupra-formentor-phev-e-hybrid-2024",
        "host": "cupra.de",
        "year": 2024,
        "url": "https://produktkatalog.cupra.de/clp/cupra-formentor-hws/?bnr=43044",
        "fields": {
            "fuelConsumptionLPerKm": 0.057,  # within 5,3–5,6 (150 kW / ICE ~110)
        },
        "weighted": {
            "weightedEnergyConsumptionKWhPerKm": 0.139,  # 13,2–13,9
            "weightedFuelConsumptionLPerKm": 0.016,  # 1,4–1,6
        },
        "note": "CUPRA Formentor 1.5 e-HYBRID 150 kW produktkatalog: CS bei entladener Batterie; Strom nur gewichtet",
    },
    {
        "id": "audi-q3-sportback-phev-45-tfsi-e-2024",
        "host": "audi.de",
        "year": 2024,
        "url": "https://www.audi.de/de/brand/de/neuwagen.html",
        "fields": {
            "fuelConsumptionLPerKm": 0.072,  # 7,2–6,6
        },
        "weighted": {
            "weightedEnergyConsumptionKWhPerKm": 0.179,  # 17,9–16,8
        },
        "note": "Audi Q3 Sportback TFSI e audi.de: CS bei entladener Batterie; Strom nur gewichtet",
    },
    {
        "id": "bmw-serie-2-active-tourer-225e-xdrive-2023",
        "host": "bmw.de",
        "year": 2023,
        "url": "https://www.bmw.de/content/dam/bmw/marketDE/bmw_de/mybmw/bmw-efficientdynamics/SP-1619_CO2_A4_Vergleich_Emissionswerte_05_2024_X4_05.pdf.coredownload.inline.pdf",
        "fields": {
            "fuelConsumptionLPerKm": 0.064,  # EnVKV 05/2024 225e actual config high 6,4
            "wltpRangeKm": 81,  # generation WLTP low from bmw.de tech (81–87)
            "batteryKWh": 14.2,
        },
        "weighted": {
            "weightedEnergyConsumptionKWhPerKm": 0.181,  # 18,1 + 0,9 gewichtet
            "weightedFuelConsumptionLPerKm": 0.009,
        },
        "note": "BMW 225e xDrive Active Tourer EnVKV 05/2024 + tech: CS; EAER/Batterie generazione U06; Strom solo gewichtet",
    },
]

# Homologation: copy partial fields from src → dst when shared fingerprint matches.
HOMOLOG_DERIVE = [
    {
        "dst_id": "bmw-x1-phev-xdrive25e-2023",
        "src_id": "bmw-x1-phev-xdrive25e-2024",
        "family": "bmw-x1-25e",
    },
    {
        "dst_id": "volvo-xc60-phev-recharge-2023",
        "src_id": "volvo-xc60-phev-recharge-2024",
        "family": "volvo-xc60",
        "ep_tol": 8.0,  # catalog powerKw ~190 vs EEA ep 186
    },
    {
        "dst_id": "jeep-renegade-phev-4xe-2023",
        "src_id": "jeep-renegade-phev-4xe-2024",
        "family": "jeep-renegade",
        "ep_tol": 6.0,  # catalog ~100 vs EEA ep 96
    },
    {
        "dst_id": "jeep-compass-phev-4xe-2023",
        "src_id": "jeep-compass-phev-4xe-2024",
        "family": "jeep-compass",
        "ep_tol": 12.0,  # catalog ~105–107 vs EEA ep 96
    },
    {
        "dst_id": "audi-q3-sportback-phev-45-tfsi-e-2023",
        "src_id": "audi-q3-sportback-phev-45-tfsi-e-2024",
        "family": "audi-q3-sb",
    },
]


def missing_calc_fields(r: dict) -> list[str]:
    miss: list[str] = []
    cs = r.get("fuelConsumptionLPerKm")
    if cs is None or float(cs) * 100 < 3.0:
        miss.append("fuelConsumptionLPerKm")
    e = r.get("energyConsumptionKWhPerKm")
    if e is None or r.get("energyIsWeighted") is True:
        miss.append("energyConsumptionKWhPerKm")
    if r.get("wltpRangeKm") is None:
        miss.append("wltpRangeKm")
    if r.get("batteryKWh") is None:
        miss.append("batteryKWh")
    return miss


def best_shared(
    family: str, src_year: int, dst_year: int, dst_power: float, shared: dict, ep_tol: float
) -> dict | None:
    cands = []
    for sh in shared.get(family) or []:
        years = {int(y): n for y, n in (sh.get("years") or {}).items()}
        if src_year not in years or dst_year not in years:
            continue
        if not (sh.get("TAN") or "").strip():
            continue
        ep = sh.get("ep")
        if ep is None:
            continue
        if abs(float(ep) - float(dst_power)) > ep_tol:
            continue
        score = float(years[src_year]) + float(years[dst_year])
        cands.append((score, sh))
    if not cands:
        return None
    cands.sort(key=lambda x: -x[0])
    return cands[0][1]


def apply_fields(row: dict, fields: dict, sources: dict, note: str) -> list[str]:
    applied = []
    fs = dict(row.get("fieldSources") or {})
    for k, v in fields.items():
        if v is None:
            continue
        row[k] = v
        fs[k] = sources[k]
        applied.append(k)
    if note:
        base = row.get("sourceName") or ""
        if note not in base:
            row["sourceName"] = f"{base}; {note}".strip("; ").strip()
    row["fieldSources"] = fs
    row["sourceUpdatedAt"] = SOURCE_DAY
    row["market"] = row.get("market") or "IT"
    if row.get("energyIsWeighted") is True and row.get("energyConsumptionKWhPerKm") is not None:
        # Never leave weighted value in calc field.
        row["energyConsumptionKWhPerKm"] = None
    row["energyIsWeighted"] = False if row.get("energyConsumptionKWhPerKm") is not None else row.get(
        "energyIsWeighted"
    )
    miss = missing_calc_fields(row)
    row["missingCalcFields"] = miss
    row["catalogDataIncomplete"] = bool(miss)
    if miss and row.get("confidenceScore") is None:
        row["confidenceScore"] = 0.7
    return applied


def main() -> None:
    seed = json.loads(SEED.read_text(encoding="utf-8"))
    by_id = {r["id"]: r for r in seed}
    ids_before = [r["id"] for r in seed]
    m3_before = {
        r["id"]: json.dumps(r, sort_keys=True)
        for r in seed
        if r["id"].startswith("tesla-model-3") and r.get("year") == 2026
    }

    parents = [r for r in seed if r.get("powertrain") == "phev" and not r.get("parentId")]

    def counts():
        complete = sum(1 for r in parents if not r.get("catalogDataIncomplete"))
        only_kwh = 0
        multi = 0
        for r in parents:
            if not r.get("catalogDataIncomplete"):
                continue
            miss = missing_calc_fields(r)
            if miss == ["energyConsumptionKWhPerKm"]:
                only_kwh += 1
            else:
                multi += 1
        return complete, only_kwh, multi

    before_c, before_kwh, before_multi = counts()

    rank = json.loads(RANK.read_text(encoding="utf-8"))
    regs = {}
    for e in (rank.get("all_incomplete") or []) + (rank.get("top") or []):
        rid = e["id"] if isinstance(e, dict) else e
        regs[rid] = e.get("regs") or e.get("n") or regs.get(rid) or 0

    fields_saved: list[dict] = []
    same_my_touched: list[str] = []

    for spec in SAME_MY_PARTIAL:
        rid = spec["id"]
        row = by_id[rid]
        if int(row["year"]) != int(spec["year"]):
            raise SystemExit(f"year mismatch {rid}")
        sources = {
            k: f"{spec['host']} {spec['year']} {spec['url']}" for k in spec["fields"]
        }
        applied = apply_fields(row, spec["fields"], sources, spec.get("note") or "")
        for wk, wv in (spec.get("weighted") or {}).items():
            row[wk] = wv
        # Never put weighted into calc energy.
        if "energyConsumptionKWhPerKm" not in spec["fields"]:
            if row.get("energyIsWeighted") is True:
                row["energyConsumptionKWhPerKm"] = None
            row["energyIsWeighted"] = (
                False if row.get("energyConsumptionKWhPerKm") is not None else None
            )
        miss = missing_calc_fields(row)
        row["missingCalcFields"] = miss
        row["catalogDataIncomplete"] = bool(miss)
        same_my_touched.append(rid)
        for k in applied:
            fields_saved.append(
                {
                    "id": rid,
                    "field": k,
                    "host": spec["host"],
                    "year": spec["year"],
                    "url": spec["url"],
                    "value": row[k],
                    "via": "same_my",
                }
            )

    homolog = json.loads(HOMOLOG.read_text(encoding="utf-8"))
    shared = homolog.get("shared") or {}
    derived_touched: list[dict] = []

    for d in HOMOLOG_DERIVE:
        dst = by_id[d["dst_id"]]
        src = by_id[d["src_id"]]
        if src.get("dataDerivedFromSameHomologationYear") is not None:
            raise SystemExit(f"chain forbidden: {d['src_id']}")
        # Source must have at least one official partial field.
        src_fs = src.get("fieldSources") or {}
        if not any(k in src_fs for k in CALC_FIELDS if src.get(k) is not None):
            # allow if same-MY just applied in this run
            if d["src_id"] not in same_my_touched:
                raise SystemExit(f"source has no fieldSources {d['src_id']}")
        sh = best_shared(
            d["family"],
            int(src["year"]),
            int(dst["year"]),
            float(dst.get("powerKw") or 0),
            shared,
            float(d.get("ep_tol") or 2.0),
        )
        if not sh:
            print(f"SKIP homolog {d['dst_id']}: no shared fingerprint")
            continue
        copy = {}
        sources = {}
        tan = sh["TAN"]
        va, ve = sh["Va"], sh["Ve"]
        for k in CALC_FIELDS:
            if src.get(k) is None:
                continue
            if k == "energyConsumptionKWhPerKm" and src.get("energyIsWeighted") is True:
                continue
            if k == "fuelConsumptionLPerKm" and float(src[k]) * 100 < 3.0:
                continue
            copy[k] = src[k]
            src_cite = (src.get("fieldSources") or {}).get(k) or (src.get("sourceName") or "OEM")
            sources[k] = (
                f"{src_cite}; stessa omologazione EEA {tan} {va}/{ve}, "
                f"anni {dst['year']} e {src['year']}"
            )
        if not copy:
            print(f"SKIP homolog {d['dst_id']}: nothing to copy")
            continue
        for wk in ("weightedFuelConsumptionLPerKm", "weightedEnergyConsumptionKWhPerKm"):
            if src.get(wk) is not None:
                dst[wk] = src[wk]
        note = (
            f"stessa omologazione EEA {tan} {va}/{ve}, anni {dst['year']} e {src['year']} "
            f"(campi parziali da MY{src['year']})"
        )
        applied = apply_fields(dst, copy, sources, note)
        dst["dataDerivedFromSameHomologationYear"] = int(src["year"])
        derived_touched.append(
            {
                "id": d["dst_id"],
                "sourceId": d["src_id"],
                "TAN": tan,
                "Va": va,
                "Ve": ve,
                "ep": sh.get("ep"),
                "fields": applied,
                "derivedFromYear": int(src["year"]),
            }
        )
        for k in applied:
            fields_saved.append(
                {
                    "id": d["dst_id"],
                    "field": k,
                    "host": "eea+oem",
                    "year": int(dst["year"]),
                    "url": (src.get("fieldSources") or {}).get(k, ""),
                    "value": dst[k],
                    "via": "homologation",
                    "TAN": tan,
                }
            )

    # Recompute missing for all touched + ensure consistency on all incomplete PHEV parents.
    for r in parents:
        miss = missing_calc_fields(r)
        if r.get("catalogDataIncomplete") or r.get("missingCalcFields") is not None or r["id"] in same_my_touched:
            r["missingCalcFields"] = miss
            r["catalogDataIncomplete"] = bool(miss)

    for r in seed:
        if r["id"] in m3_before and json.dumps(r, sort_keys=True) != m3_before[r["id"]]:
            raise SystemExit(f"M3 2026 altered: {r['id']}")

    after_c, after_kwh, after_multi = counts()

    # Top 30 by regs among PHEV parents
    ranked = sorted(parents, key=lambda r: -float(regs.get(r["id"]) or 0))
    top30 = ranked[:30]

    def top_bucket(rows):
        c = sum(1 for r in rows if not r.get("catalogDataIncomplete"))
        kwh = sum(
            1
            for r in rows
            if r.get("catalogDataIncomplete")
            and missing_calc_fields(r) == ["energyConsumptionKWhPerKm"]
        )
        multi = sum(
            1
            for r in rows
            if r.get("catalogDataIncomplete")
            and missing_calc_fields(r) != ["energyConsumptionKWhPerKm"]
        )
        return c, kwh, multi

    # before top30 approximated from pre-apply would need snapshot; store after only + overall before
    top30_after = top_bucket(top30)

    cdn = json.loads(CDN.read_text(encoding="utf-8"))
    new_ver = int(cdn.get("seedVersion") or 68) + 1
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

    man = {
        "seedVersion": new_ver,
        "ids_before": ids_before,
        "phev_complete_before": before_c,
        "phev_complete_after": after_c,
        "phev_only_kwh_before": before_kwh,
        "phev_only_kwh_after": after_kwh,
        "phev_multi_missing_before": before_multi,
        "phev_multi_missing_after": after_multi,
        "top30_complete_after": top30_after[0],
        "top30_only_kwh_after": top30_after[1],
        "top30_multi_missing_after": top30_after[2],
        "same_my_ids": same_my_touched,
        "derived": derived_touched,
        "fields_saved": fields_saved,
    }
    MANIFEST.write_text(json.dumps(man, indent=2) + "\n")
    print(
        json.dumps(
            {k: v for k, v in man.items() if k not in ("ids_before", "fields_saved")},
            indent=2,
        )
    )
    print("fields_saved_count", len(fields_saved))


if __name__ == "__main__":
    main()
