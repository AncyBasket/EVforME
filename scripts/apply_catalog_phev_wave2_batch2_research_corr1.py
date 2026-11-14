#!/usr/bin/env python3
"""
PHEV wave2 batch2 CHANGES NEEDED corr1 (seed 84→85).

- X3 30e 2024: add CS 0.079; sourceDate 2024-06-19 from press T0443191EL + attachment
- X1 30e 2023: re-cite mportal U11-11-2023.PDF (Ausgabe 1, 27.09.2023)
- Fill additional OEM-dated rows; rebuild left_nil with exact document URLs (no hub-only)
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
from catalog_confidence import POLICY_VERSION, assess_confidence  # noqa: E402
from check_catalog_phev_wave2_batch2 import cite_dating_ok, is_generic_url, urls_in  # noqa: E402
from lib.phev_manus_v76_validate import missing_calc_fields  # noqa: E402

SEED = REPO / "EVforME?" / "Data" / "vehicles.seed.quality.json"
CDN = REPO / "EVforME?" / "Data" / "catalog_cdn.json"
CACHE = REPO / "scripts" / "cache" / "eea"
INVENTORY = CACHE / "catalog_phev_wave2_batch2_inventory.json"
MANIFEST = CACHE / "catalog_phev_wave2_batch2_manifest.json"
SOURCE_DAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")
NON_PHEV_SHA = "6b9038232bc51daabc9e259fc0dab170f787984d4dfb8f597e309fe50155b4dc"
CALC_FIELDS = (
    "fuelConsumptionLPerKm",
    "energyConsumptionKWhPerKm",
    "wltpRangeKm",
    "batteryKWh",
)

AUDI_Q5SB = (
    "https://uploads.audi-mediacenter.com/system/production/car_motorizations/1248/"
    "file_en/c1fb637963ddfcca84570a97029625208ff83ace/"
    "eTD-Audi-Q5-Sportback-50-TFSIe-quattro-S_tronic-220kW_240604.pdf"
)
BMW_AT_U06 = "https://cdn.mportal.de/CDN/pdf/U06-11-2023.PDF"
BMW_X1_U11 = "https://cdn.mportal.de/CDN/pdf/U11-11-2023.PDF"
X3_PRESS = (
    "https://www.press.bmwgroup.com/greece/article/detail/T0443191EL/"
    "%CE%B7-%CE%BD%CE%AD%CE%B1-bmw-x3?language=el"
)
X3_ATTACH = "https://www.press.bmwgroup.com/greece/article/attachment/T0443191EL/618258"
C5_DE_PRESS = (
    "https://www.media.stellantis.com/de-de/citroen/press/"
    "Jetzt-noch-weiter-elektrisch_Citroen-C5-Aircross-und-C5-X-Hybrid-Modelle-mit-mehr-Reichweite"
)
C5_DE_JAN23 = (
    "https://www.media.stellantis.com/de-de/citroen/press/"
    "Citroen-C5-Aircross_Neue-Hybrid-Einstiegsmotorisierung-ab-sofort-bestellbar"
)
C5_UK_JAN23 = (
    "https://www.media.stellantis.com/uploads/uk/model-pricelist/"
    "citroenc5aircrosspricespecjan2023-63a9aed6b1132.pdf"
)
DS7_DE_MAR24 = (
    "https://www.media.stellantis.com/uploads/de/model-document/"
    "preisliste_ds_7_my42_25marz2024-6616563ea3f2c.pdf"
)
DS7_PT_MAR23 = (
    "https://www.media.stellantis.com/uploads/pt/attachment/3512/"
    "informacaodeprodutods7termicoeds7etense_am32am33_edicao07-640b0959e76c0.pdf"
)
DS7_AT_AUG22 = (
    "https://www.media.stellantis.com/at-de/ds/press/Neuer-Premium-SUV-DS-7_Die-Preise_310822"
)
KIA_IT_20240313 = (
    "https://www.kia.com/content/dam/kwcms/kme/it/it/assets/contents/utility/price-list/"
    "2024/03/listino-kia-sportage-pubblico-13-03-2024.pdf"
)
KIA_IT_20230510 = (
    "https://www.kia.com/content/dam/kwcms/kme/it/it/assets/contents/utility/price-list/"
    "2023/5/Listino_Kia_Sportage_Pubblico_10_05_2023.pdf"
)
BYD_0524 = (
    "https://www.byd.com/material/byd-site/eu/pdfs/seal-u-dm-i/"
    "Seal-U-DM-i-0524-BPS-EN-2car-V4-web.pdf"
)
CUPRA_IE_DEC22 = (
    "https://www.cupra.com/content/dam/countries/ie/cupra-website/brochure/formentor/"
    "cars-brochure-KM7-NA-dec-2022.pdf"
)
CUPRA_IE_JAN24 = (
    "https://www.cupra.com/content/dam/countries/ie/cupra-website/product-guide/formentor/"
    "cars-models-info-KM7-product-guide-Jan-2024.pdf"
)
CUPRA_GB_JAN23 = (
    "https://www.cupra.com/content/dam/countries/gb/cupra-website/download-documents/2023/"
    "v1_cars_models_cupra_formentor-pricelist-KM7-01-2023.pdf"
)
WRANGLER_IT_MY24 = "https://www.media.stellantis.com/it-it/download-price-lists/177"
WRANGLER_DE_TD_2022 = (
    "https://www.media.stellantis.com/uploads/de/model-document/"
    "220101_j_wrangler_jl_td_01012022-61dd98f991688.pdf"
)
WRANGLER_DE_PRESS_2023 = (
    "https://www.media.stellantis.com/de-de/jeep/press/"
    "moderner-digitaler-bereits-verfuegbar-der-2024-jeep-wrangler"
)
IONIQ_EU = "https://www.hyundai.com/eu/en/models/ioniq-plug-in-hybrid/Features.html"
IONIQ_AU = (
    "https://www.hyundai.com/content/dam/hyundai/au/en/models/ioniq/docs/"
    "Hyundai_IONIQ_Specifications_Sheet.pdf"
)
TUCSON_SE = (
    "https://dmassets.hyundai.com/is/content/hyundaiautoever/"
    "Prislista_TUCSON_PHEV_MY22-23_241213-2pdf"
)
TUCSON_CZ_MR25 = "https://dmassets.hyundai.com/is/content/hyundaiautoever/Tucson+FLpdf"
FORD_CMAX_2016 = (
    "https://media.ford.com/content/dam/fordmedia/North%20America/US/product/2016/"
    "2016-ford-cmax-energi-tech-specs.pdf"
)
FORD_ESCAPE_2026 = (
    "https://www.fromtheroad.ford.com/content/dam/fordmediasite/us/en/library/2026/"
    "order-guides/2026_Ford_Escape_Order_Guide.pdf"
)
HONDA_ACCORD_2014 = (
    "https://automobiles.honda.com/images/2014/accord-plug-in/downloads/my14_accord-plug-in_FS.pdf"
)
VOLT_BATTERY_2016 = (
    "https://media.gm.com/content/dam/Media/microsites/product/Volt_2016/doc/VOLT_BATTERY.pdf"
)
I3S_IT_2018 = "https://www.press.bmwgroup.com/italy/article/attachment/T0020853IT/520142"


def finalize(row: dict) -> None:
    miss = missing_calc_fields(row)
    row["missingCalcFields"] = miss
    row["catalogDataIncomplete"] = bool(miss)
    score, ev = assess_confidence(row)
    row["confidenceScore"] = score
    row["confidenceEvidence"] = ev
    row["confidencePolicyVersion"] = POLICY_VERSION


def set_field(row: dict, field: str, value, cite: str, date: str) -> None:
    urls = urls_in(cite) or [cite]
    if any(is_generic_url(u) for u in urls):
        raise SystemExit(f"generic URL rejected: {cite}")
    year = int(row["year"])
    homolog = row.get("dataDerivedFromSameHomologationYear")
    hy = int(homolog) if homolog is not None else None
    if not cite_dating_ok(cite, date, year, homolog_year=hy):
        raise SystemExit(f"dating rejected {row['id']}.{field}: {date} cite={cite[:120]}")
    row[field] = value
    fs = dict(row.get("fieldSources") or {})
    fd = dict(row.get("fieldSourceDates") or {})
    fs[field] = cite
    fd[field] = date
    row["fieldSources"] = fs
    row["fieldSourceDates"] = fd


def tech_blob(rows: list[dict]) -> str:
    conf = {
        "confidenceScore",
        "confidenceScoreLegacy",
        "confidencePolicyVersion",
        "confidenceEvidence",
    }
    cleaned = [{k: v for k, v in r.items() if k not in conf} for r in rows]
    return json.dumps(cleaned, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def nil_entry(row: dict, *, reason: str, consulted: list, field_reasons: dict | None = None) -> dict:
    out = {
        "id": row["id"],
        "brand": row.get("brand"),
        "model": row.get("model"),
        "year": row.get("year"),
        "market": row.get("market"),
        "missing": missing_calc_fields(row),
        "reason": reason,
        "consulted": consulted,
    }
    if field_reasons:
        out["fieldReasons"] = field_reasons
    already = {f: row.get(f) for f in CALC_FIELDS if row.get(f) is not None}
    if already:
        out["alreadyPresent"] = already
    return out


def append_source(row: dict, text: str) -> None:
    sn = row.get("sourceName") or ""
    # Drop stale wave2-batch2 fragments that this corr replaces.
    parts = [p.strip() for p in sn.split(";") if p.strip()]
    keep = []
    for p in parts:
        low = p.lower()
        if "wave2-batch2 x3 30e" in low:
            continue
        if "wave2-batch2 x1 30e" in low:
            continue
        if "t0322775" in low and "x1" in low:
            continue
        keep.append(p)
    keep.append(text)
    # de-dupe preserving order
    seen = set()
    out = []
    for p in keep:
        if p not in seen:
            seen.add(p)
            out.append(p)
    row["sourceName"] = "; ".join(out)


def main() -> None:
    seed = json.loads(SEED.read_text(encoding="utf-8"))
    by_id = {r["id"]: r for r in seed}
    ids_before = [r["id"] for r in seed]
    assert len(seed) == 6977

    cdn = json.loads(CDN.read_text(encoding="utf-8"))
    if int(cdn.get("seedVersion") or 0) != 84:
        raise SystemExit(f"expected seed 84 baseline, got {cdn.get('seedVersion')}")

    old_man = json.loads(MANIFEST.read_text(encoding="utf-8"))
    batch1_inv = json.loads(
        (CACHE / "catalog_phev_wave2_batch1_inventory.json").read_text(encoding="utf-8")
    )
    batch1_ids = {x["id"] for x in batch1_inv["batch1_candidates"]}
    # also protect batch1 extras
    batch1_ids |= {"bmw-330e-phev-2024", "jeep-grand-cherokee-4xe-2023"}
    batch1_before = {
        i: json.dumps(by_id[i], sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        for i in batch1_ids
        if i in by_id
    }

    m3_before = {
        r["id"]: json.dumps(r, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        for r in seed
        if r["id"].startswith("tesla-model-3") and r.get("year") == 2026
    }
    assert len(m3_before) == 4
    non_phev_sha_before = hashlib.sha256(
        tech_blob([r for r in seed if r.get("powertrain") != "phev"]).encode()
    ).hexdigest()
    if non_phev_sha_before != NON_PHEV_SHA:
        raise SystemExit(f"non-PHEV SHA unexpected: {non_phev_sha_before}")

    inv = json.loads(INVENTORY.read_text(encoding="utf-8"))
    batch2_ids = [x["id"] for x in inv["batch2_candidates"]]
    assert len(batch2_ids) == 40
    lotto = set(batch2_ids)
    outside_before = {
        r["id"]: json.dumps(r, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        for r in seed
        if r["id"] not in lotto
    }

    # Freeze Q5 SB 2024 + Active Tourer 2023 blobs (must remain byte-identical for calc fields)
    q5_freeze = {
        f: by_id["audi-q5-sportback-phev-50-tfsi-e-2024"].get(f)
        for f in (*CALC_FIELDS, "fieldSources", "fieldSourceDates")
    }
    at_freeze = {
        f: by_id["bmw-serie-2-active-tourer-225e-xdrive-2023"].get(f)
        for f in (*CALC_FIELDS, "fieldSources", "fieldSourceDates")
    }

    changed_fields: list[dict] = []
    partial: list[dict] = []
    completed: list[dict] = []
    homolog_reuse: list[dict] = []
    left_nil: list[dict] = []

    def record_fill(rid: str, field: str, value, url: str, source_date: str, **extra) -> None:
        changed_fields.append(
            {
                "id": rid,
                "field": field,
                "value": value,
                "url": url,
                "sourceDate": source_date,
                **extra,
            }
        )

    # --- X3 30e 2024: add CS + re-date to press 19.06.2024 ---------------------------------
    x3 = by_id["bmw-x3-phev-xdrive30e-2024"]
    cite_x3 = (
        "BMW Group PressClub Greece «Η νέα BMW X3.» Δελτίο τύπου 19.06.2024 (T0443191EL) "
        f"+ attachment Technical specifications BMW X3 / X3 30e xDrive Media information 06/2024 — "
        f"Energy capacity (net) 19.7 kWh; Electric range (WLTP) 81–90 → MIN 81; "
        f"Fuel consump. with battery empty (WLTP) 7.9–7.2 → MAX 0.079; "
        f"electric weighted only → pure CD nil. Press: {X3_PRESS} Attachment: {X3_ATTACH}"
    )
    set_field(x3, "batteryKWh", 19.7, cite_x3, "2024-06-19")
    set_field(x3, "wltpRangeKm", 81, cite_x3, "2024-06-19")
    set_field(x3, "fuelConsumptionLPerKm", 0.079, cite_x3, "2024-06-19")
    append_source(
        x3,
        "wave2-batch2-corr1 X3 30e press 19.06.2024 + tech PDF 06/2024 "
        f"net 19.7 / EAER 81 / CS 0.079 — {X3_PRESS} — {X3_ATTACH}",
    )
    x3["sourceUpdatedAt"] = SOURCE_DAY
    finalize(x3)
    for f, v in [
        ("batteryKWh", 19.7),
        ("wltpRangeKm", 81),
        ("fuelConsumptionLPerKm", 0.079),
    ]:
        record_fill(x3["id"], f, v, X3_ATTACH, "2024-06-19", variant="X3 30e xDrive", press=X3_PRESS)
    partial.append(
        {
            "id": x3["id"],
            "filled": {
                "batteryKWh": 19.7,
                "wltpRangeKm": 81,
                "fuelConsumptionLPerKm": 0.079,
            },
            "left_nil": ["energyConsumptionKWhPerKm"],
            "note": "corr1: CS from battery-empty row; pure CD still weighted-only",
        }
    )

    # --- X1 30e 2023: re-cite U11 mportal -------------------------------------------------
    x1 = by_id["bmw-x1-phev-xdrive30e-2023"]
    cite_x1 = (
        "BMW Preisliste X1 / U11 November 2023, Ausgabe 1, 27.09.2023 (cdn.mportal.de U11-11-2023.PDF) — "
        "xDrive30e column: Netto Batterieinhalt 14,2; Elektrische Reichweite kombiniert 71–85 → MIN 71; "
        f"Verbrauch/Stromverbrauch next to gewichtet → CS/CD nil {BMW_X1_U11}"
    )
    set_field(x1, "batteryKWh", 14.2, cite_x1, "2023-09-27")
    set_field(x1, "wltpRangeKm", 71, cite_x1, "2023-09-27")
    append_source(
        x1,
        f"wave2-batch2-corr1 X1 30e U11-11-2023.PDF netta 14.2 / EAER 71 — {BMW_X1_U11}",
    )
    x1["sourceUpdatedAt"] = SOURCE_DAY
    finalize(x1)
    record_fill(x1["id"], "batteryKWh", 14.2, BMW_X1_U11, "2023-09-27", variant="xDrive30e")
    record_fill(x1["id"], "wltpRangeKm", 71, BMW_X1_U11, "2023-09-27", variant="xDrive30e")
    partial.append(
        {
            "id": x1["id"],
            "filled": {"batteryKWh": 14.2, "wltpRangeKm": 71},
            "left_nil": ["fuelConsumptionLPerKm", "energyConsumptionKWhPerKm"],
            "note": "corr1: re-cited to dated mportal U11; press attachment live URL abandoned",
        }
    )

    # --- Keep prior Q5 SB 2024 + AT 225e 2023 fills (unchanged values) --------------------
    q5 = by_id["audi-q5-sportback-phev-50-tfsi-e-2024"]
    for f, want in q5_freeze.items():
        if q5.get(f) != want:
            raise SystemExit(f"Q5 SB 2024 mutated: {f}")
    finalize(q5)
    partial.append(
        {
            "id": q5["id"],
            "filled": {
                "fuelConsumptionLPerKm": 0.088,
                "wltpRangeKm": 57,
                "batteryKWh": 14.4,
            },
            "left_nil": ["energyConsumptionKWhPerKm"],
            "note": "unchanged from seed 84",
        }
    )
    for f, v in [("fuelConsumptionLPerKm", 0.088), ("wltpRangeKm", 57), ("batteryKWh", 14.4)]:
        record_fill(q5["id"], f, v, AUDI_Q5SB, "2024-06-04", variant="50 TFSI e 220 kW", unchanged=True)

    at = by_id["bmw-serie-2-active-tourer-225e-xdrive-2023"]
    for f, want in at_freeze.items():
        if at.get(f) != want:
            raise SystemExit(f"Active Tourer 2023 mutated: {f}")
    finalize(at)
    partial.append(
        {
            "id": at["id"],
            "filled": {"batteryKWh": 14.2, "wltpRangeKm": 78},
            "left_nil": ["fuelConsumptionLPerKm", "energyConsumptionKWhPerKm"],
            "note": "unchanged from seed 84",
        }
    )
    for f, v in [("batteryKWh", 14.2), ("wltpRangeKm", 78)]:
        record_fill(at["id"], f, v, BMW_AT_U06, "2023-09-27", variant="225e xDrive", unchanged=True)

    # --- New fills ------------------------------------------------------------------------
    c5 = by_id["citroen-c5-aircross-phev-2022"]
    cite_c5 = (
        "Stellantis Media DE Citroën press 19 Dez 2022 — C5 Aircross Hybrid 225: "
        f"14,2 kWh (12,9 kWh netto) → store net 12.9; range «bis zu 64» MAX → EAER nil; "
        f"fuel/energy footnotes gewichtet → CS/CD nil {C5_DE_PRESS}"
    )
    set_field(c5, "batteryKWh", 12.9, cite_c5, "2022-12-19")
    append_source(c5, f"wave2-batch2-corr1 C5 Aircross 2022 DE press net 12.9 — {C5_DE_PRESS}")
    c5["sourceUpdatedAt"] = SOURCE_DAY
    finalize(c5)
    record_fill(c5["id"], "batteryKWh", 12.9, C5_DE_PRESS, "2022-12-19", variant="Hybrid 225")
    partial.append(
        {
            "id": c5["id"],
            "filled": {"batteryKWh": 12.9},
            "left_nil": [
                "fuelConsumptionLPerKm",
                "energyConsumptionKWhPerKm",
                "wltpRangeKm",
            ],
            "note": "net labeled; EAER only as MAX «bis zu»; weighted fuel/energy",
        }
    )

    ds7 = by_id["ds-7-phev-e-tense-2024"]
    cite_ds7 = (
        "DS Automobiles DE Preisliste DS 7 MY42 Stand März 2024 / 25. März 2024 — E-TENSE 225: "
        "Kapazität Hochvolt Batterie Netto (Richtwert) 13; Kraftstoffverbrauch bei entladener Batterie "
        f"7,0–7,1 → MAX 0.071; EAER combined absent (AER max / City EAER only); Stromverbrauch gewichtet "
        f"→ CD nil {DS7_DE_MAR24}"
    )
    set_field(ds7, "batteryKWh", 13.0, cite_ds7, "2024-03-25")
    set_field(ds7, "fuelConsumptionLPerKm", 0.071, cite_ds7, "2024-03-25")
    append_source(
        ds7,
        f"wave2-batch2-corr1 DS7 E-TENSE 225 DE listino 2024-03-25 net 13 / CS 0.071 — {DS7_DE_MAR24}",
    )
    ds7["sourceUpdatedAt"] = SOURCE_DAY
    finalize(ds7)
    record_fill(ds7["id"], "batteryKWh", 13.0, DS7_DE_MAR24, "2024-03-25", variant="E-TENSE 225")
    record_fill(
        ds7["id"], "fuelConsumptionLPerKm", 0.071, DS7_DE_MAR24, "2024-03-25", variant="E-TENSE 225"
    )
    partial.append(
        {
            "id": ds7["id"],
            "filled": {"batteryKWh": 13.0, "fuelConsumptionLPerKm": 0.071},
            "left_nil": ["energyConsumptionKWhPerKm", "wltpRangeKm"],
            "note": "no combined EAER MIN on sheet (AER max / City EAER only)",
        }
    )

    for rid, url, date in [
        ("kia-sportage-phev-2024", KIA_IT_20240313, "2024-03-13"),
        ("kia-sportage-phev-2023", KIA_IT_20230510, "2023-05-10"),
    ]:
        row = by_id[rid]
        cite = (
            f"Kia Italia listino Sportage pubblico {date} — PHEV: CONSUMI WLTC A CARICA MINIMA 6,866 L/100 "
            f"→ CS 0.06866; Autonomia in EV ciclo medio combinato WLTC 70 km; Energia (kWh) 13,8 unlabeled "
            f"(not utilizzabile/net) → battery nil; Consumo in EV 169 Wh/km not pure-CD labeled → CD nil {url}"
        )
        set_field(row, "fuelConsumptionLPerKm", 0.06866, cite, date)
        set_field(row, "wltpRangeKm", 70, cite, date)
        append_source(
            row,
            f"wave2-batch2-corr1 Sportage PHEV IT listino {date} CS 0.06866 / EAER 70 — {url}",
        )
        row["sourceUpdatedAt"] = SOURCE_DAY
        finalize(row)
        record_fill(rid, "fuelConsumptionLPerKm", 0.06866, url, date, variant="1.6 TGDi AWD AT6 PHEV")
        record_fill(rid, "wltpRangeKm", 70, url, date, variant="1.6 TGDi AWD AT6 PHEV")
        partial.append(
            {
                "id": rid,
                "filled": {"fuelConsumptionLPerKm": 0.06866, "wltpRangeKm": 70},
                "left_nil": ["energyConsumptionKWhPerKm", "batteryKWh"],
                "note": "Energia 13,8 unlabeled; EV Wh/km not pure-CD",
            }
        )

    byd = by_id["byd-seal-u-phev-dm-i-2024"]
    cite_byd = (
        "BYD Europe Seal U DM-i specification sheet 0524-BPS-EN-V4 (filename Seal-U-DM-i-0524…) — "
        "Boost+Design columns: Fuel Consumption - combined MAX 7.4 L/100 (Design) → 0.074; "
        "Electric range - combined MIN 70 km (Design); Battery capacity 18.3 kWh unlabeled (not net/usable) "
        f"→ battery nil; Electric consumption - combined not pure-CD labeled → CD nil {BYD_0524}"
    )
    set_field(byd, "fuelConsumptionLPerKm", 0.074, cite_byd, "2024-05-01")
    set_field(byd, "wltpRangeKm", 70, cite_byd, "2024-05-01")
    append_source(
        byd,
        f"wave2-batch2-corr1 Seal U DM-i 0524 BPS CS 0.074 / EAER 70 — {BYD_0524}",
    )
    byd["sourceUpdatedAt"] = SOURCE_DAY
    finalize(byd)
    record_fill(byd["id"], "fuelConsumptionLPerKm", 0.074, BYD_0524, "2024-05-01", variant="Design/Boost max/min")
    record_fill(byd["id"], "wltpRangeKm", 70, BYD_0524, "2024-05-01", variant="Design MIN")
    partial.append(
        {
            "id": byd["id"],
            "filled": {"fuelConsumptionLPerKm": 0.074, "wltpRangeKm": 70},
            "left_nil": ["energyConsumptionKWhPerKm", "batteryKWh"],
            "note": "battery capacity unlabeled 18.3; pure CD unlabeled",
        }
    )

    filled_ids = {e["id"] for e in partial}

    NIL_REASONS: dict[str, dict] = {
        "audi-q5-sportback-phev-50-tfsi-e-2023": {
            "reason": (
                "No MY2023-dated Audi eTD for Q5 Sportback 50 TFSI e. "
                "2024-06-04 Sportback eTD rejected (future year vs MY2023). "
                "No Q5-SB family in homolog map for best_shared_exact reuse."
            ),
            "consulted": [
                {
                    "url": AUDI_Q5SB,
                    "sourceDate": "2024-06-04",
                    "reject_for": "document year 2024 ≠ MY2023; no homolog fingerprint path",
                }
            ],
        },
        "bmw-serie-2-active-tourer-225e-xdrive-2024": {
            "reason": (
                "U06 Nov 2023 Preisliste (27.09.2023) is calendar-2023 — invalid for MY2024. "
                "No MY2024-dated OEM Preisliste with Netto/EAER/CS discharged verified."
            ),
            "consulted": [
                {
                    "url": BMW_AT_U06,
                    "sourceDate": "2023-09-27",
                    "reject_for": "2023 document cannot date MY2024",
                }
            ],
        },
        "bmw-serie-2-active-tourer-225e-xdrive-2022": {
            "reason": (
                "IT listino 26.01.2022 (press T0321051IT) — no Netto/EAER for 225e extracted. "
                "Nov 2023 Preisliste is future-year vs MY2022."
            ),
            "consulted": [
                {
                    "url": "https://www.press.bmwgroup.com/italy/article/attachment/T0321051IT/520142",
                    "sourceDate": "2022-01-26",
                    "reject_for": "no labeled net battery / EAER for 225e on retrieved sheet",
                },
                {
                    "url": BMW_AT_U06,
                    "sourceDate": "2023-09-27",
                    "reject_for": "2023 document ≠ MY2022",
                },
            ],
        },
        "bmw-serie-3-320e-2024": {
            "reason": (
                "330e press sheet (T0442333, usable 19.5, 2024-05-29) is a different trim "
                "(330e ≠ 320e). No 320e-labeled net/EAER/CS discharged OEM sheet verified."
            ),
            "consulted": [
                {
                    "url": "https://www.press.bmwgroup.com/deutschland/article/attachment/T0442333DE/632499",
                    "sourceDate": "2024-05-29",
                    "reject_for": "330e variant — not 320e column",
                }
            ],
        },
        "bmw-serie-3-320e-2023": {
            "reason": "No MY2023-dated OEM sheet with labeled net battery / EAER / CS discharged for 320e.",
            "consulted": [
                {
                    "url": "https://www.press.bmwgroup.com/deutschland/article/attachment/T0442333DE/632499",
                    "sourceDate": "2024-05-29",
                    "reject_for": "2024 330e sheet — wrong year and wrong trim",
                }
            ],
        },
        "bmw-x1-phev-xdrive30e-2024": {
            "reason": (
                "U11 Nov 2023 X1 Preisliste is calendar-2023 — cannot date MY2024. "
                "weightedFuel mismatch 2023≠2024 blocks exact_homolog / best_shared_exact."
            ),
            "consulted": [
                {
                    "url": BMW_X1_U11,
                    "sourceDate": "2023-09-27",
                    "reject_for": "2023 listino ≠ MY2024; weighted fuel mismatch blocks homolog",
                }
            ],
        },
        "bmw-x2-phev-xdrive25e-2023": {
            "reason": "No MY2023 OEM listino with Netto/EAER for X2 xDrive25e (X1 U11 is different model).",
            "consulted": [
                {
                    "url": BMW_X1_U11,
                    "sourceDate": "2023-09-27",
                    "reject_for": "X1 Preisliste — wrong model vs X2",
                }
            ],
        },
        "bmw-x2-phev-xdrive25e-2022": {
            "reason": "No MY2022 OEM sheet with labeled net/EAER for X2 xDrive25e verified.",
            "consulted": [
                {
                    "url": "https://www.press.bmwgroup.com/italy/article/attachment/T0321361IT/520251",
                    "sourceDate": "2022-01-26",
                    "reject_for": "X1 F48 listino — wrong model vs X2",
                }
            ],
        },
        "bmw-x3-phev-xdrive30e-2023": {
            "reason": "X3 30e Media 06/2024 / press 19.06.2024 is future-year vs MY2023.",
            "consulted": [
                {
                    "url": X3_ATTACH,
                    "sourceDate": "2024-06-19",
                    "reject_for": "2024 media sheet ≠ MY2023",
                }
            ],
        },
        "bmw-x3-phev-xdrive30e-2022": {
            "reason": "No MY2022 OEM tech sheet with net/EAER for X3 xDrive30e verified.",
            "consulted": [
                {
                    "url": X3_ATTACH,
                    "sourceDate": "2024-06-19",
                    "reject_for": "2024 media sheet ≠ MY2022",
                }
            ],
        },
        "bmw-x5-phev-xdrive50e-2024": {
            "reason": (
                "Feb 2023 press nutzbar 25.7 / EAER 94–110 fails MY2024 dating. "
                "Herbst 2024 CS-only paragraph lacks net battery / EAER combined on same dated block."
            ),
            "consulted": [
                {
                    "url": "https://www.press.bmwgroup.com/austria/article/detail/T0411958DE/der-neue-bmw-x5-und-der-neue-bmw-x6",
                    "sourceDate": "2023-02-08",
                    "reject_for": "article date 2023 ≠ MY2024 for battery/range",
                },
                {
                    "url": "https://www.press.bmwgroup.com/deutschland/article/detail/T0445280DE",
                    "sourceDate": "2024-09-01",
                    "reject_for": "CS text without co-located net/EAER; not used for single-field invent",
                },
            ],
        },
        "bmw-i3s-with-range-extender-phev-2021": {
            "reason": (
                "Range alreadyPresent. IT listino T0020853IT (24/01/2018) has netta 27,2 for i3s REx "
                "but calendar-2018 ≠ MY2021. No 2021-dated OEM net/usable REx sheet verified."
            ),
            "consulted": [
                {
                    "url": I3S_IT_2018,
                    "sourceDate": "2018-01-24",
                    "reject_for": "2018 listino ≠ MY2021 dating",
                }
            ],
        },
        "cupra-formentor-phev-vz-e-hybrid-2023": {
            "reason": (
                "Dec-2022 IE brochure has VZ figures but 12/2022 ≠ MY2023. "
                "Jan-2024 Product Guide is MY24-dated. GB Jan-2023 pricelist has prices/CO₂ only."
            ),
            "consulted": [
                {
                    "url": CUPRA_IE_DEC22,
                    "sourceDate": "2022-12-01",
                    "reject_for": "2022 brochure ≠ MY2023",
                },
                {
                    "url": CUPRA_IE_JAN24,
                    "sourceDate": "2024-01-01",
                    "reject_for": "2024 product guide ≠ MY2023",
                },
                {
                    "url": CUPRA_GB_JAN23,
                    "sourceDate": "2023-01-01",
                    "reject_for": "pricelist lacks CS discharged / EAER / net battery columns",
                },
            ],
        },
        "cupra-formentor-phev-e-hybrid-2022": {
            "reason": (
                "IE Dec-2022 brochure PDF is image-only (no extractable text labels for net/CS/EAER); "
                "cannot verify battery convention or column variants without OCR of labeled cells."
            ),
            "consulted": [
                {
                    "url": CUPRA_IE_DEC22,
                    "sourceDate": "2022-12-01",
                    "reject_for": "image-only PDF — values not verifiable as labeled text",
                }
            ],
        },
        "citroen-c5-aircross-phev-2023": {
            "reason": (
                "DE press 19 Dez 2022 (12.9 net) is calendar-2022 ≠ MY2023. "
                "DE press 23 Jan 2023 Hybrid 180 cites 12,4 kWh unlabeled (not netto). "
                "UK Jan 2023 price/spec: 13.2 kWh unlabeled + weighted combined only."
            ),
            "consulted": [
                {
                    "url": C5_DE_PRESS,
                    "sourceDate": "2022-12-19",
                    "reject_for": "2022 press ≠ MY2023 dating",
                },
                {
                    "url": C5_DE_JAN23,
                    "sourceDate": "2023-01-23",
                    "reject_for": "12,4 kWh without net/usable label; range «bis zu» MAX",
                },
                {
                    "url": C5_UK_JAN23,
                    "sourceDate": "2023-01-01",
                    "reject_for": "13.2 kWh unlabeled; Hybrid weighted combined only",
                },
            ],
        },
        "ds-7-phev-e-tense-2023": {
            "reason": (
                "PT product info Mar 2023 quotes EAER 67 but battery 14,2 unlabeled (gross). "
                "AT press 31.08.2022 netto 12,9 is calendar-2022 ≠ MY2023. "
                "DE MY42 Mar 2024 listino is future-year vs MY2023."
            ),
            "consulted": [
                {
                    "url": DS7_PT_MAR23,
                    "sourceDate": "2023-03-01",
                    "reject_for": "EAER present but battery unlabeled; CS only ponderados",
                },
                {
                    "url": DS7_AT_AUG22,
                    "sourceDate": "2022-08-31",
                    "reject_for": "2022 press ≠ MY2023",
                },
                {
                    "url": DS7_DE_MAR24,
                    "sourceDate": "2024-03-25",
                    "reject_for": "2024 listino ≠ MY2023",
                },
            ],
        },
        "ds-7-phev-e-tense-2022": {
            "reason": (
                "Seed model is DS 7 CROSSBACK; DE MY42 / PT AM32 sheets describe post-Crossback DS 7. "
                "No Crossback MY2022 OEM net/CS/EAER sheet verified."
            ),
            "consulted": [
                {
                    "url": DS7_DE_MAR24,
                    "sourceDate": "2024-03-25",
                    "reject_for": "wrong generation (new DS 7) and wrong year",
                },
                {
                    "url": DS7_PT_MAR23,
                    "sourceDate": "2023-03-01",
                    "reject_for": "wrong generation vs CROSSBACK seed; wrong year",
                },
            ],
        },
        "jeep-compass-phev-4xe-2023": {
            "reason": (
                "Battery+EAER alreadyPresent. Pure CD nil: FR tarif 19 déc 2023 shows autonomy/CO₂ "
                "pondérés — no rein-elektrisch / pure-CD kWh label for MY2023."
            ),
            "consulted": [
                {
                    "url": (
                        "https://www.media.stellantis.com/uploads/fr/attachment/7783/"
                        "tarifpublicjeeprcompassmy242023e19decembre2023-65820ebe62db4.pdf"
                    ),
                    "sourceDate": "2023-12-19",
                    "reject_for": "pondéré only — not pure CD kWh",
                }
            ],
            "field_reasons": {
                "energyConsumptionKWhPerKm": "no pure-CD label on consulted Stellantis tarif",
            },
        },
        "jeep-compass-phev-4xe-2024": {
            "reason": (
                "Battery+EAER alreadyPresent. FR tarif 19 déc 2023 is end-of-2023 (invalid to "
                "re-date MY2024 fields). Pure CD still unlabeled."
            ),
            "consulted": [
                {
                    "url": (
                        "https://www.media.stellantis.com/uploads/fr/attachment/7783/"
                        "tarifpublicjeeprcompassmy242023e19decembre2023-65820ebe62db4.pdf"
                    ),
                    "sourceDate": "2023-12-19",
                    "reject_for": "end-of-2023 document cannot date MY2024; no pure CD",
                }
            ],
            "field_reasons": {
                "energyConsumptionKWhPerKm": "no pure-CD label; Dec-2023 tarif invalid for MY2024 dating",
            },
        },
        "jeep-grand-cherokee-4xe-2024": {
            "reason": (
                "Battery+EAER alreadyPresent. UK price list from 12/04/2024 and DE MJ23 listino show "
                "weighted electric only; UK also labels Battery gross capacity 17.3."
            ),
            "consulted": [
                {
                    "url": (
                        "https://www.media.stellantis.com/uploads/uk/model-pricelist/"
                        "grandcherokee_price_list1-6a27e5127aae0.pdf"
                    ),
                    "sourceDate": "2024-04-12",
                    "reject_for": "Electric consumption weighted combined only; battery labeled gross",
                },
                {
                    "url": (
                        "https://www.media.stellantis.com/uploads/de/model-pricelist/"
                        "preisliste_grand_cherokee_4xe_januar_20234-6486c171a11d8.pdf"
                    ),
                    "sourceDate": "2023-01-01",
                    "reject_for": "2023 listino ≠ MY2024 for new fills; Stromverbrauch gewichtet",
                },
            ],
            "field_reasons": {
                "energyConsumptionKWhPerKm": "weighted-only OEM sheets",
            },
        },
        "jeep-wrangler-4xe-2024": {
            "reason": (
                "IT MY24 listino (27/02/2024) cites Capacità della batteria 17.3 kWh without "
                "net/usable/utilizzabile label. DE press 14 Nov 2023 range figures not EAER combined MIN."
            ),
            "consulted": [
                {
                    "url": WRANGLER_IT_MY24,
                    "sourceDate": "2024-02-27",
                    "reject_for": "17.3 kWh unlabeled (not net/usable)",
                },
                {
                    "url": WRANGLER_DE_PRESS_2023,
                    "sourceDate": "2023-11-14",
                    "reject_for": "2023 press ≠ MY2024; range not EAER combined MIN",
                },
            ],
        },
        "jeep-wrangler-4xe-2023": {
            "reason": (
                "No MY2023-dated OEM Wrangler 4xe listino/tech sheet with net/EAER/CS verified. "
                "DE TD Stand 01.01.2022 is wrong year; IT MY24 listino is wrong year."
            ),
            "consulted": [
                {
                    "url": WRANGLER_DE_TD_2022,
                    "sourceDate": "2022-01-01",
                    "reject_for": "2022 TD ≠ MY2023",
                },
                {
                    "url": WRANGLER_IT_MY24,
                    "sourceDate": "2024-02-27",
                    "reject_for": "2024 listino ≠ MY2023",
                },
            ],
        },
        "jeep-wrangler-4xe-2022": {
            "reason": (
                "Battery alreadyPresent. DE TD 01.01.2022 shows EAER City only (45–53) — no combined "
                "EAER; Stromverbrauch EC, AC gewichtet only — no pure CD."
            ),
            "consulted": [
                {
                    "url": WRANGLER_DE_TD_2022,
                    "sourceDate": "2022-01-01",
                    "reject_for": "EAER City only; Stromverbrauch gewichtet — not pure CD / combined EAER",
                }
            ],
            "field_reasons": {
                "wltpRangeKm": "only EAER City on DE TD — catalog requires combined EAER",
                "energyConsumptionKWhPerKm": "weighted only",
            },
        },
        "hyundai-tucson-phev-2024": {
            "reason": (
                "IT/DE live Tucson pages are continuous MY26/27 facelift. "
                "CZ MR25 sheet has usable 13.8 but MR25 ≠ MY2024."
            ),
            "consulted": [
                {
                    "url": TUCSON_CZ_MR25,
                    "sourceDate": "2025-01-01",
                    "reject_for": "MR25 / 2025 sheet ≠ MY2024",
                },
                {
                    "url": TUCSON_SE,
                    "sourceDate": "2022-01-01",
                    "reject_for": "MY22-23 SE prislista ≠ MY2024; battery unlabeled / fuel weighted",
                },
            ],
        },
        "hyundai-tucson-phev-2023": {
            "reason": (
                "SE MY22-23 prislista: battery 13.8 unlabeled; fuel 1.4 is weighted (CO₂ 31); "
                "range not paired with CS discharged. CZ MR25 usable wrong MY."
            ),
            "consulted": [
                {
                    "url": TUCSON_SE,
                    "sourceDate": "2022-01-01",
                    "reject_for": "unlabeled battery; weighted fuel only",
                },
                {
                    "url": TUCSON_CZ_MR25,
                    "sourceDate": "2025-01-01",
                    "reject_for": "MR25 ≠ MY2023",
                },
            ],
        },
        "hyundai-tucson-phev-2022": {
            "reason": (
                "Same SE MY22-23 sheet: unlabeled 13.8 battery; weighted fuel only; "
                "no dated usable/CS discharged for MY2022."
            ),
            "consulted": [
                {
                    "url": TUCSON_SE,
                    "sourceDate": "2022-01-01",
                    "reject_for": "battery unlabeled; fuel weighted; no CS discharged label",
                }
            ],
        },
        "hyundai-ioniq-phev-2022": {
            "reason": (
                "Range alreadyPresent. EU Features and AU specs cite 8.9 kWh Capacity without "
                "usable/net/utilizzabile label."
            ),
            "consulted": [
                {
                    "url": IONIQ_EU,
                    "sourceDate": "2022-01-01",
                    "reject_for": "8.9 kWh not labeled usable/net",
                },
                {
                    "url": IONIQ_AU,
                    "sourceDate": "2022-01-01",
                    "reject_for": "Capacity 8.9 unlabeled; AU market sheet",
                },
            ],
        },
        "ford-c-max-energi-plug-in-hybrid-phev-2016": {
            "reason": (
                "2016 Ford Media C-MAX Energi tech specs cite 7.6-kWh Li-ion without usable/net label. "
                "US OEM only for IT seed preference → no fill."
            ),
            "consulted": [
                {
                    "url": FORD_CMAX_2016,
                    "sourceDate": "2016-01-01",
                    "reject_for": "7.6 kWh not labeled usable/net",
                }
            ],
        },
        "ford-escape-fwd-phev-phev-2026": {
            "reason": (
                "2026 Escape order guide has no battery kWh. 2025 Escape tech specs: range/MPGe only, "
                "no usable kWh."
            ),
            "consulted": [
                {
                    "url": FORD_ESCAPE_2026,
                    "sourceDate": "2026-01-01",
                    "reject_for": "order guide lacks usable battery kWh",
                },
                {
                    "url": (
                        "https://www.fromtheroad.ford.com/content/dam/fordmediasite/us/en/library/2025/"
                        "specs/2025_Ford_Escape_Technical_Specifications.pdf"
                    ),
                    "sourceDate": "2025-01-01",
                    "reject_for": "2025 sheet ≠ MY2026; no usable kWh",
                },
            ],
        },
        "honda-accord-phev-2014": {
            "reason": "MY14 Accord Plug-in fact sheet: no kWh capacity (only 55-hp lithium-ion mention).",
            "consulted": [
                {
                    "url": HONDA_ACCORD_2014,
                    "sourceDate": "2014-01-01",
                    "reject_for": "no battery kWh figure on OEM fact sheet",
                }
            ],
        },
        "chevrolet-volt-phev-2019": {
            "reason": (
                "2016 Volt Battery System PDF Usable Energy 14.0 kWh — document year 2016 ≠ MY2019. "
                "2019 Volt OM has no usable kWh found."
            ),
            "consulted": [
                {
                    "url": VOLT_BATTERY_2016,
                    "sourceDate": "2016-01-01",
                    "reject_for": "2016 usable 14.0 ≠ MY2019 dating",
                },
                {
                    "url": (
                        "https://www.chevrolet.com/ownercenter/content/dam/gmownercenter/gmna/dynamic/"
                        "manuals/2019/Chevrolet/volt/19_CHEV_Volt_OM_en_US_U_84044803A_2018JUN22.pdf"
                    ),
                    "sourceDate": "2018-06-22",
                    "reject_for": "owner manual — no usable kWh figure found",
                },
            ],
        },
    }

    for rid in batch2_ids:
        if rid in filled_ids:
            continue
        meta = NIL_REASONS.get(rid)
        if not meta:
            raise SystemExit(f"missing nil reason for {rid}")
        row = by_id[rid]
        finalize(row)
        # Guard: consulted must not be only generic hubs
        urls = [c.get("url") for c in meta["consulted"] if c.get("url")]
        if not urls:
            raise SystemExit(f"nil {rid} missing consulted URLs")
        if all(is_generic_url(u) for u in urls):
            raise SystemExit(f"nil {rid} consulted only generic URLs: {urls}")
        left_nil.append(
            nil_entry(
                row,
                reason=meta["reason"],
                consulted=meta["consulted"],
                field_reasons=meta.get("field_reasons"),
            )
        )

    # invariants
    if [r["id"] for r in seed] != ids_before:
        raise SystemExit("id order changed")
    for mid, blob in m3_before.items():
        now = json.dumps(by_id[mid], sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        if now != blob:
            raise SystemExit(f"Model 3 mutated: {mid}")
    for bid, blob in batch1_before.items():
        now = json.dumps(by_id[bid], sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        if now != blob:
            raise SystemExit(f"batch1 row mutated: {bid}")
    non_phev_sha = hashlib.sha256(
        tech_blob([r for r in seed if r.get("powertrain") != "phev"]).encode()
    ).hexdigest()
    if non_phev_sha != non_phev_sha_before:
        raise SystemExit("non-PHEV SHA drift")
    for oid, blob in outside_before.items():
        now = json.dumps(by_id[oid], sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        if now != blob:
            raise SystemExit(f"non-lotto mutated: {oid}")

    covered = (
        {e["id"] for e in completed}
        | {e["id"] for e in partial}
        | {e["id"] for e in homolog_reuse}
        | {e["id"] for e in left_nil}
    )
    missing = [i for i in batch2_ids if i not in covered]
    if missing:
        raise SystemExit(f"batch2 uncovered: {missing}")

    battery_convention = {
        "catalogConvention": "net/usable",
        "thisPass": [
            {
                "id": "audi-q5-sportback-phev-50-tfsi-e-2024",
                "batteryKWh": 14.4,
                "note": "unchanged eTD net 14.4",
            },
            {
                "id": "bmw-x1-phev-xdrive30e-2023",
                "batteryKWh": 14.2,
                "note": "Netto Batterieinhalt 14,2 on U11 Nov 2023 Preisliste",
            },
            {
                "id": "bmw-serie-2-active-tourer-225e-xdrive-2023",
                "batteryKWh": 14.2,
                "note": "unchanged Netto 14,2 on U06",
            },
            {
                "id": "bmw-x3-phev-xdrive30e-2024",
                "batteryKWh": 19.7,
                "note": "Energy capacity (net) 19.7 — press 19.06.2024 + tech PDF",
            },
            {
                "id": "citroen-c5-aircross-phev-2022",
                "batteryKWh": 12.9,
                "note": "14,2 kWh (12,9 kWh netto) DE press 19 Dez 2022",
            },
            {
                "id": "ds-7-phev-e-tense-2024",
                "batteryKWh": 13.0,
                "note": "Kapazität Hochvolt Batterie Netto (Richtwert) 13",
            },
        ],
    }

    new_ver = 85
    cdn["seedVersion"] = new_ver
    cdn["prevSeedVersion"] = 84
    cdn["rows"] = len(seed)
    payload = json.dumps(seed, separators=(",", ":"), ensure_ascii=False)
    cdn["bytes"] = len(payload.encode())
    cdn["updatedAt"] = datetime.now(timezone.utc).isoformat()
    cdn["note"] = (
        "seedVersion 85: PHEV wave2 batch2 corr1 — X3 CS 0.079 + press 19.06.2024 dating; "
        "X1 U11 re-cite; C5/DS7/Kia/BYD fills; hub-only nils replaced with exact docs; "
        "api/static sync deferred at seed 77"
    )
    SEED.write_text(payload)
    CDN.write_text(json.dumps(cdn, indent=2) + "\n")
    if SEED.stat().st_size != cdn["bytes"]:
        raise SystemExit(f"CDN bytes mismatch {cdn['bytes']} vs {SEED.stat().st_size}")

    man = {
        "seedVersion": new_ver,
        "prevSeedVersion": 84,
        "ids_before": ids_before,
        "batch2_ids": batch2_ids,
        "completed": completed,
        "partial": partial,
        "extras": [],
        "homolog_reuse": homolog_reuse,
        "left_nil": left_nil,
        "changed_fields": changed_fields,
        "counts": {
            "completed": len(completed),
            "partial": len(partial),
            "left_nil": len(left_nil),
            "homolog_reuse": len(homolog_reuse),
        },
        "non_phev_tech_sha": non_phev_sha,
        "m3_ids": sorted(m3_before),
        "sourceDay": SOURCE_DAY,
        "selection": inv.get("selection"),
        "reviewNotes": [
            "corr1: X3 CS + 19.06.2024 press dating; X1 → U11-11-2023.PDF",
            "corr1: fills C5 2022 net, DS7 2024 net+CS, Kia Sportage 23/24 CS+EAER, BYD Seal U CS+EAER",
            "corr1: left_nil consulted URLs are exact documents (no homepage-only)",
        ],
        "prKind": "research-corr1",
        "battery_convention": battery_convention,
        "prevManifestSeed": old_man.get("seedVersion"),
    }
    MANIFEST.write_text(json.dumps(man, indent=2, ensure_ascii=False) + "\n")
    print(
        json.dumps(
            {
                "seedVersion": new_ver,
                "bytes": cdn["bytes"],
                "counts": man["counts"],
                "changed_fields_n": len(changed_fields),
                "non_phev_tech_sha": non_phev_sha,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
