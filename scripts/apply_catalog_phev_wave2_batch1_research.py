#!/usr/bin/env python3
"""
PHEV wave2 batch1 RESEARCH (seed 78→79).

Official OEM fills only for the 40 left-nil lotto rows. Does not re-run the
restore/scrub pass from seed 77→78. Non-lotto rows stay byte-identical aside
from confidence finalize on touched PHEV rows.
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
    exact_homolog_ok,
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

# Official Audi MediaCenter eTD (Program for Germany Date on sheet).
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

CALC_FIELDS = (
    "fuelConsumptionLPerKm",
    "energyConsumptionKWhPerKm",
    "wltpRangeKm",
    "batteryKWh",
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


def fill_partial(
    row: dict,
    *,
    values: dict,
    cites: dict[str, tuple[str, str]],
    note: str,
    rejected: dict | None = None,
) -> dict:
    """Apply values + provenance; return partial/completed manifest entry."""
    for field, val in values.items():
        row[field] = val
    for field, (cite, date) in cites.items():
        set_field_source(row, field, cite, date)
    # Hygiene: non-EPA PHEVs with battery/range must cite an http doc URL in sourceName.
    urls = []
    for cite, _date in cites.values():
        urls.extend(urls_in(cite))
    url = next((u for u in urls if u.startswith("http")), None)
    if url:
        sn = row.get("sourceName") or ""
        if url not in sn:
            row["sourceName"] = f"{sn}; wave2-batch1-research {note} — {url}".strip("; ")
    row["sourceUpdatedAt"] = SOURCE_DAY
    finalize(row)
    miss = row["missingCalcFields"]
    entry = {
        "id": row["id"],
        "note": note,
        "filled": dict(values),
        "stillMissing": miss,
        "sources": {f: cites[f][0] for f in cites},
        "sourceDates": {f: cites[f][1] for f in cites},
    }
    if rejected:
        entry["rejected"] = rejected
    return entry


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
    return out


def main() -> None:
    seed = json.loads(SEED.read_text(encoding="utf-8"))
    by_id = {r["id"]: r for r in seed}
    ids_before = [r["id"] for r in seed]
    assert len(seed) == 6977

    cdn = json.loads(CDN.read_text(encoding="utf-8"))
    if int(cdn.get("seedVersion") or 0) != 78:
        raise SystemExit(f"expected seed 78 baseline, got {cdn.get('seedVersion')}")

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

    # Snapshot non-batch1 rows (full JSON) to enforce byte-identity after apply.
    non_batch_before = {
        r["id"]: json.dumps(r, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        for r in seed
        if r["id"] not in batch1_ids
    }

    completed: list[dict] = []
    partial: list[dict] = []
    homolog_reuse: list[dict] = []
    left_nil: list[dict] = []
    extras: list[dict] = list(prev_man.get("extras") or [])  # keep GC/330e notes historically

    # Carry forward prior partials that are NOT in the 40 nils (GC 2023, 330e).
    for p in prev_man.get("partial") or []:
        if p["id"] not in batch1_ids:
            partial.append(p)

    for h in prev_man.get("homolog_reuse") or []:
        if h["id"] not in batch1_ids:
            homolog_reuse.append(h)

    # --- Fills -----------------------------------------------------------------

    # 1) Q3 Sportback 45 TFSI e 2024 — eTD Date 03/14/24
    q3sb24 = by_id["audi-q3-sportback-phev-45-tfsi-e-2024"]
    q3sb24_cite = (
        "Audi MediaCenter eTD Q3 Sportback 45 TFSI e S tronic 110/180 kW "
        "Program for Germany Date: 03/14/24 — CS discharged battery combined "
        "MAX 7.2–6.6 L/100; EAER combined MIN 52–58 km; battery gross 13.0 kWh; "
        f"electric weighted-only (no pure CD label) {AUDI_Q3SB_45_240314}"
    )
    q3sb24_date = "2024-03-14"
    q3sb24.pop("dataDerivedFromSameHomologationYear", None)
    partial.append(
        fill_partial(
            q3sb24,
            values={
                "fuelConsumptionLPerKm": 0.072,
                "wltpRangeKm": 52,
                "batteryKWh": 13.0,
            },
            cites={
                "fuelConsumptionLPerKm": (q3sb24_cite, q3sb24_date),
                "wltpRangeKm": (q3sb24_cite, q3sb24_date),
                "batteryKWh": (q3sb24_cite, q3sb24_date),
            },
            note=(
                "Audi eTD 2024-03-14 Q3 Sportback 45 TFSI e: CS 7.2 (MAX), EAER 52 (MIN), "
                "battery 13.0 gross; pure CD nil (only weighted electric on sheet)"
            ),
            rejected={
                "energyConsumptionKWhPerKm": {
                    "reason": "sheet labels electric as weighted combined only — never derive pure CD",
                    "url": AUDI_Q3SB_45_240314,
                    "sourceDate": q3sb24_date,
                }
            },
        )
    )

    # 2) Q3 Sportback 45 TFSI e 2023 — exact homolog onto 2024 donor
    q3sb23 = by_id["audi-q3-sportback-phev-45-tfsi-e-2023"]
    if not exact_homolog_ok(q3sb23, q3sb24):
        raise SystemExit("Q3 SB 2023↔2024 exact homolog failed")
    q3sb23["dataDerivedFromSameHomologationYear"] = 2024
    q3sb23_cite = (
        "stessa omologazione EEA seed power+weighted WLTP identical 2023↔2024; "
        "donor Audi MediaCenter eTD Q3 Sportback 45 TFSI e Date: 03/14/24 "
        f"{AUDI_Q3SB_45_240314}"
    )
    q3sb23_vals = {
        "fuelConsumptionLPerKm": 0.072,
        "wltpRangeKm": 52,
        "batteryKWh": 13.0,
    }
    for field, val in q3sb23_vals.items():
        q3sb23[field] = val
        set_field_source(q3sb23, field, q3sb23_cite, q3sb24_date)
    sn23 = q3sb23.get("sourceName") or ""
    if AUDI_Q3SB_45_240314 not in sn23:
        q3sb23["sourceName"] = (
            f"{sn23}; wave2-batch1-research exact homolog 2023←2024 Q3 SB eTD — "
            f"{AUDI_Q3SB_45_240314}"
        ).strip("; ")
    q3sb23["sourceUpdatedAt"] = SOURCE_DAY
    finalize(q3sb23)
    homolog_reuse.append(
        {
            "id": q3sb23["id"],
            "sourceId": q3sb24["id"],
            "note": "exact homolog 2023←2024 Audi eTD for CS+EAER+battery",
            "filled": dict(q3sb23_vals),
            "stillMissing": q3sb23["missingCalcFields"],
            "sources": {f: q3sb23_cite for f in q3sb23_vals},
            "sourceDates": {f: q3sb24_date for f in q3sb23_vals},
        }
    )
    partial.append(homolog_reuse[-1])

    # 3) Q3 45 TFSI e 2024 (non-SB)
    q324 = by_id["audi-q3-phev-45-tfsi-e-2024"]
    q324_cite = (
        "Audi MediaCenter eTD Q3 45 TFSI e S tronic 110/180 kW "
        "Program for Germany Date: 03/14/24 — CS discharged MAX 7.3–6.5 L/100; "
        "EAER combined MIN 51–59 km; battery gross 13.0 kWh; "
        f"electric weighted-only {AUDI_Q3_45_240314}"
    )
    q324.pop("dataDerivedFromSameHomologationYear", None)
    partial.append(
        fill_partial(
            q324,
            values={
                "fuelConsumptionLPerKm": 0.073,
                "wltpRangeKm": 51,
                "batteryKWh": 13.0,
            },
            cites={
                "fuelConsumptionLPerKm": (q324_cite, q3sb24_date),
                "wltpRangeKm": (q324_cite, q3sb24_date),
                "batteryKWh": (q324_cite, q3sb24_date),
            },
            note=(
                "Audi eTD 2024-03-14 Q3 45 TFSI e: CS 7.3 (MAX), EAER 51 (MIN), battery 13.0; "
                "pure CD nil (weighted electric only)"
            ),
            rejected={
                "energyConsumptionKWhPerKm": {
                    "reason": "only weighted combined electric on eTD — no pure CD label",
                    "url": AUDI_Q3_45_240314,
                    "sourceDate": q3sb24_date,
                }
            },
        )
    )

    # 4) A3 45 TFSI e 2024
    a345 = by_id["audi-a3-phev-45-tfsi-e-2024"]
    a345_cite = (
        "Audi MediaCenter eTD A3 Sportback 45 TFSI e S tronic 180 kW (ICE 110) "
        "Program for Germany Date: 03/14/24 — CS discharged MAX 6.6–6.1 L/100; "
        "EAER combined MIN 64–58 km → 58; battery gross 13 kWh; "
        f"electric weighted-only {AUDI_A3_45_240314}"
    )
    a345.pop("dataDerivedFromSameHomologationYear", None)
    partial.append(
        fill_partial(
            a345,
            values={
                "fuelConsumptionLPerKm": 0.066,
                "wltpRangeKm": 58,
                "batteryKWh": 13.0,
            },
            cites={
                "fuelConsumptionLPerKm": (a345_cite, q3sb24_date),
                "wltpRangeKm": (a345_cite, q3sb24_date),
                "batteryKWh": (a345_cite, q3sb24_date),
            },
            note=(
                "Audi eTD 2024-03-14 A3 45 TFSI e: CS 6.6 (MAX), EAER 58 (MIN of 64–58), "
                "battery 13.0; pure CD nil"
            ),
            rejected={
                "energyConsumptionKWhPerKm": {
                    "reason": "only weighted combined electric on eTD",
                    "url": AUDI_A3_45_240314,
                    "sourceDate": q3sb24_date,
                }
            },
        )
    )

    # 5) A3 40 TFSI e 2023 — range+battery; CS unlabeled → reject as weighted
    a34023 = by_id["audi-a3-phev-40-tfsi-e-2023"]
    a34023_cite = (
        "Audi MediaCenter eTD A3 Sportback 40 TFSI e S tronic 150 kW "
        "Program for Germany Date: 07/18/23 — EAER combined MIN 66–58 km → 58; "
        "battery gross 13 kWh; fuel/electric labeled 'combined according to WLTP' "
        f"without discharged/pure marker → CS+CD nil {AUDI_A3_40_230718}"
    )
    a34023_date = "2023-07-18"
    a34023.pop("dataDerivedFromSameHomologationYear", None)
    partial.append(
        fill_partial(
            a34023,
            values={"wltpRangeKm": 58, "batteryKWh": 13.0},
            cites={
                "wltpRangeKm": (a34023_cite, a34023_date),
                "batteryKWh": (a34023_cite, a34023_date),
            },
            note=(
                "Audi eTD 2023-07-18 A3 40 TFSI e: EAER 58 (MIN), battery 13.0; "
                "CS/CD nil — WLTP combined unlabeled (treat as weighted)"
            ),
            rejected={
                "fuelConsumptionLPerKm": {
                    "reason": "Fuel consumption, combined according to WLTP unlabeled — not discharged-battery CS",
                    "url": AUDI_A3_40_230718,
                    "sourceDate": a34023_date,
                },
                "energyConsumptionKWhPerKm": {
                    "reason": "Electric power consumption, combined according to WLTP unlabeled — not pure CD",
                    "url": AUDI_A3_40_230718,
                    "sourceDate": a34023_date,
                },
            },
        )
    )

    # 6) Q5 50 TFSI e 2024
    q524 = by_id["audi-q5-phev-50-tfsi-e-2024"]
    q524_cite = (
        "Audi MediaCenter eTD Q5 50 TFSI e quattro S tronic 220 kW (ICE 195) "
        "Program for Germany Date: 06/04/24 — CS discharged MAX 8.7–8.0 L/100; "
        "EAER combined MIN 56–62 km; battery gross 17.9 kWh; "
        f"electric weighted-only {AUDI_Q5_50_240604}"
    )
    q524_date = "2024-06-04"
    q524.pop("dataDerivedFromSameHomologationYear", None)
    partial.append(
        fill_partial(
            q524,
            values={
                "fuelConsumptionLPerKm": 0.087,
                "wltpRangeKm": 56,
                "batteryKWh": 17.9,
            },
            cites={
                "fuelConsumptionLPerKm": (q524_cite, q524_date),
                "wltpRangeKm": (q524_cite, q524_date),
                "batteryKWh": (q524_cite, q524_date),
            },
            note=(
                "Audi eTD 2024-06-04 Q5 50 TFSI e: CS 8.7 (MAX), EAER 56 (MIN), battery 17.9; "
                "pure CD nil"
            ),
            rejected={
                "energyConsumptionKWhPerKm": {
                    "reason": "only weighted combined electric on eTD",
                    "url": AUDI_Q5_50_240604,
                    "sourceDate": q524_date,
                }
            },
        )
    )

    filled_ids = {p["id"] for p in partial} | {h["id"] for h in homolog_reuse}

    # --- Per-row nil reasons with consulted/rejected URLs -----------------------
    nil_specs: dict[str, dict] = {
        "jeep-compass-phev-4xe-2022": {
            "reason": (
                "CS/CD still nil: jeep.de/hybrid-suv generic landing rejected; "
                "2022↔2024 exact homolog blocked (weighted WLTP/power not identical)"
            ),
            "consulted": [
                {
                    "url": "https://www.jeep.de/hybrid-suv",
                    "reject": "generic /hybrid-suv range landing",
                },
                {
                    "url": "https://web.archive.org/web/20240620055110/https://www.jeep.de/hybrid-suv",
                    "reject": "archive of generic /hybrid-suv — still generic path",
                },
            ],
            "fieldReasons": {
                "fuelConsumptionLPerKm": "no dated MY22 OEM CS (discharged) label",
                "energyConsumptionKWhPerKm": "no dated MY22 pure-CD OEM label",
            },
        },
        "jeep-renegade-phev-4xe-2022": {
            "reason": (
                "CS/CD nil: jeep.de/hybrid-suv rejected; 2022↔2024 donor weighted WLTP not identical"
            ),
            "consulted": [
                {
                    "url": "https://www.jeep.de/hybrid-suv",
                    "reject": "generic /hybrid-suv",
                },
                {
                    "url": (
                        "https://www.media.stellantis.com/fr-fr/download-price-lists/184"
                    ),
                    "reject": "MY24 FR tarif endpoint — wrong model year for MY22",
                },
            ],
        },
        "cupra-formentor-phev-e-hybrid-2024": {
            "reason": (
                "CS+CD+EAER still nil: CUPRA IE Jan-2024 Product Guide has battery 12.8 "
                "(already filled) and weighted-only 1.2/1.5 L/100 — no discharged CS, "
                "no EAER combined, no pure CD"
            ),
            "consulted": [
                {
                    "url": (
                        "https://www.cupra.com/content/dam/countries/ie/cupra-website/"
                        "product-guide/formentor/cars-models-info-KM7-product-guide-Jan-2024.pdf"
                    ),
                    "sourceDate": "2024-01-01",
                    "reject_for": "CS/CD/EAER — only battery + weighted fuel present",
                },
                {
                    "url": (
                        "https://www.cupra.com/content/dam/public/cupra-website/generic/pdf/"
                        "cupra-formentor-catalogue-dic-2024.pdf"
                    ),
                    "reject": "Dec 2024 brochure shows facelift 25.8 kWh — wrong gen vs seed 12.8 / power 110.6",
                },
            ],
            "fieldReasons": {
                "fuelConsumptionLPerKm": "Jan 2024 guide lists only weighted 1.2–1.5 L/100 for e-Hybrid",
                "energyConsumptionKWhPerKm": "no pure-electric kWh label on Jan 2024 guide",
                "wltpRangeKm": "no EAER combined figure on Jan 2024 guide",
            },
        },
        "jeep-renegade-phev-4xe-2023": {
            "reason": "CD puro nil; CS hybrid-suv scrubbed; MY24 FR tarif has weighted fuel only",
            "consulted": [
                {
                    "url": "https://www.jeep.de/hybrid-suv",
                    "reject": "generic landing",
                },
                {
                    "url": (
                        "https://www.media.stellantis.com/uploads/fr/model-pricelist/"
                        "tarifpublicjeeprrenegademy242024c3avril2024-66334a53de22c.pdf"
                    ),
                    "sourceDate": "2024-04-03",
                    "reject": "MY24 dated — wrong year for MY23; fuel figures weighted/pondéré",
                },
            ],
        },
        "mini-countryman-cooper-se-all4-2023": {
            "reason": (
                "CS/CD/range/battery nil: MINI 2023-08-22 postcard labels combined = weighted; "
                "no discharged CS / pure CD / EAER combined"
            ),
            "consulted": [
                {
                    "url": "https://www.press.bmwgroup.com/",
                    "reject": "MINI Countryman SE ALL4 postcard 2023-08-22 — consumption labeled combined/weighted only",
                },
            ],
        },
        "volvo-xc40-phev-recharge-2022": {
            "reason": "no MY2022-dated Volvo XC40 PHEV OEM sheet with CS/CD/EAER/battery found",
            "consulted": [
                {
                    "url": "https://www.media.volvocars.com/",
                    "reject": "live media hub — undated continuous pages invalid for MY22",
                },
            ],
        },
        "cupra-formentor-phev-e-hybrid-2023": {
            "reason": (
                "CS/CD/range/battery nil: no MY23-dated CUPRA Formentor e-Hybrid OEM sheet; "
                "2023↔2024 exact homolog blocked (powerKw 110.0 vs 110.6)"
            ),
            "consulted": [
                {
                    "url": (
                        "https://www.cupra.com/content/dam/countries/ie/cupra-website/"
                        "product-guide/formentor/cars-models-info-KM7-product-guide-Jan-2024.pdf"
                    ),
                    "sourceDate": "2024-01-01",
                    "reject": "MY24-dated guide — future year vs MY23; homolog blocked by power mismatch",
                },
            ],
        },
        "volvo-xc40-phev-recharge-2023": {
            "reason": "no MY2023-dated Volvo XC40 PHEV OEM document with fillable CS/CD/EAER/battery",
            "consulted": [
                {
                    "url": "https://www.media.volvocars.com/",
                    "reject": "live undated media hub invalid for past MY",
                },
            ],
        },
        "volvo-xc60-phev-recharge-2024": {
            "reason": (
                "CD puro nil (CS/range/battery already present): Volvo 2024-06-01 press "
                "lists Stromverbrauch gewichtet only"
            ),
            "consulted": [
                {
                    "url": "https://www.media.volvocars.com/global/en-gb/media/pressreleases",
                    "reject": "XC60 Recharge press 2024-06-01 — electric labeled gewichtet/weighted",
                },
            ],
            "fieldReasons": {
                "energyConsumptionKWhPerKm": "only weighted electric kWh on dated press — never derive pure CD",
            },
        },
        "bmw-x1-phev-xdrive25e-2024": {
            "reason": "CD puro nil: BMW EnVKV / Nov 2023 listino shows Stromverbrauch gewichtet only",
            "consulted": [
                {
                    "url": (
                        "https://www.bmw.de/content/dam/bmw/marketDE/bmw_de/topics/price-list/"
                        "bmw-x1-preisliste.pdf"
                    ),
                    "reject": "live continuous listino path (no MY token) and/or weighted-only Strom",
                },
            ],
            "fieldReasons": {
                "energyConsumptionKWhPerKm": "weighted-only Strom on EnVKV — no charge-depleting label",
            },
        },
        "bmw-x1-phev-xdrive25e-2022": {
            "reason": "CS+CD nil: IT listino 2022-01-26 has range/battery already; no discharged CS / pure CD",
            "consulted": [
                {
                    "url": "scripts/cache/oem/bmw_x1_listino_it_20220126.pdf",
                    "sourceDate": "2022-01-26",
                    "reject_for": "CS/CD — no discharged-battery or rein-elektrisch labels verified",
                },
            ],
        },
        "jeep-renegade-phev-4xe-2024": {
            "reason": "CD puro nil; CS hybrid-suv scrubbed; MY24 FR tarif weighted/pondéré only",
            "consulted": [
                {
                    "url": (
                        "https://www.media.stellantis.com/uploads/fr/model-pricelist/"
                        "tarifpublicjeeprrenegademy242024c3avril2024-66334a53de22c.pdf"
                    ),
                    "sourceDate": "2024-04-03",
                    "reject": "pondéré/weighted fuel+electric — no pure CD / discharged CS",
                },
            ],
        },
        "alfa-romeo-tonale-phev-2023": {
            "reason": (
                "CS/CD/range/battery nil: Stellantis Tonale factsheets are price-only; "
                "PT press 2023-03-14 cites >80 km urbano (City EAER) — rejected; "
                "IT listino 403 from media.stellantis during research"
            ),
            "consulted": [
                {
                    "url": (
                        "https://www.media.stellantis.com/uploads/de/model-pricelist/"
                        "alfaromeotonalefactsheet202306-64df54f63a076.pdf"
                    ),
                    "sourceDate": "2023-06-01",
                    "reject": "price/overview factsheet — no WLTP CS/CD/EAER/battery table",
                },
                {
                    "url": (
                        "https://www.media.stellantis.com/pt-pt/alfa-romeo/press/"
                        "novo-alfa-romeo-tonale-hibrido-plug-in-q4-280cv-chega-a-portugal"
                    ),
                    "sourceDate": "2023-03-14",
                    "reject": "autonomia >80 km ciclo urbano = EAER City only; battery 15.5 not on a WLTP datasheet with CS",
                },
                {
                    "url": (
                        "https://www.media.stellantis.com/uploads/it/model-pricelist/"
                        "listinoartonalemy24-6544e1a3b2070.pdf"
                    ),
                    "reject": "HTTP 403 during research; filename MY24 / listino 01/11/2023 — if retrieved later, verify EAER combined vs City",
                },
            ],
        },
        "ford-kuga-phev-2022": {
            "reason": (
                "no MY2022-dated OEM typenblatt; continuous Technische_Daten_des_Ford_Kuga.pdf "
                "invalid for MY22; weightedFuel 0.01007 kept from EEA"
            ),
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
            "reason": (
                "CS/CD/range/battery nil: mercedes-benz.de/…/glc/overview.html is live continuous; "
                "2022 press cites EAER city only for GLC 300 de"
            ),
            "consulted": [
                {
                    "url": "https://www.mercedes-benz.de/passengercars/models/suv/glc/overview.html",
                    "reject": "live continuously updated model page — invalid as dated MY24 document",
                },
                {
                    "url": "https://media.mercedes-benz.com/article/795bffa0-830f-4df5-9bb8-bb8dae8f7e40",
                    "reject": "press table lists Reichweite E-Fahrt (EAER city) only — City rejected",
                },
            ],
        },
        "volvo-xc60-phev-recharge-2023": {
            "reason": "CD puro nil: no MY23-dated pure-electric kWh label after undated live-press scrub",
            "consulted": [
                {
                    "url": "https://www.media.volvocars.com/",
                    "reject": "live undated press reuse invalid for MY23 pure CD",
                },
            ],
            "fieldReasons": {
                "energyConsumptionKWhPerKm": "no dated pure-CD OEM cite for MY23",
            },
        },
        "toyota-c-hr-phev-2024": {
            "reason": (
                "CD puro nil: Toyota DE PL_07_24 lists Stromverbrauch gewichtet; "
                "CS/range/battery already present from prior wave"
            ),
            "consulted": [
                {
                    "url": (
                        "https://www.toyota.de/content/dam/toyota/nmsc/germany/pdf/"
                        "preislisten/PL_07_24.pdf"
                    ),
                    "sourceDate": "2024-07-01",
                    "reject": "Stromverbrauch gewichtet only — no pure CD",
                },
            ],
            "fieldReasons": {
                "energyConsumptionKWhPerKm": "weighted-only electric on PL_07_24",
            },
        },
        "peugeot-3008-phev-2022": {
            "reason": "no MY2022-dated Peugeot 3008 PHEV OEM sheet with CS/CD/EAER/battery",
            "consulted": [
                {
                    "url": "https://www.peugeot.co.uk/",
                    "reject": "live brand site — no MY22-dated PHEV typenblatt verified",
                },
            ],
        },
        "renault-captur-phev-e-tech-phev-2022": {
            "reason": "no MY2022-dated Renault Captur E-Tech OEM sheet with fillable fields",
            "consulted": [
                {
                    "url": "https://www.renault.de/",
                    "reject": "live brand site — no MY22-dated E-Tech PHEV datasheet verified",
                },
            ],
        },
        "bmw-x1-phev-xdrive25e-2023": {
            "reason": "CD puro nil: Nov 2023 EnVKV/preisliste Stromverbrauch gewichtet only",
            "consulted": [
                {
                    "url": "scripts/cache/oem/bmw_x1_preisliste_nov2023.pdf",
                    "sourceDate": "2023-11-01",
                    "reject": "Stromverbrauch gewichtet — no rein-elektrisch / charge-depleting label",
                },
            ],
            "fieldReasons": {
                "energyConsumptionKWhPerKm": "weighted-only Strom for MY23",
            },
        },
        "mercedes-benz-gle-phev-350-de-2022": {
            "reason": "no MY2022-dated Mercedes GLE 350 de OEM sheet with CS/CD/EAER/battery",
            "consulted": [
                {
                    "url": "https://media.mercedes-benz.com/",
                    "reject": "live media hub — no MY22-dated GLE 350 de typenblatt verified",
                },
            ],
        },
        "peugeot-3008-phev-2023": {
            "reason": "CS+CD nil: no dated Peugeot 3008 MY23 PHEV OEM sheet with discharged CS / pure CD",
            "consulted": [
                {
                    "url": "https://www.peugeot.fr/",
                    "reject": "live brand site — no MY23-dated PHEV datasheet verified",
                },
            ],
        },
        "mini-countryman-cooper-se-all4-2022": {
            "reason": "no MY2022-dated MINI Countryman SE ALL4 OEM sheet",
            "consulted": [
                {
                    "url": "https://www.press.bmwgroup.com/",
                    "reject": "no MY22-dated MINI PHEV postcard/typenblatt verified",
                },
            ],
        },
        "audi-q3-phev-45-tfsi-e-2023": {
            "reason": (
                "CS/CD/range/battery nil: 2024 eTD is future-year vs MY23; "
                "exact_homolog with 2024 seed row fails (weightedFuel 0.01506 vs 0.01415)"
            ),
            "consulted": [
                {
                    "url": AUDI_Q3_45_240314,
                    "sourceDate": "2024-03-14",
                    "reject": "document year 2024 > MY23; homolog blocked by weighted WLTP mismatch",
                },
            ],
        },
        "audi-q3-phev-45-tfsi-e-2022": {
            "reason": "no MY2022-dated Audi Q3 45 TFSI e eTD found; 2024 eTD future-year invalid",
            "consulted": [
                {
                    "url": AUDI_Q3_45_240314,
                    "sourceDate": "2024-03-14",
                    "reject": "future-year vs MY22",
                },
            ],
        },
        "audi-q3-sportback-phev-45-tfsi-e-2022": {
            "reason": "no MY2022-dated Q3 Sportback TFSI e eTD; 2024 eTD future-year; weightedFuel differs from 2024 donor",
            "consulted": [
                {
                    "url": AUDI_Q3SB_45_240314,
                    "sourceDate": "2024-03-14",
                    "reject": "future-year vs MY22; seed weightedFuel 0.01745 ≠ 2024 0.01481",
                },
            ],
        },
        "audi-a3-phev-40-tfsi-e-2024": {
            "reason": (
                "CS/CD/range/battery nil: Oct-2024 eTD is 25.7 kWh facelift (weighted ~0.4 L/100) "
                "— wrong gen vs seed weightedFuel 0.01192 / old 13 kWh; "
                "no 2024-dated 13 kWh A3 40 sheet found; 2023 eTD wrong year without homolog"
            ),
            "consulted": [
                {
                    "url": AUDI_A3_40_241014,
                    "sourceDate": "2024-10-14",
                    "reject": "25.7/19.7 kWh facelift — does not match seed weighted 0.01192 (old gen)",
                },
                {
                    "url": AUDI_A3_40_230718,
                    "sourceDate": "2023-07-18",
                    "reject": "MY23-dated sheet; exact_homolog 2024↔2023 fails (weightedFuel differs)",
                },
            ],
        },
        "audi-a3-phev-40-tfsi-e-2022": {
            "reason": "no MY2022-dated A3 40 TFSI e eTD; 2023/2024 sheets wrong year / wrong gen",
            "consulted": [
                {
                    "url": AUDI_A3_40_230718,
                    "sourceDate": "2023-07-18",
                    "reject": "future year vs MY22",
                },
                {
                    "url": AUDI_A3_40_241014,
                    "sourceDate": "2024-10-14",
                    "reject": "future year + 25.7 kWh facelift",
                },
            ],
        },
        "audi-a3-e-tron-ultra-phev-2016": {
            "reason": "US/EPA shell; battery nil; no EU WLTP package researched this pass",
            "consulted": [
                {
                    "url": "https://www.fueleconomy.gov/",
                    "reject": "EPA already backs CS/CD/range — no official battery kWh on EU OEM sheet found",
                },
            ],
            "fieldReasons": {
                "batteryKWh": "no official OEM battery capacity for this US/EPA shell",
            },
        },
        "audi-q5-phev-50-tfsi-e-2023": {
            "reason": (
                "no MY2023-dated Q5 50 TFSI e eTD; 2024-06-04 sheet future-year; "
                "exact_homolog 2023↔2024 fails (weightedFuel 0.01579 vs 0.01593)"
            ),
            "consulted": [
                {
                    "url": AUDI_Q5_50_240604,
                    "sourceDate": "2024-06-04",
                    "reject": "future year vs MY23; weightedFuel not identical for homolog",
                },
            ],
        },
        "mercedes-benz-gla-phev-250-e-2023": {
            "reason": "no MY2023-dated Mercedes GLA 250 e OEM sheet",
            "consulted": [
                {
                    "url": "https://media.mercedes-benz.com/",
                    "reject": "live hub — no MY23-dated GLA 250 e typenblatt verified",
                },
            ],
        },
        "mercedes-benz-gle-coupe-phev-350-de-2022": {
            "reason": "no MY2022-dated GLE Coupé 350 de OEM sheet",
            "consulted": [
                {
                    "url": "https://media.mercedes-benz.com/",
                    "reject": "live hub — no MY22-dated GLE Coupé 350 de typenblatt verified",
                },
            ],
        },
        "mercedes-benz-gla-phev-250-e-2022": {
            "reason": "no MY2022-dated Mercedes GLA 250 e OEM sheet",
            "consulted": [
                {
                    "url": "https://media.mercedes-benz.com/",
                    "reject": "live hub — no MY22-dated GLA 250 e typenblatt verified",
                },
            ],
        },
        "alfa-romeo-tonale-phev-2024": {
            "reason": (
                "CS/CD/range/battery nil: DE Jul-2024 Preisliste is prices-only; "
                "IT listino HTTP 403; no WLTP CS/EAER/battery table retrieved"
            ),
            "consulted": [
                {
                    "url": (
                        "https://www.media.stellantis.com/uploads/de/model-document/"
                        "preislistemy24tonalejul_24_-668fc61a7e1ef.pdf"
                    ),
                    "sourceDate": "2024-07-01",
                    "reject": "price list without discharged CS / EAER combined / battery kWh table",
                },
                {
                    "url": (
                        "https://www.media.stellantis.com/uploads/it/model-pricelist/"
                        "listinoartonalemy24del1luglio2024-6686b7f7dea8f.pdf"
                    ),
                    "reject": "HTTP 403 during research",
                },
            ],
        },
    }

    for rid in batch1_ids:
        if rid in filled_ids:
            continue
        row = by_id[rid]
        spec = nil_specs.get(rid) or {
            "reason": f"no valid dated OEM fill for {rid} in this research pass",
            "consulted": [],
        }
        entry = nil_entry(
            row,
            reason=spec["reason"],
            consulted=spec.get("consulted") or [],
            field_reasons=spec.get("fieldReasons"),
        )
        already = {f: row.get(f) for f in CALC_FIELDS if row.get(f) is not None}
        if already:
            entry["alreadyPresent"] = already
        left_nil.append(entry)

    # Classify completed vs partial among new fills
    completed = []
    partial_out = []
    for p in partial:
        row = by_id[p["id"]]
        miss = missing_calc_fields(row)
        p["stillMissing"] = miss
        if not miss:
            completed.append(p)
        else:
            partial_out.append(p)
    partial = partial_out

    # Invariants
    if [r["id"] for r in seed] != ids_before:
        raise SystemExit("id list changed")
    for mid, blob in m3_before.items():
        now = json.dumps(by_id[mid], sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        if now != blob:
            raise SystemExit(f"M3 altered {mid}")
    non_phev_after = tech_blob([r for r in seed if r.get("powertrain") != "phev"])
    non_phev_sha_after = hashlib.sha256(non_phev_after.encode()).hexdigest()
    if non_phev_sha_after != non_phev_sha_before:
        raise SystemExit("non-PHEV tech blob changed")

    for rid, blob in non_batch_before.items():
        now = json.dumps(by_id[rid], sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        if now != blob:
            # Allow confidence-only drift? User said all other seed rows byte-identical.
            # GC/330e are non-batch1 — must stay identical.
            raise SystemExit(f"non-batch1 row changed: {rid}")

    new_ver = 79
    cdn["seedVersion"] = new_ver
    cdn["rows"] = len(seed)
    payload = json.dumps(seed, separators=(",", ":"), ensure_ascii=False)
    cdn["bytes"] = len(payload.encode())
    cdn["updatedAt"] = datetime.now(timezone.utc).isoformat()
    cdn["note"] = (
        "seedVersion 79: PHEV wave2 batch1 research — Audi Q3/Q3 SB/A3/Q5 official eTD "
        "partial fills; remaining lotto rows stay nil with consulted/rejected OEM URLs; "
        "confidence policy v2 unchanged; api/static sync deferred at seed 77"
    )

    SEED.write_text(payload)
    CDN.write_text(json.dumps(cdn, indent=2) + "\n")

    man = {
        "seedVersion": new_ver,
        "prevSeedVersion": 78,
        "ids_before": ids_before,
        "batch1_ids": batch1_ids,
        "completed": completed,
        "partial": partial,
        "extras": extras,
        "homolog_reuse": homolog_reuse,
        "left_nil": left_nil,
        "non_phev_tech_sha": non_phev_sha_after,
        "m3_ids": sorted(m3_before),
        "sourceDay": SOURCE_DAY,
        "reviewNotes": [
            "RESEARCH PR — official Audi MediaCenter eTD fills for Q3 SB 2024 (+homolog 2023), "
            "Q3 2024, A3 45 2024, A3 40 2023 (range+battery), Q5 50 2024.",
            "Pure CD never filled from weighted electric on any sheet.",
            "A3 40 2024 left nil: Oct-2024 25.7 kWh facelift ≠ seed weighted 0.01192 old gen.",
            "Q3/Q5 2023 left nil where exact homolog fails or only future-year eTD available.",
            "Non-batch1 seed rows byte-identical to seed 78; api/ untouched.",
        ],
        "prKind": "research",
    }
    MANIFEST.write_text(json.dumps(man, indent=2, ensure_ascii=False) + "\n")
    print(
        json.dumps(
            {
                "seedVersion": new_ver,
                "completed": len(completed),
                "partial": len(partial),
                "left_nil": len(left_nil),
                "homolog_reuse": len(homolog_reuse),
                "non_phev_tech_sha": non_phev_sha_after,
                "bytes": cdn["bytes"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    # Fix invalid walrus import hack if any — ensure clean imports only
    main()
