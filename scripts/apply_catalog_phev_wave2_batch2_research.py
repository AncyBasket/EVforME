#!/usr/bin/env python3
"""
PHEV wave2 batch2 RESEARCH (seed 83→84).

Official OEM fills for batch2_candidates (40). Non-lotto rows byte-identical.
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
from check_catalog_phev_wave2_batch1 import cite_dating_ok, is_generic_url, urls_in  # noqa: E402
from lib.phev_manus_v76_validate import missing_calc_fields  # noqa: E402

SEED = REPO / "EVforME?" / "Data" / "vehicles.seed.quality.json"
CDN = REPO / "EVforME?" / "Data" / "catalog_cdn.json"
CACHE = REPO / "scripts" / "cache" / "eea"
INVENTORY = CACHE / "catalog_phev_wave2_batch2_inventory.json"
MANIFEST = CACHE / "catalog_phev_wave2_batch2_manifest.json"
RESEARCH = CACHE / "catalog_phev_wave2_batch2_research.json"
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
BMW_X1_NOV23 = "https://www.press.bmwgroup.com/deutschland/article/attachment/T0322775DE/609585"
BMW_AT_NOV23 = "https://cdn.mportal.de/CDN/pdf/U06-11-2023.PDF"
BMW_X3_JUN24 = "https://www.press.bmwgroup.com/greece/article/attachment/T0443191EL/618258"
COMPASS_TARIF_DEC23 = (
    "https://www.media.stellantis.com/uploads/fr/attachment/7783/"
    "tarifpublicjeeprcompassmy242023e19decembre2023-65820ebe62db4.pdf"
)
GC_JAN23 = (
    "https://www.media.stellantis.com/uploads/de/model-pricelist/"
    "preisliste_grand_cherokee_4xe_januar_20234-6486c171a11d8.pdf"
)


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
        raise SystemExit(f"dating rejected {row['id']}.{field}: {date}")
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
    if text not in sn:
        row["sourceName"] = f"{sn}; {text}".strip("; ")


def main() -> None:
    seed = json.loads(SEED.read_text(encoding="utf-8"))
    by_id = {r["id"]: r for r in seed}
    ids_before = [r["id"] for r in seed]
    assert len(seed) == 6977

    cdn = json.loads(CDN.read_text(encoding="utf-8"))
    if int(cdn.get("seedVersion") or 0) != 83:
        raise SystemExit(f"expected seed 83 baseline, got {cdn.get('seedVersion')}")

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
    batch2 = inv["batch2_candidates"]
    batch2_ids = [x["id"] for x in batch2]
    assert len(batch2_ids) == 40
    lotto = set(batch2_ids)
    outside_before = {
        r["id"]: json.dumps(r, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        for r in seed
        if r["id"] not in lotto
    }

    changed_fields: list[dict] = []
    partial: list[dict] = []
    completed: list[dict] = []
    homolog_reuse: list[dict] = []
    left_nil: list[dict] = []

    def record_fill(rid: str, field: str, value, url: str, source_date: str, **extra) -> None:
        changed_fields.append(
            {"id": rid, "field": field, "value": value, "url": url, "sourceDate": source_date, **extra}
        )

    # --- Audi Q5 Sportback 50 TFSI e 2024 -------------------------------------------------
    q5 = by_id["audi-q5-sportback-phev-50-tfsi-e-2024"]
    cite = (
        f"Audi MediaCenter eTD Q5 Sportback 50 TFSI e quattro S tronic 220 kW "
        f"Program for Germany Date: 06/04/24 — CS discharged MAX 8.8–8.1 → 0.088; "
        f"EAER combined MIN 57–62 → 57; battery net/usable 14.4 (gross 17.9); "
        f"electric kWh weighted only → pure CD nil {AUDI_Q5SB}"
    )
    set_field(q5, "fuelConsumptionLPerKm", 0.088, cite, "2024-06-04")
    set_field(q5, "wltpRangeKm", 57, cite, "2024-06-04")
    set_field(q5, "batteryKWh", 14.4, cite.replace("CS discharged", "battery net"), "2024-06-04")
    append_source(q5, f"wave2-batch2 Audi eTD Q5 SB 50 TFSI e 2024-06-04 net 14.4 / EAER 57 / CS 0.088 — {AUDI_Q5SB}")
    q5["sourceUpdatedAt"] = SOURCE_DAY
    finalize(q5)
    for f, v in [("fuelConsumptionLPerKm", 0.088), ("wltpRangeKm", 57), ("batteryKWh", 14.4)]:
        record_fill(q5["id"], f, v, AUDI_Q5SB, "2024-06-04", variant="50 TFSI e 220 kW")
    partial.append(
        {
            "id": q5["id"],
            "filled": {
                "fuelConsumptionLPerKm": 0.088,
                "wltpRangeKm": 57,
                "batteryKWh": 14.4,
            },
            "left_nil": ["energyConsumptionKWhPerKm"],
            "note": "pure CD nil — eTD electric consumption is weighted combined only",
        }
    )

    # --- BMW X1 xDrive30e 2023 ------------------------------------------------------------
    x1 = by_id["bmw-x1-phev-xdrive30e-2023"]
    cite = (
        "press.bmwgroup.com BMW X1 Preisliste November 2023 (Ausgabe 1, 27.09.2023) — "
        "xDrive30e column: Netto Batterieinhalt 14,2; Elektrische Reichweite kombiniert "
        f"71–85 → MIN 71; CS/CD weighted-only → nil {BMW_X1_NOV23}"
    )
    set_field(x1, "batteryKWh", 14.2, cite, "2023-09-27")
    set_field(x1, "wltpRangeKm", 71, cite, "2023-09-27")
    append_source(x1, f"wave2-batch2 X1 30e Nov 2023 listino netta 14.2 / EAER 71 — {BMW_X1_NOV23}")
    x1["sourceUpdatedAt"] = SOURCE_DAY
    finalize(x1)
    record_fill(x1["id"], "batteryKWh", 14.2, BMW_X1_NOV23, "2023-09-27", variant="xDrive30e")
    record_fill(x1["id"], "wltpRangeKm", 71, BMW_X1_NOV23, "2023-09-27", variant="xDrive30e")
    partial.append(
        {
            "id": x1["id"],
            "filled": {"batteryKWh": 14.2, "wltpRangeKm": 71},
            "left_nil": ["fuelConsumptionLPerKm", "energyConsumptionKWhPerKm"],
            "note": "listino Verbrauch/Stromverbrauch next to CO2 gewichtet",
        }
    )

    # --- BMW 2er Active Tourer 225e 2023 --------------------------------------------------
    at = by_id["bmw-serie-2-active-tourer-225e-xdrive-2023"]
    cite = (
        "BMW Preisliste 2er Active Tourer (U06) Ausgabe 1, 27.09.2023 — 225e xDrive: "
        "Netto Batterieinhalt 14,2; Elektrische Reichweite kombiniert 78–88 → MIN 78; "
        f"Verbrauch kombiniert gewichtet only → CS/CD nil {BMW_AT_NOV23}"
    )
    set_field(at, "batteryKWh", 14.2, cite, "2023-09-27")
    set_field(at, "wltpRangeKm", 78, cite, "2023-09-27")
    append_source(at, f"wave2-batch2 Active Tourer 225e Nov 2023 netta 14.2 / EAER 78 — {BMW_AT_NOV23}")
    at["sourceUpdatedAt"] = SOURCE_DAY
    finalize(at)
    record_fill(at["id"], "batteryKWh", 14.2, BMW_AT_NOV23, "2023-09-27", variant="225e xDrive")
    record_fill(at["id"], "wltpRangeKm", 78, BMW_AT_NOV23, "2023-09-27", variant="225e xDrive")
    partial.append(
        {
            "id": at["id"],
            "filled": {"batteryKWh": 14.2, "wltpRangeKm": 78},
            "left_nil": ["fuelConsumptionLPerKm", "energyConsumptionKWhPerKm"],
            "note": "gewichtet fuel/electric only on Preisliste",
        }
    )

    # --- BMW X3 xDrive30e 2024 ------------------------------------------------------------
    x3 = by_id["bmw-x3-phev-xdrive30e-2024"]
    cite = (
        "press.bmwgroup.com BMW Media information 06/2024 — Technical specifications "
        "BMW X3 30e xDrive: Energy capacity (net) 19.7 kWh; Electric range (WLTP) 81–90 → MIN 81; "
        f"Fuel consump. weighted only → CS/CD nil {BMW_X3_JUN24}"
    )
    set_field(x3, "batteryKWh", 19.7, cite, "2024-06-01")
    set_field(x3, "wltpRangeKm", 81, cite, "2024-06-01")
    append_source(x3, f"wave2-batch2 X3 30e Media 06/2024 net 19.7 / EAER 81 — {BMW_X3_JUN24}")
    x3["sourceUpdatedAt"] = SOURCE_DAY
    finalize(x3)
    record_fill(x3["id"], "batteryKWh", 19.7, BMW_X3_JUN24, "2024-06-01", variant="X3 30e xDrive")
    record_fill(x3["id"], "wltpRangeKm", 81, BMW_X3_JUN24, "2024-06-01", variant="X3 30e xDrive")
    partial.append(
        {
            "id": x3["id"],
            "filled": {"batteryKWh": 19.7, "wltpRangeKm": 81},
            "left_nil": ["fuelConsumptionLPerKm", "energyConsumptionKWhPerKm"],
            "note": "tech specs sheet has weighted fuel only",
        }
    )

    filled_ids = {e["id"] for e in partial}

    # --- Honest nils for remaining batch2 -------------------------------------------------
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
                "bmw.de live Preisliste continuous — rejected for past/current MY dating. "
                "Dealer Juli 2024 PDFs are not OEM."
            ),
            "consulted": [
                {
                    "url": BMW_AT_NOV23,
                    "sourceDate": "2023-09-27",
                    "reject_for": "2023 document cannot date MY2024",
                },
                {
                    "url": "https://www.bmw.de/de/neufahrzeuge/2er/2-series-active-tourer/bmw-2er-active-tourer.html",
                    "sourceDate": "",
                    "reject_for": "live continuous OEM landing / undated download",
                },
            ],
        },
        "bmw-serie-2-active-tourer-225e-xdrive-2022": {
            "reason": (
                "IT listino 26.01.2022 (press T0321051IT) covers ICE trims in retrieved text; "
                "no Netto Batterieinhalt / EAER for 225e extracted from that sheet. "
                "Nov 2023 Preisliste is future-year vs MY2022."
            ),
            "consulted": [
                {
                    "url": "https://www.press.bmwgroup.com/italy/article/attachment/T0321051IT/520142",
                    "sourceDate": "2022-01-26",
                    "reject_for": "no labeled net battery / EAER for 225e on retrieved sheet",
                },
                {
                    "url": BMW_AT_NOV23,
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
                "Nov 2023 X1 Preisliste is calendar-2023 — cannot date MY2024. "
                "weightedFuel 0.00782 (2024) ≠ 0.00785 (2023) → exact_homolog_ok fails; "
                "no best_shared_exact reuse."
            ),
            "consulted": [
                {
                    "url": BMW_X1_NOV23,
                    "sourceDate": "2023-09-27",
                    "reject_for": "2023 listino ≠ MY2024; weighted fuel mismatch blocks homolog",
                }
            ],
        },
        "bmw-x2-phev-xdrive25e-2023": {
            "reason": "No MY2023 OEM listino with Netto/EAER for X2 xDrive25e verified (X1 sheet is different model).",
            "consulted": [
                {
                    "url": BMW_X1_NOV23,
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
            "reason": "X3 30e Media information 06/2024 is future-year vs MY2023; no MY2023 OEM tech sheet verified.",
            "consulted": [
                {
                    "url": BMW_X3_JUN24,
                    "sourceDate": "2024-06-01",
                    "reject_for": "2024 media sheet ≠ MY2023",
                }
            ],
        },
        "bmw-x3-phev-xdrive30e-2022": {
            "reason": "No MY2022 OEM tech sheet with net/EAER for X3 xDrive30e verified.",
            "consulted": [
                {
                    "url": BMW_X3_JUN24,
                    "sourceDate": "2024-06-01",
                    "reject_for": "2024 media sheet ≠ MY2022",
                }
            ],
        },
        "bmw-x5-phev-xdrive50e-2024": {
            "reason": (
                "Press texts cite nutzbar 25.7 kWh / EAER 94–110 for X5 50e but attached "
                "OEM PDF with printable Program/Date line not retrieved in this pass "
                "(press HTML wall). No fill without dated attachment."
            ),
            "consulted": [
                {
                    "url": "https://www.press.bmwgroup.com/austria/article/detail/T0411958DE/der-neue-bmw-x5-und-der-neue-bmw-x6",
                    "sourceDate": "2023-02-08",
                    "reject_for": "article date 2023 ≠ MY2024; no dated tech PDF attachment captured",
                }
            ],
        },
        "bmw-i3s-with-range-extender-phev-2021": {
            "reason": "Range alreadyPresent; no 2021 OEM sheet with labeled net/usable battery verified (gross-only sources rejected).",
            "consulted": [
                {
                    "url": "https://www.press.bmwgroup.com/global",
                    "sourceDate": "",
                    "reject_for": "generic press landing — no MY2021 net-labeled battery PDF found",
                }
            ],
        },
        "byd-seal-u-phev-dm-i-2024": {
            "reason": "No EU/IT OEM dated tech sheet with net battery / EAER combined / CS discharged for Seal U DM-i 2024 verified.",
            "consulted": [
                {
                    "url": "https://www.byd.com/",
                    "sourceDate": "",
                    "reject_for": "generic OEM homepage",
                }
            ],
        },
        "cupra-formentor-phev-vz-e-hybrid-2023": {
            "reason": (
                "JANUARY 2024 Product Guide (battery 12.8) is calendar-2024 — invalid for MY2023. "
                "No MY2023-dated CUPRA guide with VZ e-Hybrid column verified."
            ),
            "consulted": [
                {
                    "url": "https://www.cupraofficial.com/",
                    "sourceDate": "2024-01-01",
                    "reject_for": "2024 product guide dating ≠ MY2023; landing generic",
                }
            ],
        },
        "cupra-formentor-phev-e-hybrid-2022": {
            "reason": "No MY2022-dated CUPRA Product Guide with e-Hybrid net/EAER/CS verified.",
            "consulted": [
                {
                    "url": "https://www.cupraofficial.com/",
                    "sourceDate": "",
                    "reject_for": "generic OEM landing",
                }
            ],
        },
        "chevrolet-volt-phev-2019": {
            "reason": "US-market Volt; no EU OEM MY2019 net-battery sheet. Range alreadyPresent; battery stays nil.",
            "consulted": [
                {
                    "url": "https://www.chevrolet.com/",
                    "sourceDate": "",
                    "reject_for": "generic US OEM landing / market mismatch for IT seed",
                }
            ],
        },
        "citroen-c5-aircross-phev-2023": {
            "reason": "No MY2023 Stellantis/Citroën dated listino with usable battery / EAER / CS discharged verified.",
            "consulted": [
                {
                    "url": "https://www.media.stellantis.com/",
                    "sourceDate": "",
                    "reject_for": "media hub landing — no dated C5 Aircross PHEV sheet captured",
                }
            ],
        },
        "citroen-c5-aircross-phev-2022": {
            "reason": "No MY2022 OEM dated C5 Aircross PHEV tech/listino with net/EAER/CS verified.",
            "consulted": [
                {
                    "url": "https://www.media.stellantis.com/",
                    "sourceDate": "",
                    "reject_for": "media hub landing",
                }
            ],
        },
        "ds-7-phev-e-tense-2024": {
            "reason": "No MY2024 DS Automobiles OEM dated e-TENSE sheet with net/EAER/CS verified.",
            "consulted": [
                {
                    "url": "https://www.media.stellantis.com/",
                    "sourceDate": "",
                    "reject_for": "media hub landing",
                }
            ],
        },
        "ds-7-phev-e-tense-2023": {
            "reason": "No MY2023 DS e-TENSE OEM dated sheet verified.",
            "consulted": [
                {
                    "url": "https://www.media.stellantis.com/",
                    "sourceDate": "",
                    "reject_for": "media hub landing",
                }
            ],
        },
        "ds-7-phev-e-tense-2022": {
            "reason": "No MY2022 DS e-TENSE OEM dated sheet verified.",
            "consulted": [
                {
                    "url": "https://www.media.stellantis.com/",
                    "sourceDate": "",
                    "reject_for": "media hub landing",
                }
            ],
        },
        "ford-c-max-energi-plug-in-hybrid-phev-2016": {
            "reason": "US Energi model; no EU OEM MY2016 net-battery sheet. Range alreadyPresent.",
            "consulted": [
                {
                    "url": "https://www.ford.com/",
                    "sourceDate": "",
                    "reject_for": "generic US OEM landing",
                }
            ],
        },
        "ford-escape-fwd-phev-phev-2026": {
            "reason": "No EU/IT OEM Escape PHEV 2026 datasheet with net battery verified (US Escape ≠ EU Kuga naming).",
            "consulted": [
                {
                    "url": "https://www.ford.com/",
                    "sourceDate": "",
                    "reject_for": "generic OEM landing / market naming mismatch",
                }
            ],
        },
        "honda-accord-phev-2014": {
            "reason": "No EU OEM MY2014 Accord PHEV net-battery sheet. Range alreadyPresent.",
            "consulted": [
                {
                    "url": "https://www.honda.com/",
                    "sourceDate": "",
                    "reject_for": "generic OEM landing",
                }
            ],
        },
        "hyundai-ioniq-phev-2022": {
            "reason": "Range alreadyPresent; no MY2022 Hyundai OEM EU sheet with labeled usable/net battery verified.",
            "consulted": [
                {
                    "url": "https://www.hyundai.com/eu/en.html",
                    "sourceDate": "",
                    "reject_for": "generic EU landing",
                }
            ],
        },
        "hyundai-tucson-phev-2024": {
            "reason": "No MY2024 Hyundai OEM EU dated tech/listino with net/EAER/CS discharged verified.",
            "consulted": [
                {
                    "url": "https://www.hyundai.com/eu/en.html",
                    "sourceDate": "",
                    "reject_for": "generic EU landing",
                }
            ],
        },
        "hyundai-tucson-phev-2023": {
            "reason": "No MY2023 Hyundai OEM EU dated Tucson PHEV sheet verified.",
            "consulted": [
                {
                    "url": "https://www.hyundai.com/eu/en.html",
                    "sourceDate": "",
                    "reject_for": "generic EU landing",
                }
            ],
        },
        "hyundai-tucson-phev-2022": {
            "reason": "No MY2022 Hyundai OEM EU dated Tucson PHEV sheet verified.",
            "consulted": [
                {
                    "url": "https://www.hyundai.com/eu/en.html",
                    "sourceDate": "",
                    "reject_for": "generic EU landing",
                }
            ],
        },
        "jeep-compass-phev-4xe-2023": {
            "reason": (
                "Battery+EAER alreadyPresent. Pure CD nil: no OEM cite with rein-elektrisch / "
                "pure-CD label for MY2023 (weighted EEA energy stays in weighted*)."
            ),
            "consulted": [
                {
                    "url": COMPASS_TARIF_DEC23,
                    "sourceDate": "2023-12-19",
                    "reject_for": "tarif shows autonomy/CO2 pondérés — not pure CD kWh; also MY24 packaging",
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
                    "url": COMPASS_TARIF_DEC23,
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
                "Battery+EAER alreadyPresent from prior wave. Pure CD nil. "
                "MJ23 DE listino is 2023 — cannot newly date MY2024; weighted EEA unchanged."
            ),
            "consulted": [
                {
                    "url": GC_JAN23,
                    "sourceDate": "2023-01-01",
                    "reject_for": "2023 listino ≠ MY2024 for new fills; no pure-CD label",
                }
            ],
            "field_reasons": {
                "energyConsumptionKWhPerKm": "no pure-CD label on GC listino",
            },
        },
        "jeep-wrangler-4xe-2024": {
            "reason": "No MY2024 OEM Wrangler 4xe dated listino with net/EAER/CS verified.",
            "consulted": [
                {
                    "url": "https://www.media.stellantis.com/",
                    "sourceDate": "",
                    "reject_for": "media hub landing",
                }
            ],
        },
        "jeep-wrangler-4xe-2023": {
            "reason": "No MY2023 OEM Wrangler 4xe dated listino with net/EAER/CS verified.",
            "consulted": [
                {
                    "url": "https://www.media.stellantis.com/",
                    "sourceDate": "",
                    "reject_for": "media hub landing",
                }
            ],
        },
        "jeep-wrangler-4xe-2022": {
            "reason": "Battery alreadyPresent; no MY2022 OEM sheet with EAER combined / pure CD verified.",
            "consulted": [
                {
                    "url": "https://www.media.stellantis.com/",
                    "sourceDate": "",
                    "reject_for": "media hub landing",
                }
            ],
        },
        "kia-sportage-phev-2024": {
            "reason": "No MY2024 Kia OEM EU dated Sportage PHEV sheet with net/EAER/CS verified.",
            "consulted": [
                {
                    "url": "https://www.kia.com/",
                    "sourceDate": "",
                    "reject_for": "generic OEM landing",
                }
            ],
        },
        "kia-sportage-phev-2023": {
            "reason": "No MY2023 Kia OEM EU dated Sportage PHEV sheet verified.",
            "consulted": [
                {
                    "url": "https://www.kia.com/",
                    "sourceDate": "",
                    "reject_for": "generic OEM landing",
                }
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
        finalize(row)  # confidence only; no field mutation for pure nils
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
                "note": "eTD Gross/net 17.9/14.4 → store net 14.4",
            },
            {
                "id": "bmw-x1-phev-xdrive30e-2023",
                "batteryKWh": 14.2,
                "note": "Netto Batterieinhalt 14,2 on Nov 2023 Preisliste",
            },
            {
                "id": "bmw-serie-2-active-tourer-225e-xdrive-2023",
                "batteryKWh": 14.2,
                "note": "Netto Batterieinhalt 14,2 on U06 Nov 2023 Preisliste",
            },
            {
                "id": "bmw-x3-phev-xdrive30e-2024",
                "batteryKWh": 19.7,
                "note": "Energy capacity (net) 19.7 on Media information 06/2024",
            },
        ],
    }

    new_ver = 84
    cdn["seedVersion"] = new_ver
    cdn["prevSeedVersion"] = 83
    cdn["rows"] = len(seed)
    payload = json.dumps(seed, separators=(",", ":"), ensure_ascii=False)
    cdn["bytes"] = len(payload.encode())
    cdn["updatedAt"] = datetime.now(timezone.utc).isoformat()
    cdn["note"] = (
        "seedVersion 84: PHEV wave2 batch2 research — Audi Q5 SB 2024 eTD; BMW X1 30e 2023 / "
        "Active Tourer 225e 2023 / X3 30e 2024 nets+EAER; remaining batch2 honest nils; "
        "api/static sync deferred at seed 77"
    )
    SEED.write_text(payload)
    CDN.write_text(json.dumps(cdn, indent=2) + "\n")
    if SEED.stat().st_size != cdn["bytes"]:
        raise SystemExit(f"CDN bytes mismatch {cdn['bytes']} vs {SEED.stat().st_size}")

    man = {
        "seedVersion": new_ver,
        "prevSeedVersion": 83,
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
            "Batch2 = next 40 incomplete after batch1 (40) + batch1 extras excluded.",
            "Fills: Q5 SB 2024 eTD; X1 30e 2023; Active Tourer 225e 2023; X3 30e 2024.",
            "No CS/CD pure fills this pass where sheets only show weighted.",
        ],
        "prKind": "research",
        "battery_convention": battery_convention,
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
