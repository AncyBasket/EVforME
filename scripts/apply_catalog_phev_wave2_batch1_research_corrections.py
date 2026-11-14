#!/usr/bin/env python3
"""
PHEV wave2 batch1 RESEARCH corrections (seed 79→80).

CHANGES NEEDED on PR #41:
- Audi batteryKWh → net/usable (10.4 / 14.4); label net in cites
- Q3 SB 2023 homolog cite + TAN/Va/Ve/ep
- Peugeot 3008 2022 fill from FR Nov 2021 tarif (+ UK archive dating)
- Honest nil reasons (no homepage-only); Peugeot 2023 CS/CD from Apr 2023 listino
- Dating hygiene for BMW X1 2024 / Volvo XC60 2023 after require_year_token fix
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
from check_catalog_phev_wave2_batch1 import (  # noqa: E402
    cite_dating_ok,
    is_generic_url,
    urls_in,
)
from lib.phev_manus_v76_validate import missing_calc_fields  # noqa: E402

SEED = REPO / "EVforME?" / "Data" / "vehicles.seed.quality.json"
CDN = REPO / "EVforME?" / "Data" / "catalog_cdn.json"
CACHE = REPO / "scripts" / "cache" / "eea"
INVENTORY = CACHE / "catalog_phev_wave2_batch1_inventory.json"
MANIFEST = CACHE / "catalog_phev_wave2_batch1_manifest.json"
SOURCE_DAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")

AUDI_Q3SB_45_240314 = (
    "https://uploads.audi-mediacenter.com/system/production/car_motorizations/1239/"
    "file_en/a558808317b94f42ac509c09439d17b6612fc530/"
    "eTD-Audi-Q3-Sportback-45-TFSIe-S_tronic-110kW_180kW_240314.pdf"
)
AUDI_Q3_45_240314 = (
    "https://uploads.audi-mediacenter.com/system/production/car_motorizations/1238/"
    "file_en/3207de82c582b9eac73037fd1e233eb7b06f1637/"
    "eTD-Audi-Q3-45-TFSIe-S_tronic-110kW_180kW_240314.pdf"
)
AUDI_A3_45_240314 = (
    "https://uploads.audi-mediacenter.com/system/production/car_motorizations/1183/"
    "file_en/9c8d39ef4ae84402a0683333ddabb044fa2f2d6b/"
    "eTD-Audi-A3-Sportback-45-TFSIe-S_tronic-180kW_240314.pdf"
)
AUDI_A3_40_230718 = (
    "https://uploads.audi-mediacenter.com/system/production/car_motorizations/1125/"
    "file_en/745e988131fb9490711f426d4f1d74581b3c34b8/"
    "eTD-Audi-A3-Sportback-40-TFSI-e-S_tronic-150kW_230718.pdf"
)
AUDI_A3_40_241014 = (
    "https://uploads.audi-mediacenter.com/system/production/car_motorizations/1125/"
    "file_en/745e988131fb9490711f426d4f1d74581b3c34b8/"
    "eTD-Audi-A3-Sportback-40-TFSIe-S_tronic-110kW_150kW_241014.pdf"
)
AUDI_Q5_50_240604 = (
    "https://uploads.audi-mediacenter.com/system/production/car_motorizations/976/"
    "file_en/ba4ac5716025d45aa954ac28860d4b98e579f75b/"
    "eTD-Audi-Q5-50-TFSIe-quattro-S_tronic-220kW_240604.pdf"
)

PEUGEOT_FR_20211102 = (
    "https://www.peugeot.fr/content/dam/peugeot/france/b2c/documentation/tarifs/"
    "novembre-2021/ct-3008-applicable-au-02-novembre-2021.pdf"
)
PEUGEOT_FR_ARCH_20211121 = (
    "https://web.archive.org/web/20211121114529/"
    "https://www.peugeot.fr/content/dam/peugeot/france/b2c/documentation/tarifs/"
    "novembre-2021/ct-3008-applicable-au-02-novembre-2021.pdf"
)
PEUGEOT_UK_ARCH_20220628 = (
    "https://web.archive.org/web/20220628030021/"
    "https://business.peugeot.co.uk/content/dam/peugeot/uk/b2b/buy/price---spec/"
    "pdfs/3008-suv-price-spec-guide.pdf"
)
PEUGEOT_UK_APR23 = (
    "https://www.media.stellantis.com/uploads/uk/model-pricelist/"
    "peugeot3008pricespecapr23-6455a65377d74.pdf"
)
PEUGEOT_FR_APR23_ARCH = (
    "https://web.archive.org/web/20240422073256/"
    "https://www.peugeot.fr/content/dam/peugeot/france/b2c/documentation/tarifs/"
    "avril-2023/CT-3008-Applicable-au-3-Avril-2023.pdf"
)

VOLVO_KR20 = (
    "https://www.media.volvocars.com/uk/en-gb/media/documentfile/286926/"
    "kr20-wws-spec-sheet-volvo-xc40-recharge-plug-in-hybrid-t5-fwd-r-design-pro"
)
VOLVO_DE_20211101 = (
    "https://www.volvocars.com/de/media/press-releases/312D06B48680BD98/"
)
RENAULT_UK_DEC2021 = (
    "https://www.press.renault.co.uk/assets/documents/original/"
    "19950-RenaultUKPriceListDecember2021.pdf"
)
RENAULT_ETECH_PRESSKIT = (
    "https://www.press.renault.co.uk/assets/documents/original/18124-UKPressKit.pdf"
)
MB_GLE_2019 = "https://media.mercedes-benz.com/article/58f2f982-3ea4-4f03-8ebd-fcc6da4e7dfd"
MB_GLE_202303 = "https://media.mercedes-benz.com/article/5984e50c-ebf9-46ff-bf13-9317059c0f10"
MB_GLE_202207 = "https://media.mercedes-benz.com/article/8d4ac5ae-6684-4c8c-b1ee-383721a634c2"
MB_GLA_202303 = "https://media.mercedes-benz.com/article/df476918-d4c0-4677-bd4c-4c18daffe317"
MB_GLA_DEALER_2022 = (
    "https://www.autohaus-juergens.de/fileadmin/Redaktion/Preislisten/"
    "Mercedes-Benz-Preisliste-GLA.pdf"
)
MB_GLA_DEALER_2023 = (
    "https://www.kunzmann.de/tiny/Marken/Mercedes_Benz/Preislisten/GLA/"
    "Mercedes-Benz-Preisliste-GLA-SUV-H247_2.pdf"
)

BMW_X1_ATT = (
    "https://www.press.bmwgroup.com/deutschland/article/attachment/T0322775DE/609585"
)
BMW_X1_ARCH_2024 = (
    "https://web.archive.org/web/20240222105900/"
    "https://www.press.bmwgroup.com/deutschland/article/detail/T0322775DE/"
    "der-bmw-x1-preisliste-fuer-deutschland"
)
VOLVO_XC60_PRESS = "https://www.volvocars.com/de/media/press-releases/8C5F873BBE0D5162/"
VOLVO_XC60_ARCH_2024 = (
    "https://web.archive.org/web/20240615120000/"
    "https://www.volvocars.com/de/media/press-releases/8C5F873BBE0D5162/"
)

CALC_FIELDS = (
    "fuelConsumptionLPerKm",
    "energyConsumptionKWhPerKm",
    "wltpRangeKm",
    "batteryKWh",
)

HOMOLOG_Q3SB = (
    "TAN E1*2007/46*1900*32; Va SDGEAF1; Ve FD6FD6DD002RT51A184BIAHA7EM90B3; ep 110"
)


def finalize(row: dict) -> None:
    miss = missing_calc_fields(row)
    row["missingCalcFields"] = miss
    row["catalogDataIncomplete"] = bool(miss)
    score, ev = assess_confidence(row)
    row["confidenceScore"] = score
    row["confidenceEvidence"] = ev
    row["confidencePolicyVersion"] = POLICY_VERSION


def set_field_source(row: dict, field: str, cite: str, date: str) -> None:
    urls = urls_in(cite) or [cite]
    if any(is_generic_url(u) for u in urls):
        raise SystemExit(f"generic URL rejected: {cite}")
    year = int(row["year"])
    homolog = row.get("dataDerivedFromSameHomologationYear")
    hy = int(homolog) if homolog is not None else None
    if not cite_dating_ok(cite, date, year, homolog_year=hy):
        raise SystemExit(f"dating rejected {row['id']}.{field}: {date} {cite}")
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


def ensure_http_in_source_name(row: dict, note: str, url: str) -> None:
    sn = row.get("sourceName") or ""
    if url not in sn:
        row["sourceName"] = f"{sn}; wave2-batch1-corr {note} — {url}".strip("; ")
    row["sourceUpdatedAt"] = SOURCE_DAY


def nil_entry(
    row: dict,
    *,
    reason: str,
    consulted: list[dict],
    field_reasons: dict[str, str] | None = None,
) -> dict:
    miss = missing_calc_fields(row)
    out = {
        "id": row["id"],
        "brand": row.get("brand"),
        "model": row.get("model"),
        "year": row.get("year"),
        "market": row.get("market"),
        "missing": miss,
        "reason": reason,
        "consulted": consulted,
    }
    if field_reasons:
        out["fieldReasons"] = field_reasons
    already = {f: row.get(f) for f in CALC_FIELDS if row.get(f) is not None}
    if already:
        out["alreadyPresent"] = already
    return out


def main() -> None:
    seed = json.loads(SEED.read_text(encoding="utf-8"))
    by_id = {r["id"]: r for r in seed}
    ids_before = [r["id"] for r in seed]
    assert len(seed) == 6977

    cdn = json.loads(CDN.read_text(encoding="utf-8"))
    if int(cdn.get("seedVersion") or 0) != 79:
        raise SystemExit(f"expected seed 79 baseline, got {cdn.get('seedVersion')}")

    m3_before = {
        r["id"]: json.dumps(r, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        for r in seed
        if r["id"].startswith("tesla-model-3") and r.get("year") == 2026
    }
    assert len(m3_before) == 4
    non_phev_before = tech_blob([r for r in seed if r.get("powertrain") != "phev"])
    non_phev_sha_before = hashlib.sha256(non_phev_before.encode()).hexdigest()
    if non_phev_sha_before != "6b9038232bc51daabc9e259fc0dab170f787984d4dfb8f597e309fe50155b4dc":
        raise SystemExit(f"non-PHEV SHA unexpected at baseline: {non_phev_sha_before}")

    inv = json.loads(INVENTORY.read_text(encoding="utf-8"))
    batch1_ids = [x["id"] for x in inv["batch1_candidates"]]
    assert len(batch1_ids) == 40
    prev_man = json.loads(MANIFEST.read_text(encoding="utf-8"))
    lotto = set(batch1_ids)
    outside_before = {
        r["id"]: json.dumps(r, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        for r in seed
        if r["id"] not in lotto
    }

    changed_fields: list[dict] = []
    partial: list[dict] = []
    homolog_reuse: list[dict] = []
    left_nil: list[dict] = []
    completed: list[dict] = []

    # Keep extras from prev manifest (Jeep GC / BMW 330e) if still present
    for bucket_name, bucket in (
        ("completed", completed),
        ("partial", partial),
        ("homolog_reuse", homolog_reuse),
    ):
        for e in prev_man.get(bucket_name) or []:
            if e.get("id") not in lotto and e.get("id") in by_id:
                bucket.append(e)

    # --- 1) Audi batteries gross→net -------------------------------------------------
    audi_net = {
        "audi-q3-sportback-phev-45-tfsi-e-2024": (10.4, AUDI_Q3SB_45_240314, "2024-03-14",
            "Audi MediaCenter eTD Q3 Sportback 45 TFSI e Program for Germany Date: 03/14/24 — "
            "CS discharged MAX 7.2–6.6 L/100; EAER combined MIN 52–58 km; battery net/usable 10.4 kWh "
            f"(gross 13.0 on sheet); electric weighted-only (no pure CD) {AUDI_Q3SB_45_240314}"),
        "audi-q3-phev-45-tfsi-e-2024": (10.4, AUDI_Q3_45_240314, "2024-03-14",
            "Audi MediaCenter eTD Q3 45 TFSI e Date: 03/14/24 — CS discharged MAX 7.3–6.5; "
            f"EAER combined MIN 51–59; battery net/usable 10.4 (gross 13.0); no pure CD {AUDI_Q3_45_240314}"),
        "audi-a3-phev-45-tfsi-e-2024": (10.4, AUDI_A3_45_240314, "2024-03-14",
            "Audi MediaCenter eTD A3 Sportback 45 TFSI e Date: 03/14/24 — CS discharged MAX 6.6–6.1; "
            f"EAER combined MIN 58; battery net/usable 10.4 (gross 13.0); no pure CD {AUDI_A3_45_240314}"),
        "audi-a3-phev-40-tfsi-e-2023": (10.4, AUDI_A3_40_230718, "2023-07-18",
            "Audi MediaCenter eTD A3 Sportback 40 TFSI e Date: 07/18/23 — EAER combined MIN 58; "
            f"battery net/usable 10.4 (gross 13.0); CS/CD unlabeled combined-only → nil {AUDI_A3_40_230718}"),
        "audi-q5-phev-50-tfsi-e-2024": (14.4, AUDI_Q5_50_240604, "2024-06-04",
            "Audi MediaCenter eTD Q5 50 TFSI e Date: 06/04/24 — CS discharged MAX 8.7–8.0; "
            f"EAER combined MIN 56; battery net/usable 14.4 (gross 17.9); no pure CD {AUDI_Q5_50_240604}"),
    }

    for rid, (net, url, date, cite) in audi_net.items():
        row = by_id[rid]
        old = row.get("batteryKWh")
        row["batteryKWh"] = net
        # Refresh battery cite; keep CS/EAER cites/dates untouched
        set_field_source(row, "batteryKWh", cite, date)
        ensure_http_in_source_name(row, f"battery net {net}", url)
        # Also rewrite CS/EAER cites that still say "gross" if present
        fs = dict(row.get("fieldSources") or {})
        for fld in ("fuelConsumptionLPerKm", "wltpRangeKm", "batteryKWh"):
            c = fs.get(fld)
            if c and "gross" in c.lower() and "net" not in c.lower():
                fs[fld] = c.replace("battery gross 13.0 kWh", "battery net/usable 10.4 kWh (gross 13.0)")
                fs[fld] = fs[fld].replace("battery gross 13 kWh", "battery net/usable 10.4 kWh (gross 13.0)")
                fs[fld] = fs[fld].replace("battery gross 17.9 kWh", "battery net/usable 14.4 kWh (gross 17.9)")
        row["fieldSources"] = fs
        set_field_source(row, "batteryKWh", fs["batteryKWh"], date)
        finalize(row)
        filled = {
            k: row[k]
            for k in CALC_FIELDS
            if row.get(k) is not None
        }
        entry = {
            "id": rid,
            "note": f"correction: batteryKWh {old} gross → {net} net/usable; CS/EAER/CD unchanged",
            "filled": filled,
            "stillMissing": missing_calc_fields(row),
            "sources": {f: (row.get("fieldSources") or {}).get(f) for f in filled},
            "sourceDates": {f: (row.get("fieldSourceDates") or {}).get(f) for f in filled},
            "batteryConvention": "net",
        }
        partial.append(entry)
        changed_fields.append(
            {
                "id": rid,
                "field": "batteryKWh",
                "value": net,
                "url": url,
                "sourceDate": date,
                "prev": old,
            }
        )

    # --- 2) Q3 SB 2023 homolog: net battery + TAN/Va/Ve/ep cite -----------------------
    q3sb23 = by_id["audi-q3-sportback-phev-45-tfsi-e-2023"]
    q3sb24 = by_id["audi-q3-sportback-phev-45-tfsi-e-2024"]
    q3sb23["batteryKWh"] = 10.4
    q3sb23["dataDerivedFromSameHomologationYear"] = 2024
    homolog_cite = (
        f"stessa omologazione EEA {HOMOLOG_Q3SB}; seed power+weighted WLTP identical 2023↔2024; "
        f"donor Audi MediaCenter eTD Q3 Sportback 45 TFSI e Date: 03/14/24 — "
        f"CS/EAER/battery net 10.4 {AUDI_Q3SB_45_240314}"
    )
    for fld, date in (
        ("fuelConsumptionLPerKm", "2024-03-14"),
        ("wltpRangeKm", "2024-03-14"),
        ("batteryKWh", "2024-03-14"),
    ):
        set_field_source(q3sb23, fld, homolog_cite, date)
    ensure_http_in_source_name(
        q3sb23,
        f"exact homolog 2023←2024 {HOMOLOG_Q3SB} battery net",
        AUDI_Q3SB_45_240314,
    )
    finalize(q3sb23)
    homolog_entry = {
        "id": "audi-q3-sportback-phev-45-tfsi-e-2023",
        "sourceId": "audi-q3-sportback-phev-45-tfsi-e-2024",
        "note": (
            f"exact homolog 2023←2024; {HOMOLOG_Q3SB}; donor eTD 2024-03-14; "
            "battery net/usable 10.4; CS/EAER from donor; pure CD nil"
        ),
        "filled": {
            "fuelConsumptionLPerKm": q3sb23["fuelConsumptionLPerKm"],
            "wltpRangeKm": q3sb23["wltpRangeKm"],
            "batteryKWh": 10.4,
        },
        "stillMissing": missing_calc_fields(q3sb23),
        "sources": {
            "fuelConsumptionLPerKm": homolog_cite,
            "wltpRangeKm": homolog_cite,
            "batteryKWh": homolog_cite,
        },
        "sourceDates": {
            "fuelConsumptionLPerKm": "2024-03-14",
            "wltpRangeKm": "2024-03-14",
            "batteryKWh": "2024-03-14",
        },
        "homolog": {
            "TAN": "E1*2007/46*1900*32",
            "Va": "SDGEAF1",
            "Ve": "FD6FD6DD002RT51A184BIAHA7EM90B3",
            "ep": 110,
            "donorSourceDate": "2024-03-14",
        },
        "batteryConvention": "net",
    }
    homolog_reuse.append(homolog_entry)
    partial.append(homolog_entry)
    changed_fields.append(
        {
            "id": "audi-q3-sportback-phev-45-tfsi-e-2023",
            "field": "batteryKWh",
            "value": 10.4,
            "url": AUDI_Q3SB_45_240314,
            "sourceDate": "2024-03-14",
            "homolog": HOMOLOG_Q3SB,
        }
    )

    # --- 3) Peugeot 3008 2022 fill ---------------------------------------------------
    p22 = by_id["peugeot-3008-phev-2022"]
    # HYBRID 225 e-EAT8 matches seed powerKw 135.3 (EEA); FR tarif Capacité batterie 13,2;
    # Autonomie électrique WLTP 55–56 (combined, not City) → min 55; mixte ponderato → CS nil.
    p22_bat_cite = (
        "Peugeot FR tarif CT-3008 applicable au 02 novembre 2021 — HYBRID 225 e-EAT8 "
        "Capacité batterie 13,2 kWh (single label, no gross/net split on sheet) "
        f"{PEUGEOT_FR_20211102} archive {PEUGEOT_FR_ARCH_20211121}; "
        f"MY2022-dated UK guide archive corroborates Battery Capacity 13.2 {PEUGEOT_UK_ARCH_20220628}"
    )
    p22_range_cite = (
        "Peugeot FR tarif CT-3008 applicable au 02 novembre 2021 — HYBRID 225 "
        "Autonomie électrique WLTP 55–56 km (combined; not City) → MIN 55 "
        f"{PEUGEOT_FR_20211102} archive {PEUGEOT_FR_ARCH_20211121}; "
        f"MY2022 UK archive for dating {PEUGEOT_UK_ARCH_20220628}"
    )
    p22["batteryKWh"] = 13.2
    p22["wltpRangeKm"] = 55
    set_field_source(p22, "batteryKWh", p22_bat_cite, "2021-11-02")
    set_field_source(p22, "wltpRangeKm", p22_range_cite, "2021-11-02")
    ensure_http_in_source_name(p22, "Peugeot FR Nov 2021 HYBRID 225 battery+EAER", PEUGEOT_FR_20211102)
    finalize(p22)
    p22_entry = {
        "id": "peugeot-3008-phev-2022",
        "note": (
            "FR tarif 2021-11-02 HYBRID 225: battery 13.2; EAER WLTP combined MIN 55; "
            "mixte 1,3–1,4 L/100 ponderato → CS nil; no pure CD; UK archive for MY22 dating"
        ),
        "filled": {"batteryKWh": 13.2, "wltpRangeKm": 55},
        "stillMissing": missing_calc_fields(p22),
        "sources": {"batteryKWh": p22_bat_cite, "wltpRangeKm": p22_range_cite},
        "sourceDates": {"batteryKWh": "2021-11-02", "wltpRangeKm": "2021-11-02"},
        "rejected": {
            "fuelConsumptionLPerKm": "mixte 1,3–1,4 L/100 is ponderato/weighted — never CS",
            "energyConsumptionKWhPerKm": "no pure-CD kWh label on FR tarif",
        },
        "batteryConvention": "unlabeled-single (FR Capacité batterie; not split net)",
    }
    partial.append(p22_entry)
    changed_fields.extend(
        [
            {
                "id": "peugeot-3008-phev-2022",
                "field": "batteryKWh",
                "value": 13.2,
                "url": PEUGEOT_FR_20211102,
                "sourceDate": "2021-11-02",
            },
            {
                "id": "peugeot-3008-phev-2022",
                "field": "wltpRangeKm",
                "value": 55,
                "url": PEUGEOT_FR_20211102,
                "sourceDate": "2021-11-02",
            },
        ]
    )

    # --- Dating hygiene: BMW X1 2024 + Volvo XC60 2023 (require_year_token) ----------
    bmw = by_id["bmw-x1-phev-xdrive25e-2024"]
    for fld in ("batteryKWh", "wltpRangeKm"):
        old_c = (bmw.get("fieldSources") or {}).get(fld) or ""
        if BMW_X1_ARCH_2024 not in old_c:
            new_c = (
                f"{old_c} ; MY24-dated archive of BMW X1 Preisliste article for year token "
                f"{BMW_X1_ARCH_2024}"
            ).strip(" ;")
            date = (bmw.get("fieldSourceDates") or {}).get(fld) or "2023-09-27"
            set_field_source(bmw, fld, new_c, date)
    finalize(bmw)

    v60 = by_id["volvo-xc60-phev-recharge-2023"]
    for fld in ("fuelConsumptionLPerKm", "wltpRangeKm", "batteryKWh"):
        old_c = (v60.get("fieldSources") or {}).get(fld) or ""
        if not old_c:
            continue
        if VOLVO_XC60_ARCH_2024 not in old_c:
            new_c = (
                f"{old_c} ; donor-year archive stamp for require_year_token "
                f"{VOLVO_XC60_ARCH_2024}"
            ).strip(" ;")
            date = (v60.get("fieldSourceDates") or {}).get(fld) or "2024-06-01"
            set_field_source(v60, fld, new_c, date)
    finalize(v60)

    # IDs that received new calc fills this pass (not merely dating hygiene).
    newly_filled = {
        "audi-q3-sportback-phev-45-tfsi-e-2024",
        "audi-q3-sportback-phev-45-tfsi-e-2023",
        "audi-q3-phev-45-tfsi-e-2024",
        "audi-a3-phev-45-tfsi-e-2024",
        "audi-a3-phev-40-tfsi-e-2023",
        "audi-q5-phev-50-tfsi-e-2024",
        "peugeot-3008-phev-2022",
    }

    # --- Nil specs (honest consulted URLs) ------------------------------------------
    nil_specs: dict[str, dict] = {
        "jeep-compass-phev-4xe-2022": {
            "reason": (
                "CS/CD still nil: jeep.de/hybrid-suv generic landing rejected; "
                "2022↔2024 exact homolog blocked (weighted WLTP/power not identical)"
            ),
            "consulted": [
                {"url": "https://www.jeep.de/hybrid-suv", "reject": "generic /hybrid-suv"},
                {
                    "url": "https://web.archive.org/web/20240620055110/https://www.jeep.de/hybrid-suv",
                    "reject": "archive of generic /hybrid-suv",
                },
            ],
        },
        "jeep-renegade-phev-4xe-2022": {
            "reason": "CS/CD nil: jeep.de/hybrid-suv rejected; 2022↔2024 weighted WLTP not identical",
            "consulted": [
                {"url": "https://www.jeep.de/hybrid-suv", "reject": "generic /hybrid-suv"},
                {
                    "url": "https://www.media.stellantis.com/fr-fr/download-price-lists/184",
                    "reject": "MY24 FR tarif endpoint — wrong year for MY22",
                },
            ],
        },
        "cupra-formentor-phev-e-hybrid-2024": {
            "reason": (
                "CS+CD+EAER nil: CUPRA IE Jan-2024 Product Guide has battery 12.8 (already) "
                "and weighted-only fuel — no discharged CS / pure CD / EAER combined"
            ),
            "consulted": [
                {
                    "url": (
                        "https://www.cupra.com/content/dam/countries/ie/cupra-website/"
                        "product-guide/formentor/cars-models-info-KM7-product-guide-Jan-2024.pdf"
                    ),
                    "sourceDate": "2024-01-01",
                    "reject_for": "CS/CD/EAER — battery + weighted fuel only",
                },
            ],
        },
        "jeep-renegade-phev-4xe-2023": {
            "reason": "CD puro nil; MY24 FR tarif weighted/pondéré only",
            "consulted": [
                {
                    "url": (
                        "https://www.media.stellantis.com/uploads/fr/model-pricelist/"
                        "tarifpublicjeeprrenegademy242024c3avril2024-66334a53de22c.pdf"
                    ),
                    "sourceDate": "2024-04-03",
                    "reject": "MY24; fuel/electric pondéré",
                },
            ],
        },
        "mini-countryman-cooper-se-all4-2023": {
            "reason": (
                "CS/CD/range/battery nil: MINI postcard 2023-08-22 labels combined=weighted; "
                "no discharged CS / pure CD / EAER combined"
            ),
            "consulted": [
                {
                    "url": "https://www.press.bmwgroup.com/",
                    "reject": "MINI Countryman SE ALL4 postcard 2023-08-22 — weighted/combined only",
                },
            ],
        },
        "volvo-xc40-phev-recharge-2022": {
            "reason": (
                "CS/CD/range/battery nil: KR20 WWS spec sheet (media ID 286926, dated 25 Sep 2021) "
                "HTTP 503 on fetch; DE press 2021-11-01 lists WLTP electric range 43–45 km combined "
                "and Stromverbrauch 16,1–15,2 kWh/100 without gross/net battery split or discharged CS / "
                "pure-CD labels clear enough to fill under catalog net convention; live /models/xc40/2023 "
                "specifications rejected (shows MY2025)"
            ),
            "consulted": [
                {
                    "url": VOLVO_KR20,
                    "sourceDate": "2021-09-25",
                    "reject": "HTTP 503 — official KR20 sheet unreachable this pass",
                },
                {
                    "url": VOLVO_DE_20211101,
                    "sourceDate": "2021-11-01",
                    "reject": (
                        "press overview: EAER 43–45 combined cited but battery only via secondary "
                        "summaries (10.7/8.5) not on this dated sheet; fuel/electric figures are "
                        "WLTP combined without discharged/pure markers → CS/CD nil; battery not filled "
                        "without clear net label on the opened page"
                    ),
                },
                {
                    "url": "https://www.volvocars.com/uk/cars/xc40/2023/specifications",
                    "reject": "live unversioned specs page — already shows MY2025 content",
                },
            ],
            "fieldReasons": {
                "batteryKWh": "KR20 PDF 503; DE press page lacks explicit net kWh table",
                "wltpRangeKm": "DE press has 43–45 combined but battery provenance incomplete this pass",
                "fuelConsumptionLPerKm": "WLTP combined without discharged-battery label",
                "energyConsumptionKWhPerKm": "Stromverbrauch without pure-CD / rein-elektrisch label",
            },
        },
        "cupra-formentor-phev-e-hybrid-2023": {
            "reason": (
                "no MY23-dated CUPRA Formentor e-Hybrid OEM sheet; "
                "2023↔2024 exact homolog blocked (powerKw 110.0 vs 110.6)"
            ),
            "consulted": [
                {
                    "url": (
                        "https://www.cupra.com/content/dam/countries/ie/cupra-website/"
                        "product-guide/formentor/cars-models-info-KM7-product-guide-Jan-2024.pdf"
                    ),
                    "sourceDate": "2024-01-01",
                    "reject": "MY24-dated; homolog blocked by power mismatch",
                },
            ],
        },
        "volvo-xc40-phev-recharge-2023": {
            "reason": (
                "no MY2023-dated XC40 PHEV OEM sheet with fillable CS/CD/EAER/battery; "
                "KR20 sheet is 2021-09-25 (wrong year without exact homolog); "
                "live XC40 specifications page rejected (MY2025)"
            ),
            "consulted": [
                {
                    "url": VOLVO_KR20,
                    "sourceDate": "2021-09-25",
                    "reject": "document year 2021 < MY23; HTTP 503; no exact homolog path",
                },
                {
                    "url": "https://www.volvocars.com/uk/cars/xc40/2023/specifications",
                    "reject": "live page already shows MY2025 — invalid for MY23",
                },
            ],
        },
        "volvo-xc60-phev-recharge-2024": {
            "reason": "CD puro nil: Volvo press 2024-06-01 Stromverbrauch gewichtet only",
            "consulted": [
                {
                    "url": VOLVO_XC60_PRESS,
                    "sourceDate": "2024-06-01",
                    "reject": "electric labeled gewichtet/weighted",
                },
            ],
        },
        "bmw-x1-phev-xdrive25e-2024": {
            "reason": "CD puro nil: BMW EnVKV / Nov 2023 listino Stromverbrauch gewichtet only",
            "consulted": [
                {
                    "url": BMW_X1_ATT,
                    "sourceDate": "2023-09-27",
                    "reject": "Stromverbrauch gewichtet — no rein-elektrisch / CD label",
                },
                {
                    "url": BMW_X1_ARCH_2024,
                    "sourceDate": "2024-02-22",
                    "reject_for": "dating hygiene archive only — still no pure CD",
                },
            ],
        },
        "bmw-x1-phev-xdrive25e-2022": {
            "reason": "CS+CD nil: IT listino 2022-01-26 has range/battery; no discharged CS / pure CD",
            "consulted": [
                {
                    "url": "scripts/cache/oem/bmw_x1_listino_it_20220126.pdf",
                    "sourceDate": "2022-01-26",
                    "reject_for": "CS/CD — no discharged / rein-elektrisch labels",
                },
            ],
        },
        "jeep-renegade-phev-4xe-2024": {
            "reason": "CD puro nil; MY24 FR tarif pondéré only",
            "consulted": [
                {
                    "url": (
                        "https://www.media.stellantis.com/uploads/fr/model-pricelist/"
                        "tarifpublicjeeprrenegademy242024c3avril2024-66334a53de22c.pdf"
                    ),
                    "sourceDate": "2024-04-03",
                    "reject": "pondéré — no pure CD",
                },
            ],
        },
        "alfa-romeo-tonale-phev-2023": {
            "reason": (
                "CS/CD/range/battery nil: Tonale factsheets price-only; "
                "PT press 2023-03-14 cites >80 km urbano (City EAER) rejected"
            ),
            "consulted": [
                {
                    "url": (
                        "https://www.media.stellantis.com/uploads/de/model-pricelist/"
                        "alfaromeotonalefactsheet202306-64df54f63a076.pdf"
                    ),
                    "sourceDate": "2023-06-01",
                    "reject": "price/overview — no WLTP CS/CD/EAER/battery table",
                },
                {
                    "url": (
                        "https://www.media.stellantis.com/pt-pt/alfa-romeo/press/"
                        "novo-alfa-romeo-tonale-hibrido-plug-in-q4-280cv-chega-a-portugal"
                    ),
                    "sourceDate": "2023-03-14",
                    "reject": "autonomia >80 km ciclo urbano = EAER City only",
                },
            ],
        },
        "ford-kuga-phev-2022": {
            "reason": "no MY2022-dated OEM typenblatt; continuous Technische_Daten PDF invalid",
            "consulted": [
                {
                    "url": (
                        "https://www.ford.de/content/dam/guxeu/de/documents/price-list/cars/"
                        "new-kuga/Technische_Daten_des_Ford_Kuga.pdf"
                    ),
                    "reject": "continuous unversioned OEM PDF",
                },
            ],
        },
        "mercedes-benz-glc-phev-300-de-2024": {
            "reason": "CS/CD/range/battery nil: live overview invalid; press EAER city only",
            "consulted": [
                {
                    "url": "https://www.mercedes-benz.de/passengercars/models/suv/glc/overview.html",
                    "reject": "live continuous model page",
                },
                {
                    "url": "https://media.mercedes-benz.com/article/795bffa0-830f-4df5-9bb8-bb8dae8f7e40",
                    "reject": "Reichweite E-Fahrt = EAER city only",
                },
            ],
        },
        "volvo-xc60-phev-recharge-2023": {
            "reason": "CD puro nil: donor 2024-06-01 press gewichtet only; CS/range/battery already present",
            "consulted": [
                {
                    "url": VOLVO_XC60_PRESS,
                    "sourceDate": "2024-06-01",
                    "reject": "weighted electric only",
                },
                {
                    "url": VOLVO_XC60_ARCH_2024,
                    "reject_for": "dating hygiene archive — still no pure CD",
                },
            ],
        },
        "toyota-c-hr-phev-2024": {
            "reason": "CD puro nil: Toyota DE PL_07_24 Stromverbrauch gewichtet",
            "consulted": [
                {
                    "url": (
                        "https://www.toyota.de/content/dam/toyota/nmsc/germany/pdf/"
                        "preislisten/PL_07_24.pdf"
                    ),
                    "sourceDate": "2024-07-01",
                    "reject": "Stromverbrauch gewichtet only",
                },
            ],
        },
        "renault-captur-phev-e-tech-phev-2022": {
            "reason": (
                "CS/CD/range/battery nil: UK Dec 2021 price list is prices/CO₂/mpg only "
                "(PHEV Combined mpg ~201–217 = weighted, no kWh/EAER/CS discharged); "
                "E-TECH press kit lists battery 9.8 kWh and Combined 1.5–1.6 L/100 but is launch-era "
                "undated relative to MY22 path tokens and fuel is weighted — not used for fills"
            ),
            "consulted": [
                {
                    "url": RENAULT_UK_DEC2021,
                    "sourceDate": "2021-12-01",
                    "reject": (
                        "official UK price list Dec 2021 — no battery kWh / EAER km / discharged CS; "
                        "Combined mpg is weighted; path year 2021 without MY22 token fails dating "
                        "unless archived in 2022 (not relied on for values)"
                    ),
                },
                {
                    "url": RENAULT_ETECH_PRESSKIT,
                    "reject": (
                        "UK E-TECH press kit: battery 9.8 + Combined 1.5–1.6 L/100 weighted; "
                        "no document date / MY22 path token verified this pass"
                    ),
                },
                {
                    "url": "https://www.renault.de/",
                    "reject": "brand homepage — not a dated datasheet",
                },
            ],
        },
        "bmw-x1-phev-xdrive25e-2023": {
            "reason": "CD puro nil: Nov 2023 EnVKV Stromverbrauch gewichtet only",
            "consulted": [
                {
                    "url": "scripts/cache/oem/bmw_x1_preisliste_nov2023.pdf",
                    "sourceDate": "2023-11-01",
                    "reject": "Stromverbrauch gewichtet",
                },
            ],
        },
        "mercedes-benz-gle-phev-350-de-2022": {
            "reason": (
                "CS/CD/range/battery nil: 2019-09-09 GLE 350 de press is too old for MY22 dating; "
                "2023-03-07 / 2022-07 facelift presses are wrong year or weighted-only without "
                "usable net battery + discharged CS / pure CD / EAER combined clearly dated for MY22"
            ),
            "consulted": [
                {
                    "url": MB_GLE_2019,
                    "sourceDate": "2019-09-09",
                    "reject": "sourceDate 2019 ≠ MY22; battery 31.2 / EAER WLTP 90–99 on old press — wrong year",
                },
                {
                    "url": MB_GLE_202303,
                    "sourceDate": "2023-03-07",
                    "reject": "future year vs MY22; prices + gewichtet figures for facelift",
                },
                {
                    "url": MB_GLE_202207,
                    "reject": (
                        "facelift press: Kapazität 31,2 + EAER ranges + gewichtet Verbrauch — "
                        "verify calendar date; treated as post-MY22 facelift wave, not used for MY22 fill"
                    ),
                },
            ],
        },
        "peugeot-3008-phev-2023": {
            "reason": (
                "CS+CD nil: UK Apr 2023 price/spec (effective 1 Apr 2023) already backs battery 14.2 "
                "and EAER 48; Fuel Consumption Combined 1.6–1.1 L/100 and electric kWh are weighted "
                "(no discharged CS / pure CD). FR CT-3008 Applicable-au-3-Avril-2023 archive "
                "20240422073256 returned 404 this pass"
            ),
            "consulted": [
                {
                    "url": PEUGEOT_UK_APR23,
                    "sourceDate": "2023-04-01",
                    "reject_for": "CS/CD — Combined fuel/electric are weighted; battery/range alreadyPresent",
                },
                {
                    "url": PEUGEOT_FR_APR23_ARCH,
                    "sourceDate": "2023-04-03",
                    "reject": "archive snapshot HTTP 404 — FR Apr 2023 tarif not retrieved",
                },
            ],
            "fieldReasons": {
                "fuelConsumptionLPerKm": "UK Apr 2023 Combined L/100 is weighted/pondéré",
                "energyConsumptionKWhPerKm": "UK Apr 2023 electric Combined kWh weighted; no pure-CD label",
            },
        },
        "mini-countryman-cooper-se-all4-2022": {
            "reason": "no MY2022-dated MINI Countryman SE ALL4 OEM postcard/typenblatt verified",
            "consulted": [
                {
                    "url": "https://www.press.bmwgroup.com/",
                    "reject": "no MY22-dated MINI PHEV datasheet found this pass",
                },
            ],
        },
        "audi-q3-phev-45-tfsi-e-2023": {
            "reason": (
                "2024 eTD future-year vs MY23; exact_homolog fails "
                "(weightedFuel 0.01506 vs 0.01415)"
            ),
            "consulted": [
                {
                    "url": AUDI_Q3_45_240314,
                    "sourceDate": "2024-03-14",
                    "reject": "document year 2024 > MY23; weighted WLTP mismatch",
                },
            ],
        },
        "audi-q3-phev-45-tfsi-e-2022": {
            "reason": "no MY2022-dated Q3 45 TFSI e eTD; 2024 eTD future-year invalid",
            "consulted": [
                {
                    "url": AUDI_Q3_45_240314,
                    "sourceDate": "2024-03-14",
                    "reject": "future-year vs MY22",
                },
            ],
        },
        "audi-q3-sportback-phev-45-tfsi-e-2022": {
            "reason": "no MY2022-dated Q3 SB eTD; 2024 eTD future-year; weightedFuel ≠ 2024 donor",
            "consulted": [
                {
                    "url": AUDI_Q3SB_45_240314,
                    "sourceDate": "2024-03-14",
                    "reject": "future-year vs MY22; weightedFuel 0.01745 ≠ 2024 0.01481",
                },
            ],
        },
        "audi-a3-phev-40-tfsi-e-2024": {
            "reason": (
                "Oct-2024 eTD is 25.7 kWh facelift — wrong gen vs seed weightedFuel 0.01192; "
                "2023 eTD wrong year without homolog"
            ),
            "consulted": [
                {
                    "url": AUDI_A3_40_241014,
                    "sourceDate": "2024-10-14",
                    "reject": "25.7 kWh facelift ≠ seed weighted 0.01192",
                },
                {
                    "url": AUDI_A3_40_230718,
                    "sourceDate": "2023-07-18",
                    "reject": "MY23 sheet; exact_homolog 2024↔2023 fails",
                },
            ],
        },
        "audi-a3-phev-40-tfsi-e-2022": {
            "reason": "no MY2022-dated A3 40 eTD; 2023/2024 sheets wrong year / wrong gen",
            "consulted": [
                {"url": AUDI_A3_40_230718, "sourceDate": "2023-07-18", "reject": "future year vs MY22"},
                {"url": AUDI_A3_40_241014, "sourceDate": "2024-10-14", "reject": "future year + 25.7 kWh"},
            ],
        },
        "audi-a3-e-tron-ultra-phev-2016": {
            "reason": "US/EPA shell; battery nil; no EU WLTP battery package this pass",
            "consulted": [
                {
                    "url": "https://www.fueleconomy.gov/",
                    "reject": "EPA backs CS/CD/range — no official OEM battery kWh",
                },
            ],
        },
        "audi-q5-phev-50-tfsi-e-2023": {
            "reason": (
                "no MY2023-dated Q5 50 eTD; 2024-06-04 future-year; "
                "exact_homolog fails (weightedFuel 0.01579 vs 0.01593)"
            ),
            "consulted": [
                {
                    "url": AUDI_Q5_50_240604,
                    "sourceDate": "2024-06-04",
                    "reject": "future year; weightedFuel not identical",
                },
            ],
        },
        "mercedes-benz-gla-phev-250-e-2023": {
            "reason": (
                "CS/CD/range/battery nil: media.mercedes-benz.com 2023-03-16 GLA facelift press "
                "labels values vorläufig/provisional and Stromverbrauch gewichtet; "
                "dealer Preisliste ab 10.05.2023 (kunzmann) is not OEM media — discarded"
            ),
            "consulted": [
                {
                    "url": MB_GLA_202303,
                    "sourceDate": "2023-03-16",
                    "reject": (
                        "vorläufige Werte; Kraftstoff/Strom gewichtet; Nennkapazität Batterie 11,5 "
                        "without usable/net split; EAER provisional — not filled"
                    ),
                },
                {
                    "url": MB_GLA_DEALER_2023,
                    "sourceDate": "2023-05-10",
                    "reject": "dealer/partner PDF — not mercedes-benz.com / media OEM",
                },
            ],
        },
        "mercedes-benz-gle-coupe-phev-350-de-2022": {
            "reason": (
                "same sources as GLE SUV 2022: 2019 press too old; 2023 facelift presses wrong year / "
                "weighted-only — no MY22-dated OEM typenblatt with net battery + CS discharged + EAER"
            ),
            "consulted": [
                {
                    "url": MB_GLE_2019,
                    "sourceDate": "2019-09-09",
                    "reject": "sourceDate 2019 ≠ MY22",
                },
                {
                    "url": MB_GLE_202303,
                    "sourceDate": "2023-03-07",
                    "reject": "future year vs MY22",
                },
            ],
        },
        "mercedes-benz-gla-phev-250-e-2022": {
            "reason": (
                "CS/CD/range/battery nil: dealer Preisliste ab 01.02.2022 (autohaus-juergens) shows "
                "elektr. Reichweite 53–60 + Verbrauch/Strom gewichtet but is not OEM media; "
                "no MY22-dated media.mercedes-benz.com typenblatt with net battery + discharged CS verified"
            ),
            "consulted": [
                {
                    "url": MB_GLA_DEALER_2022,
                    "sourceDate": "2022-02-01",
                    "reject": (
                        "dealer PDF (aktualisiert 10.02.2022) — not official Mercedes media; "
                        "figures are gewichtet; battery kWh not clearly net-labeled"
                    ),
                },
                {
                    "url": MB_GLA_202303,
                    "sourceDate": "2023-03-16",
                    "reject": "future year vs MY22; provisional facelift values",
                },
                {
                    "url": "https://media.mercedes-benz.com/",
                    "reject": "media hub browsed — no MY22-dated GLA 250 e PDF attachment retrieved",
                },
            ],
        },
        "alfa-romeo-tonale-phev-2024": {
            "reason": "DE Jul-2024 Preisliste prices-only; IT listino HTTP 403",
            "consulted": [
                {
                    "url": (
                        "https://www.media.stellantis.com/uploads/de/model-document/"
                        "preislistemy24tonalejul_24_-668fc61a7e1ef.pdf"
                    ),
                    "sourceDate": "2024-07-01",
                    "reject": "price list without CS/EAER/battery table",
                },
                {
                    "url": (
                        "https://www.media.stellantis.com/uploads/it/model-pricelist/"
                        "listinoartonalemy24del1luglio2024-6686b7f7dea8f.pdf"
                    ),
                    "reject": "HTTP 403",
                },
            ],
        },
    }

    for rid in batch1_ids:
        if rid in newly_filled:
            continue
        row = by_id[rid]
        spec = nil_specs.get(rid) or {
            "reason": f"no valid dated OEM fill for {rid} in this correction pass",
            "consulted": [],
        }
        left_nil.append(
            nil_entry(
                row,
                reason=spec["reason"],
                consulted=spec.get("consulted") or [],
                field_reasons=spec.get("fieldReasons"),
            )
        )

    # Reclassify completed vs partial among lotto fills
    completed_out: list[dict] = []
    partial_out: list[dict] = []
    for p in partial:
        if p["id"] not in lotto and p["id"] not in by_id:
            continue
        row = by_id[p["id"]]
        miss = missing_calc_fields(row)
        p["stillMissing"] = miss
        if not miss:
            completed_out.append(p)
        else:
            partial_out.append(p)
    # extras completed from prev
    for e in completed:
        if e.get("id") not in {x["id"] for x in completed_out}:
            completed_out.append(e)

    partial = partial_out
    completed = completed_out

    # Ensure every batch1 id covered
    covered = (
        {e["id"] for e in completed}
        | {e["id"] for e in partial}
        | {e["id"] for e in homolog_reuse}
        | {e["id"] for e in left_nil}
    )
    for rid in batch1_ids:
        if rid not in covered:
            left_nil.append(
                nil_entry(
                    by_id[rid],
                    reason="missing from correction outcomes — added as nil",
                    consulted=[],
                )
            )

    # Invariants
    assert [r["id"] for r in seed] == ids_before
    for mid, blob in m3_before.items():
        now = json.dumps(by_id[mid], sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        if now != blob:
            raise SystemExit(f"Model 3 IT2026 mutated: {mid}")
    non_phev_after = tech_blob([r for r in seed if r.get("powertrain") != "phev"])
    non_phev_sha = hashlib.sha256(non_phev_after.encode()).hexdigest()
    if non_phev_sha != non_phev_sha_before:
        raise SystemExit(f"non-PHEV SHA drift: {non_phev_sha}")

    for oid, blob in outside_before.items():
        now = json.dumps(by_id[oid], sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        if now != blob:
            # allow confidence-only? We require identical for non-lotto
            raise SystemExit(f"non-lotto row mutated: {oid}")

    battery_convention = {
        "catalogConvention": "net/usable",
        "evidence": [
            "bmw-330e-phev-2024 batteryKWh=19.5 labeled usable energy",
            "bmw-x1-phev-xdrive25e-2023 batteryKWh=14.2 labeled Netto Batterieinhalt",
            "WeeklyChargeEstimator / catalog calc treat batteryKWh as usable pack energy",
        ],
        "thisPRAudi": "net (10.4 for Q3/A3 13.0 gross sheets; 14.4 for Q5 17.9 gross)",
        "existingViolationsNotFixed": [
            {
                "id": "bmw-x1-phev-xdrive25e-2022",
                "batteryKWh": 10.0,
                "note": "IT listino lorda/netta 10/8.82 → stored 10 (gross)",
            },
            {
                "id": "peugeot-3008-phev-2023",
                "batteryKWh": 14.2,
                "note": "UK Apr 2023 Battery Capacity MAX 14.2; Usable Battery Capacity 10.4 on same sheet",
            },
        ],
    }

    new_ver = 80
    cdn["seedVersion"] = new_ver
    cdn["prevSeedVersion"] = 79
    cdn["rows"] = len(seed)
    payload = json.dumps(seed, separators=(",", ":"), ensure_ascii=False)
    cdn["bytes"] = len(payload.encode())
    cdn["updatedAt"] = datetime.now(timezone.utc).isoformat()
    cdn["note"] = (
        "seedVersion 80: PHEV wave2 batch1 research corrections — Audi battery net/usable "
        "(10.4/14.4); Q3 SB 2023 homolog TAN/Va/Ve/ep; Peugeot 3008 2022 battery+EAER; "
        "honest nil reasons; require_year_token dating hygiene; api/static sync deferred at seed 77"
    )
    SEED.write_text(payload)
    CDN.write_text(json.dumps(cdn, indent=2) + "\n")
    if SEED.stat().st_size != cdn["bytes"]:
        raise SystemExit(
            f"CDN bytes {cdn['bytes']} != seed file {SEED.stat().st_size}"
        )

    extras = list(prev_man.get("extras") or [])
    man = {
        "seedVersion": new_ver,
        "prevSeedVersion": 79,
        "ids_before": ids_before,
        "batch1_ids": batch1_ids,
        "completed": [p for p in completed if p["id"] in lotto],
        "partial": [p for p in partial if p["id"] in lotto],
        "extras": extras,
        "homolog_reuse": [h for h in homolog_reuse if h["id"] in lotto],
        "left_nil": left_nil,
        "changed_fields": changed_fields,
        "battery_convention": battery_convention,
        "counts": {
            "completed": len([p for p in completed if p["id"] in lotto]),
            "partial": len([p for p in partial if p["id"] in lotto]),
            "left_nil": len(left_nil),
            "homolog_reuse": len([h for h in homolog_reuse if h["id"] in lotto]),
        },
        "non_phev_tech_sha": non_phev_sha,
        "m3_ids": sorted(m3_before),
        "sourceDay": SOURCE_DAY,
        "reviewNotes": [
            "CORRECTION: catalog batteryKWh convention = net/usable; Audi eTD gross→net "
            "(10.4 / 14.4) with explicit net label; CS/EAER/CD dates unchanged.",
            "Q3 SB 2023 homolog cites TAN E1*2007/46*1900*32 / Va SDGEAF1 / "
            "Ve FD6FD6DD002RT51A184BIAHA7EM90B3 / ep 110 + donor eTD 2024-03-14.",
            "Peugeot 3008 2022: FR tarif 2021-11-02 HYBRID 225 battery 13.2 + EAER 55; CS nil (ponderato).",
            "Existing convention violations reported only: bmw-x1-2022 gross 10; peugeot-3008-2023 Capacity 14.2 vs Usable 10.4.",
            "Nil reasons cite concrete OEM/archive URLs — no homepage-only claims.",
            "Checker: require_year_token now fails when homolog donor-year cite lacks year token; must-fail probe added.",
        ],
        "prKind": "research-correction",
    }
    MANIFEST.write_text(json.dumps(man, indent=2, ensure_ascii=False) + "\n")
    print(
        json.dumps(
            {
                "seedVersion": new_ver,
                "bytes": cdn["bytes"],
                "counts": man["counts"],
                "changed_fields": len(changed_fields),
                "battery_convention": battery_convention["catalogConvention"],
                "non_phev_tech_sha": non_phev_sha,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
