#!/usr/bin/env python3
"""
Top-30 PHEV wave 3 (seed v74→v75) — same branch as PR #32.

1) Demote 4 OEM kWh values that sit next to weighted CO2/L/100 without a pure-electric
   (charge-depleting) label → weightedEnergyConsumptionKWhPerKm; nil CD energy.
2) Must-fail probes live in check_catalog_phev_top30_official.py.
3) Peugeot 3008 UK Apr-2023: keep (model+year verified).
4) Cupra Formentor e-HYBRID 2024: two powertrains — do not overwrite prior-gen 110.6 kW row.
5) 7 US/EPA stale-complete rows: catalogDataIncomplete=true + missingCalcFields.
6) Backfill fieldSources pure-electric labels on legitimate CD energies (EPA/Kuga/Terramar).

No row removals. M3 2026 untouched.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SEED = REPO / "EVforME?" / "Data" / "vehicles.seed.quality.json"
CDN = REPO / "EVforME?" / "Data" / "catalog_cdn.json"
CACHE = REPO / "scripts" / "cache" / "eea"
MANIFEST = CACHE / "catalog_phev_top30_official_manifest.json"
WAVE3_MANIFEST = CACHE / "catalog_phev_top30_wave3_manifest.json"
PREV_MANIFEST_BACKUP = CACHE / "catalog_phev_top30_official_manifest_v74.json"

SOURCE_DAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")

TOP30_MULTI = [
    "jeep-compass-phev-4xe-2022",
    "jeep-renegade-phev-4xe-2022",
    "cupra-formentor-phev-e-hybrid-2024",
    "jeep-renegade-phev-4xe-2023",
    "mini-countryman-cooper-se-all4-2023",
    "volvo-xc40-phev-recharge-2022",
    "cupra-formentor-phev-e-hybrid-2023",
    "volvo-xc40-phev-recharge-2023",
    "bmw-x1-phev-xdrive25e-2024",
    "bmw-x1-phev-xdrive25e-2022",
    "jeep-renegade-phev-4xe-2024",
    "alfa-romeo-tonale-phev-2023",
    "ford-kuga-phev-2022",
    "mercedes-benz-glc-phev-300-de-2024",
    "toyota-c-hr-phev-2024",
    "peugeot-3008-phev-2022",
    "renault-captur-phev-e-tech-phev-2022",
    "bmw-x1-phev-xdrive25e-2023",
    "mercedes-benz-gle-phev-350-de-2022",
    "peugeot-3008-phev-2023",
    "mini-countryman-cooper-se-all4-2022",
    "audi-q3-sportback-phev-45-tfsi-e-2024",
    "audi-q3-sportback-phev-45-tfsi-e-2023",
    "mercedes-benz-gla-phev-250-e-2023",
    "mercedes-benz-gle-coupe-phev-350-de-2022",
    "mercedes-benz-gla-phev-250-e-2022",
]

EPA_FALSE_COMPLETE = [
    "audi-a3-e-tron-ultra-phev-2016",
    "bmw-i3s-with-range-extender-phev-2021",
    "chevrolet-volt-phev-2019",
    "ford-c-max-energi-plug-in-hybrid-phev-2016",
    "ford-escape-fwd-phev-phev-2026",
    "honda-accord-phev-2014",
    "hyundai-ioniq-phev-2022",
]

# Wave2 wrongly stored these as CD; docs place kWh with weighted CO2/L/100 and do NOT
# label pure-electric / charge-depleting / "bei vollständig geladener Batterie".
WEIGHTED_ENERGY_DEMOTE = {
    "jeep-compass-phev-4xe-2022": {
        "kwh_per_km": 0.168,
        "url": (
            "https://www.media.stellantis.com/uploads/fr/model-document/"
            "tarifpublicnouvellejeeprcompassmy224xe2022a4jan2022-61d48676cf80a.pdf"
        ),
        "date": "2022-01-04",
        "cite": (
            "media.stellantis.com Tarif Public Nouveau Compass 4xe MY22 2022-A du 4 janvier 2022 "
            "«Consommations d'énergie électrique» 16,8–16,1 next to CO2/L/100 pondérés "
            "→ weightedEnergy 0.168 (not CD)"
        ),
    },
    "jeep-renegade-phev-4xe-2022": {
        "kwh_per_km": 0.163,
        "url": (
            "https://www.media.stellantis.com/uploads/fr/model-document/"
            "tarifpublicjeeprrenegademy222022e1erjuin2022-62ac25f07f521.pdf"
        ),
        "date": "2022-06-01",
        "cite": (
            "media.stellantis.com Tarif Public Renegade MY22 2022-E au 1er juin 2022 "
            "«Consommation d'énergie électrique» 16,3–15,6 next to CO2/L/100 pondérés "
            "→ weightedEnergy 0.163 (not CD)"
        ),
    },
    "bmw-x1-phev-xdrive25e-2022": {
        "kwh_per_km": 0.154,
        "url": "https://www.press.bmwgroup.com/italy/article/attachment/T0321361IT/520251",
        "date": "2022-01-26",
        "cite": (
            "press.bmwgroup.com BMW X1 LISTINO PREZZI (F48) Valido a partire dal 26.01.2022 "
            "«Consumo elettrico» 15,0–15,4 next to Combinato 1,7–1,9 / CO2 40–44 "
            "→ weightedEnergy 0.154 (not CD / no batteria carica)"
        ),
    },
    "toyota-c-hr-phev-2024": {
        "kwh_per_km": 0.153,
        "url": (
            "https://web.archive.org/web/20240725090934id_/"
            "https://www.toyota.de/content/dam/toyota/nmsc/germany/downloads/toyota-c-hr/"
            "Toyota_C-HR_PL_07_24_j.pdf"
        ),
        "date": "2024-07-01",
        "cite": (
            "toyota.de archive TOYOTA C-HR Preise und Fakten PL_07_24 footnote 2: "
            "«gewichtet, kombiniert: 0,8–0,9 l/100 km und 15,1–15,3 kWh/100 km» "
            "→ weightedEnergy 0.153 (explicitly gewichtet, not CD)"
        ),
    },
}

# Legitimate CD energies that lacked fieldSources pure-electric labels (needed for check #2).
PURE_ELECTRIC_BACKFILL = {
    "ford-kuga-phev-2024": {
        "cite": (
            "ford.de Technische Daten Kuga: Stromverbrauch bei rein elektrischem Betrieb "
            "kombiniert 20,9–18,4 → 0.209 (solo elettrico / charge-depleting) "
            "https://www.ford.de/content/dam/guxeu/de/documents/price-list/cars/new-kuga/"
            "Technische_Daten_des_Ford_Kuga.pdf"
        ),
        "date": "2024-05-01",
    },
    "ford-kuga-phev-2023": {
        "cite": (
            "ford.de Technische Daten Kuga via stessa omologazione EEA: Stromverbrauch bei "
            "rein elektrischem Betrieb kombiniert 20,9–18,4 → 0.209 "
            "(solo elettrico / charge-depleting) "
            "https://www.ford.de/content/dam/guxeu/de/documents/price-list/cars/new-kuga/"
            "Technische_Daten_des_Ford_Kuga.pdf"
        ),
        "date": "2024-05-01",
    },
    "cupra-terramar-e-hybrid-2025": {
        "cite": (
            "CUPRA Terramar catalogue June 2025: charge-depleting electric 17.6–19.0 → 0.19 "
            "(solo elettrico / charge-depleting) "
            "https://www.cupraofficial.com/content/dam/public/cupra-website/cars/terramar/"
            "broachure/cupra-terramar-catalogue-june-2025.pdf"
        ),
        "date": "2025-06-01",
    },
}


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


def finalize(row: dict) -> None:
    if row.get("energyConsumptionKWhPerKm") is None and row.get(
        "weightedEnergyConsumptionKWhPerKm"
    ) is not None:
        row["energyIsWeighted"] = True
    miss = missing_calc_fields(row)
    row["missingCalcFields"] = miss
    row["catalogDataIncomplete"] = bool(miss)
    if miss and row.get("confidenceScore") is None:
        row["confidenceScore"] = 0.7


def counts(rows):
    complete = only_kwh = multi = 0
    for r in rows:
        miss = missing_calc_fields(r)
        if not miss:
            complete += 1
        elif miss == ["energyConsumptionKWhPerKm"]:
            only_kwh += 1
        else:
            multi += 1
    return complete, only_kwh, multi


def demote_weighted_energy(row: dict, meta: dict, fields_changed: list) -> dict:
    before = {
        "energyConsumptionKWhPerKm": row.get("energyConsumptionKWhPerKm"),
        "weightedEnergyConsumptionKWhPerKm": row.get("weightedEnergyConsumptionKWhPerKm"),
        "energyIsWeighted": row.get("energyIsWeighted"),
        "catalogDataIncomplete": row.get("catalogDataIncomplete"),
        "missingCalcFields": list(row.get("missingCalcFields") or []),
    }
    val = float(meta["kwh_per_km"])
    cur = row.get("energyConsumptionKWhPerKm")
    if cur is None or abs(float(cur) - val) > 1e-9:
        raise SystemExit(
            f"{row['id']}: expected energy {val}, got {cur}"
        )
    row["energyConsumptionKWhPerKm"] = None
    row["weightedEnergyConsumptionKWhPerKm"] = val
    row["energyIsWeighted"] = True
    fs = dict(row.get("fieldSources") or {})
    fd = dict(row.get("fieldSourceDates") or {})
    fs.pop("energyConsumptionKWhPerKm", None)
    fd.pop("energyConsumptionKWhPerKm", None)
    fs["weightedEnergyConsumptionKWhPerKm"] = f"{meta['cite']} {meta['url']}".strip()
    fd["weightedEnergyConsumptionKWhPerKm"] = meta["date"]
    row["fieldSources"] = fs
    row["fieldSourceDates"] = fd
    sn = row.get("sourceName") or ""
    note = (
        f"wave3: kWh {val} demoted to weightedEnergyConsumptionKWhPerKm "
        f"(doc places énergie/Strom with ponderati / gewichtet, no pure-CD label) — {meta['url']}"
    )
    if "wave3: kWh" not in sn:
        row["sourceName"] = f"{sn}; {note}".strip("; ").strip()
    row["sourceUpdatedAt"] = SOURCE_DAY
    finalize(row)
    after = {
        "energyConsumptionKWhPerKm": row.get("energyConsumptionKWhPerKm"),
        "weightedEnergyConsumptionKWhPerKm": row.get("weightedEnergyConsumptionKWhPerKm"),
        "energyIsWeighted": row.get("energyIsWeighted"),
        "catalogDataIncomplete": row.get("catalogDataIncomplete"),
        "missingCalcFields": list(row.get("missingCalcFields") or []),
    }
    fields_changed.append(
        {
            "id": row["id"],
            "field": "energyConsumptionKWhPerKm→weightedEnergyConsumptionKWhPerKm",
            "before": before["energyConsumptionKWhPerKm"],
            "after": after["weightedEnergyConsumptionKWhPerKm"],
            "sourceDate": meta["date"],
            "url": meta["url"],
            "via": "same_my",
            "TAN": None,
            "note": "demoted: no pure-electric label in document",
        }
    )
    return {"id": row["id"], "before": before, "after": after}


def main() -> None:
    seed = json.loads(SEED.read_text(encoding="utf-8"))
    cdn = json.loads(CDN.read_text(encoding="utf-8"))
    prev = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if not PREV_MANIFEST_BACKUP.exists():
        PREV_MANIFEST_BACKUP.write_text(json.dumps(prev, indent=2) + "\n")
    by_id = {r["id"]: r for r in seed}
    ids_before = [r["id"] for r in seed]
    m3_before = {
        r["id"]: json.dumps(r, sort_keys=True)
        for r in seed
        if r["id"].startswith("tesla-model-3") and r.get("year") == 2026
    }

    parents = [r for r in seed if r.get("powertrain") == "phev" and not r.get("parentId")]
    c0, k0, m0 = counts(parents)

    top30 = [by_id[i] for i in TOP30_MULTI if i in by_id]
    t0c, t0k, t0m = counts(top30)

    fields_changed: list[dict] = []
    energy_demotions: list[dict] = []
    epa_hygiene: list[dict] = []
    pure_backfill: list[str] = []
    cupra_note: dict = {}

    # --- 1) Demote weighted-as-CD energies ---
    for rid, meta in WEIGHTED_ENERGY_DEMOTE.items():
        energy_demotions.append(demote_weighted_energy(by_id[rid], meta, fields_changed))

    # --- 3) Peugeot UK: verify model/year, keep ---
    peu = by_id["peugeot-3008-phev-2023"]
    if peu.get("year") != 2023 or "3008" not in (peu.get("model") or ""):
        raise SystemExit("peugeot 3008 year/model mismatch")
    peugeot_verify = {
        "id": peu["id"],
        "model": peu.get("model"),
        "year": peu.get("year"),
        "market": peu.get("market"),
        "sourceDate": (peu.get("fieldSourceDates") or {}).get("wltpRangeKm"),
        "url": (
            "https://www.media.stellantis.com/uploads/uk/model-pricelist/"
            "peugeot3008pricespecapr23-6455a65377d74.pdf"
        ),
        "doc_title": "PEUGEOT 3008 Pricelist — Effective from 1st April 2023",
        "doc_model_year": "2023.25 Model Year (G2)",
        "action": "kept",
    }

    # --- 4) Cupra: two versions — do not overwrite ---
    cupra = by_id["cupra-formentor-phev-e-hybrid-2024"]
    cupra_note = {
        "seed_id": cupra["id"],
        "seed_powerKw": cupra.get("powerKw"),
        "seed_batteryKWh": cupra.get("batteryKWh"),
        "seed_status": "incomplete (EEA prior-gen ~110.6 kW registrations)",
        "catalogue_2024_12": {
            "url": (
                "https://www.cupra.com/content/dam/public/cupra-website/generic/pdf/"
                "cupra-formentor-catalogue-dic-2024.pdf"
            ),
            "variants": [
                {"name": "1.5 e-HYBRID 150 kW", "system_kW": 150, "battery_kWh": 25.8},
                {"name": "1.5 e-HYBRID 200 kW", "system_kW": 200, "battery_kWh": 25.8},
            ],
            "cite_lines": (
                "ENGINE SPECS «1.5 e-HYBRID 150 KW 6-SPEED DSG» Max. power 150 (204); "
                "Battery capacity (kWh) 25,8; Charge sustaining 5.4–5.8; "
                "Electric consumption combined WLTP 16.1–17.2; Electric range 125–115"
            ),
        },
        "decision": (
            "TWO versions: seed row matches EEA IT 2024 FORMENTOR E-HYBRID ~110.6 kW "
            "(prior-gen still registered). Dic-2024 catalogue documents the facelift "
            "150/200 kW + 25.8 kWh. Do NOT overwrite the 110.6 row. Proceed by adding "
            "a new variant id (e.g. cupra-formentor-phev-e-hybrid-150kw-2024) in a later "
            "wave — no row removals this wave."
        ),
        "action": "left_incomplete_no_overwrite",
    }
    sn = cupra.get("sourceName") or ""
    cupra_src = (
        "wave3: Cupra Formentor catalogue dic-2024 is 150/200 kW + 25.8 kWh facelift; "
        "seed powerKw 110.6 = prior-gen EEA — kept incomplete, no overwrite "
        "https://www.cupra.com/content/dam/public/cupra-website/generic/pdf/"
        "cupra-formentor-catalogue-dic-2024.pdf"
    )
    if "wave3: Cupra Formentor" not in sn:
        cupra["sourceName"] = f"{sn}; {cupra_src}".strip("; ").strip()
        cupra["sourceUpdatedAt"] = SOURCE_DAY
    finalize(cupra)

    # --- 5) EPA flag hygiene ---
    for rid in EPA_FALSE_COMPLETE:
        r = by_id[rid]
        if (r.get("market") or "").upper() != "US/EPA":
            raise SystemExit(f"{rid}: expected US/EPA")
        before = {
            "catalogDataIncomplete": r.get("catalogDataIncomplete"),
            "missingCalcFields": r.get("missingCalcFields"),
            "batteryKWh": r.get("batteryKWh"),
        }
        miss = missing_calc_fields(r)
        if miss != ["batteryKWh"]:
            raise SystemExit(f"{rid}: expected only batteryKWh missing, got {miss}")
        if r.get("batteryKWh") is not None:
            raise SystemExit(f"{rid}: battery unexpectedly present")
        r["missingCalcFields"] = miss
        r["catalogDataIncomplete"] = True
        if r.get("confidenceScore") is None:
            r["confidenceScore"] = 0.7
        # Pure-electric label for existing CD energy (EPA CD is charge-depleting).
        fs = dict(r.get("fieldSources") or {})
        fd = dict(r.get("fieldSourceDates") or {})
        e = r.get("energyConsumptionKWhPerKm")
        fs["energyConsumptionKWhPerKm"] = (
            f"EPA-FuelEconomy charge-depleting (solo elettrico / CD) electricity "
            f"→ {e} kWh/km; batteryKWh absent in this EPA extract"
        )
        fd["energyConsumptionKWhPerKm"] = str(r.get("year") or "")
        r["fieldSources"] = fs
        r["fieldSourceDates"] = fd
        after = {
            "catalogDataIncomplete": r.get("catalogDataIncomplete"),
            "missingCalcFields": list(r.get("missingCalcFields") or []),
            "batteryKWh": r.get("batteryKWh"),
        }
        epa_hygiene.append({"id": rid, "before": before, "after": after})

    # --- 2 support: backfill pure-electric fieldSources on remaining CD energies ---
    for rid, meta in PURE_ELECTRIC_BACKFILL.items():
        r = by_id[rid]
        if r.get("energyConsumptionKWhPerKm") is None:
            raise SystemExit(f"{rid}: expected CD energy")
        fs = dict(r.get("fieldSources") or {})
        fd = dict(r.get("fieldSourceDates") or {})
        if "solo elettrico" not in (fs.get("energyConsumptionKWhPerKm") or "").lower() and \
           "charge-depleting" not in (fs.get("energyConsumptionKWhPerKm") or "").lower():
            fs["energyConsumptionKWhPerKm"] = meta["cite"]
            fd["energyConsumptionKWhPerKm"] = meta["date"]
            r["fieldSources"] = fs
            r["fieldSourceDates"] = fd
            pure_backfill.append(rid)
        finalize(r)

    # Re-finalize demoted rows already done; ensure all parents coherent for complete check
    for r in parents:
        if r["id"] in WEIGHTED_ENERGY_DEMOTE or r["id"] in EPA_FALSE_COMPLETE:
            continue
        # Do not mass-finalize untouched rows (would rewrite missingCalcFields shapes).
        pass

    # Safety: no complete PHEV with nil calc field
    bad_complete = [
        {"id": r["id"], "miss": missing_calc_fields(r)}
        for r in parents
        if not r.get("catalogDataIncomplete") and missing_calc_fields(r)
    ]
    if bad_complete:
        raise SystemExit(f"complete_with_nil_calc: {bad_complete}")

    # M3 + row set
    for r in seed:
        if r["id"] in m3_before and json.dumps(r, sort_keys=True) != m3_before[r["id"]]:
            raise SystemExit(f"M3 2026 altered: {r['id']}")
    if set(ids_before) != {r["id"] for r in seed}:
        raise SystemExit("row set changed")

    parents = [r for r in seed if r.get("powertrain") == "phev" and not r.get("parentId")]
    c1, k1, m1 = counts(parents)
    top30 = [by_id[i] for i in TOP30_MULTI if i in by_id]
    t1c, t1k, t1m = counts(top30)

    new_ver = int(cdn.get("seedVersion") or 74) + 1
    if new_ver != 75:
        raise SystemExit(f"expected seed 75, got {new_ver}")
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
        **prev,
        "seedVersion": new_ver,
        "prevSeedVersion": 74,
        "ids_before": ids_before,
        "phev_complete_before": c0,
        "phev_only_kwh_before": k0,
        "phev_multi_missing_before": m0,
        "phev_complete_after": c1,
        "phev_only_kwh_after": k1,
        "phev_multi_missing_after": m1,
        "top30_complete_before": t0c,
        "top30_only_kwh_before": t0k,
        "top30_multi_missing_before": t0m,
        "top30_complete_after": t1c,
        "top30_only_kwh_after": t1k,
        "top30_multi_missing_after": t1m,
        "wave3_energy_demotions": energy_demotions,
        "wave3_fields_changed": fields_changed,
        "wave3_epa_hygiene": epa_hygiene,
        "wave3_peugeot_verify": peugeot_verify,
        "wave3_cupra_note": cupra_note,
        "wave3_pure_electric_backfill": pure_backfill,
    }
    MANIFEST.write_text(json.dumps(man, indent=2) + "\n")
    WAVE3_MANIFEST.write_text(json.dumps(man, indent=2) + "\n")
    print(
        json.dumps(
            {
                "seedVersion": new_ver,
                "counts": {"before": [c0, k0, m0], "after": [c1, k1, m1]},
                "top30": {"before": [t0c, t0k, t0m], "after": [t1c, t1k, t1m]},
                "demotions": [d["id"] for d in energy_demotions],
                "epa": [e["id"] for e in epa_hygiene],
                "cupra": cupra_note["decision"][:120],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
