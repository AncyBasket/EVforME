#!/usr/bin/env python3
"""
PHEV wave2 batch3 RESEARCH (seed 86→87).

Official OEM fills for the 36 remaining PR #40 incomplete IDs after batch1∪extras∪batch2.
Non-lotto rows (incl. batch1 + batch2) stay byte-identical.
"""

from __future__ import annotations

import hashlib
import json
import math
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
INVENTORY = CACHE / "catalog_phev_wave2_batch3_inventory.json"
MANIFEST = CACHE / "catalog_phev_wave2_batch3_manifest.json"
RESEARCH = CACHE / "catalog_phev_wave2_batch3_research.json"
SOURCE_DAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")

NON_PHEV_SHA = "6b9038232bc51daabc9e259fc0dab170f787984d4dfb8f597e309fe50155b4dc"
CALC_FIELDS = (
    "fuelConsumptionLPerKm",
    "energyConsumptionKWhPerKm",
    "wltpRangeKm",
    "batteryKWh",
)

EVOQUE = (
    "https://www.landrover.com/content/dam/lrdx/pdfs/xi/wltp/"
    "Land-Rover-Range-Rover-Evoque-TD-Insert-1L5512400000XXEN01P.pdf"
)
MAZDA_CX60 = (
    "https://media-assets.mazda.eu/raw/upload/mazdade/globalassets/pdfs/brochure/cx-60/"
    "03-07-2023_preisliste_2022_mazda-cx-60.pdf"
)
MITSU = (
    "https://www.mitsubishi-motors.at/content/dam/mitsubishi-motors-at/preislisten/"
    "eclipse-cross-phev/broschüre/EclipseCrossPHEV_MY23_Broschuere.pdf"
)
PEUGEOT_308 = (
    "https://www.media.stellantis.com/uploads/uk/model-pricelist/"
    "peugeot308pricespecapr23-6455a56f26ccf.pdf"
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


def clear_field(row: dict, field: str) -> None:
    row[field] = None
    fs = dict(row.get("fieldSources") or {})
    fd = dict(row.get("fieldSourceDates") or {})
    fs.pop(field, None)
    fd.pop(field, None)
    row["fieldSources"] = fs or None
    row["fieldSourceDates"] = fd or None


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
    if int(cdn.get("seedVersion") or 0) != 86:
        raise SystemExit(f"expected seed 86 baseline, got {cdn.get('seedVersion')}")

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
    batch3 = inv["batch3_candidates"]
    batch3_ids = [x["id"] for x in batch3]
    assert len(batch3_ids) == 36, len(batch3_ids)
    lotto = set(batch3_ids)
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
    battery_convention_pass: list[dict] = []

    def record_fill(rid: str, field: str, value, url: str, source_date: str, **extra) -> None:
        changed_fields.append(
            {"id": rid, "field": field, "value": value, "url": url, "sourceDate": source_date, **extra}
        )

    # --- Land Rover Evoque P300e 2023 (usable battery) ------------------------------------
    evo = by_id["land-rover-range-rover-evoque-phev-2023"]
    cite = (
        "Land Rover TECHNICAL SPECIFICATION 2023 — P300e: Battery capacity Total (Usable) "
        "kWh 14,9 (12,1) → store usable 12.1; data da metadati PDF CreationDate "
        f"D:20230614160233+05'30' → 2023-06-14; CS/EAER/CD not filled from this sheet "
        f"(WLTP combined fuel is not discharged; TEL range not EAER MIN) {EVOQUE}"
    )
    set_field(evo, "batteryKWh", 12.1, cite, "2023-06-14")
    append_source(evo, f"wave2-batch3 Land Rover Evoque P300e usable 12.1 — {EVOQUE}")
    evo["sourceUpdatedAt"] = SOURCE_DAY
    finalize(evo)
    record_fill(evo["id"], "batteryKWh", 12.1, EVOQUE, "2023-06-14", variant="P300e")
    battery_convention_pass.append(
        {"id": evo["id"], "batteryKWh": 12.1, "note": "Total (Usable) 14,9 (12,1) — store usable 12.1"}
    )
    partial.append(
        {
            "id": evo["id"],
            "filled": {"batteryKWh": 12.1},
            "left_nil": ["fuelConsumptionLPerKm", "energyConsumptionKWhPerKm", "wltpRangeKm"],
            "note": "usable battery only; CS/EAER/CD labels missing on same sheet",
        }
    )

    # --- Mazda CX-60 PHEV 2023 (EAER combined) --------------------------------------------
    mazda = by_id["mazda-cx-60-phev-2023"]
    cite = (
        "Mazda DE Preisliste CX-60 Stand: 03. Juli 2023 — e-SKYACTIV PHEV column: "
        "WLTP elektrische Reichweite (km) kombiniert 63 (innerorts 68 not used); "
        "footnote 10 real-world variance only (not bis zu); Batteriekapazität 17,8 unlabeled → bat nil; "
        f"Kraftstoff/Strom gewichtet → CS/CD nil {MAZDA_CX60}"
    )
    set_field(mazda, "wltpRangeKm", 63, cite, "2023-07-03")
    append_source(mazda, f"wave2-batch3 Mazda CX-60 EAER kombiniert 63 — {MAZDA_CX60}")
    mazda["sourceUpdatedAt"] = SOURCE_DAY
    finalize(mazda)
    record_fill(mazda["id"], "wltpRangeKm", 63, MAZDA_CX60, "2023-07-03", variant="e-SKYACTIV PHEV")
    partial.append(
        {
            "id": mazda["id"],
            "filled": {"wltpRangeKm": 63},
            "left_nil": ["fuelConsumptionLPerKm", "energyConsumptionKWhPerKm", "batteryKWh"],
            "note": "WLTP combined electric range only; battery unlabeled; fuel/energy gewichtet",
        }
    )

    # --- Mitsubishi Eclipse Cross PHEV 2023 (pure CD kWh) ---------------------------------
    mitsu = by_id["mitsubishi-eclipse-cross-phev-2023"]
    cite = (
        "Mitsubishi Motors AT Eclipse Cross PHEV MY23 brochure — EV-Betrieb rein elektrisch "
        "(charge-depleting / rein elektrischem) 17,5 kWh/100km → 0.175 kWh/km; "
        "WLTP Gewichteter kombinierter Verbrauch 2 l/100km stays weighted-only → CS nil; "
        "Kapazität 13,8 unlabeled → bat nil; Norm-Reichweite rein elektrisch 45 not EAER combined "
        f"→ EAER nil; data da metadati PDF CreationDate D:20230427174320+02'00' → 2023-04-27 {MITSU}"
    )
    set_field(mitsu, "energyConsumptionKWhPerKm", 0.175, cite, "2023-04-27")
    mitsu["energyIsWeighted"] = False
    append_source(
        mitsu,
        f"wave2-batch3 Mitsubishi Eclipse Cross rein elektrisch / charge-depleting 0.175 — {MITSU}",
    )
    mitsu["sourceUpdatedAt"] = SOURCE_DAY
    finalize(mitsu)
    record_fill(
        mitsu["id"],
        "energyConsumptionKWhPerKm",
        0.175,
        MITSU,
        "2023-04-27",
        variant="Eclipse Cross PHEV MY23",
    )
    partial.append(
        {
            "id": mitsu["id"],
            "filled": {"energyConsumptionKWhPerKm": 0.175},
            "left_nil": ["fuelConsumptionLPerKm", "wltpRangeKm", "batteryKWh"],
            "note": "pure CD rein elektrisch only",
        }
    )

    # --- Peugeot 308 PHEV 2023 (EAER from Electric Range Combined MIN) --------------------
    p308 = by_id["peugeot-308-phev-2023"]
    mi_min = 37.0
    eaer = int(math.floor(mi_min * 1.609344))
    assert eaer == 59
    cite = (
        "Peugeot UK Prices-Equipment-Technical Specifications 308 & 308 SW Version 1.7 "
        "Effective from 1st April 2023 (2023.25 Model Year) — aggregate HYBRID 180/225 e-EAT8: "
        "Electric Range (Combined) miles Very High–Very Low Consumption MIN 37 → floor(37×1.609344)=59 km; "
        "tax-only EAER (miles) line rejected per sheet footnote; Battery Capacity 12.4 unlabeled "
        f"(BEV Usable Battery Capacity labeled separately) → bat nil; fuel 1.0–1.2 weighted → CS nil "
        f"{PEUGEOT_308}"
    )
    set_field(p308, "wltpRangeKm", eaer, cite, "2023-04-01")
    append_source(p308, f"wave2-batch3 Peugeot 308 Electric Range Combined MIN 59 km — {PEUGEOT_308}")
    p308["sourceUpdatedAt"] = SOURCE_DAY
    finalize(p308)
    record_fill(
        p308["id"],
        "wltpRangeKm",
        eaer,
        PEUGEOT_308,
        "2023-04-01",
        variant="aggregate HYBRID 180/225",
    )
    partial.append(
        {
            "id": p308["id"],
            "filled": {"wltpRangeKm": eaer},
            "left_nil": ["fuelConsumptionLPerKm", "energyConsumptionKWhPerKm", "batteryKWh"],
            "note": "Electric Range Combined MIN across 180/225; battery unlabeled; CS weighted-only",
        }
    )

    # --- Scrub RAV4 2023 unlabeled battery ------------------------------------------------
    rav4 = by_id["toyota-rav4-phev-2023"]
    if rav4.get("batteryKWh") is not None:
        clear_field(rav4, "batteryKWh")
        append_source(
            rav4,
            "wave2-batch3 scrub: MY23 scheda Litio Capacità 18.1 kWh unlabeled net/usable → battery nil",
        )
        rav4["sourceUpdatedAt"] = SOURCE_DAY
        finalize(rav4)
        changed_fields.append(
            {
                "id": rav4["id"],
                "field": "batteryKWh",
                "value": None,
                "was": 18.1,
                "url": "https://newsroom.toyota.it/download/1316286/20230101rav4plug-inhybridmy23schedatecnica.pdf",
                "sourceDate": "2023-01-03",
                "note": "scrub unlabeled capacity",
            }
        )

    # --- Left-nil for remaining lotto rows ------------------------------------------------
    filled_ids = {e["id"] for e in partial + completed + homolog_reuse}
    nil_reasons = {
        "land-rover-range-rover-evoque-phev-2022": (
            "No MY2022-dated OEM sheet with CS discharged, EAER combined MIN, or net/usable battery. "
            "MY22 DE list is Juni 2021 (calendar 2021). Nov 2022 list is MY23 packaging.",
            [
                {
                    "url": "https://www.landrover.de/content/dam/landrover/germany/brochure-pdfs/download-a-brochure/price-lists/L551-Range-Rover-Evoque-MY22-PL-06-21-D1d-Ansicht.pdf",
                    "sourceDate": "2021-06-01",
                    "reject_for": "Juni 2021 calendar year ≠ MY2022; Batteriekapazität unlabeled; fuel not CS",
                },
                {
                    "url": "https://www.landrover.de/content/dam/lrdx/pdfs/de/download-a-brochure/L551%20Range%20Rover%20Evoque%20MY23%20PL%2011-22%20D1c.pdf",
                    "sourceDate": "2022-11-30",
                    "reject_for": "Stand 30.11.2022 but file is MY23 — not MY2022",
                },
            ],
        ),
        "lexus-nx-phev-450h-2024": (
            "2024 OEM AT Preisliste (Stand Januar 2024) has bis zu range, unlabeled 18.1 kWh, weighted fuel/energy only. "
            "Live aktuelle-preislisten PDF is continuous and a later powertrain.",
            [
                {
                    "url": "https://www.lexus.at/content/dam/lexus/nmsc/austria/broschueren-preislisten/januar24/Preisliste_NX_Januar24_AT.pdf",
                    "sourceDate": None,
                    "reject_for": "Stand Januar 2024 month-only; bis zu range; 18,1 unlabeled; weighted only",
                },
                {
                    "url": "https://www.lexus.at/content/dam/lexus/nmsc/austria/broschueren-preislisten/aktuelle-preislisten/Preisliste_NX_AT.pdf",
                    "sourceDate": None,
                    "reject_for": "live aktuelle-preislisten continuous; later 107 kW powertrain",
                },
            ],
        ),
        "lexus-nx-phev-450h-2023": (
            "Februar 2023 AT Preisliste: bis zu range, unlabeled 18.1 kWh, weighted combined only — no CS/EAER MIN/net.",
            [
                {
                    "url": "https://www.lexus.at/content/dam/lexus/nmsc/austria/broschueren-preislisten/23-0098_Preisliste_NX_Februar23_AT_AK3.pdf",
                    "sourceDate": None,
                    "reject_for": "Stand Februar 2023 month-only; bis zu 74; 18,1 unlabeled; weighted only",
                }
            ],
        ),
        "lexus-nx-phev-450h-2022": (
            "No 2022-dated OEM NX 450h+ sheet with net battery, CS discharged, or EAER combined MIN.",
            [
                {
                    "url": "https://newsroom.lexus.eu/download/1078126/nx450hand350h-presskit-english.pdf",
                    "sourceDate": "2021-09-01",
                    "reject_for": "2021 press kit ≠ MY2022; pending homologation range; unlabeled 18.1",
                }
            ],
        ),
        "mg-hs-phev-2024": (
            "No 2024 OEM sheet for the 119 kW EHS generation; 2024 press describes a later HS PHEV+ powertrain.",
            [
                {
                    "url": "https://news.mgmotor.eu/at/press/mg-hs-phev-ab-sofort-in-oesterreich-bestellbar/",
                    "sourceDate": "2024-09-26",
                    "reject_for": "new HS PHEV+ 105 kW petrol / 21.4 kWh — not catalog 119 kW; up-to range",
                },
                {
                    "url": "https://cdn.mgmotor.eu/images/model/brochure/EHS-brochure-EU-06-2023.pdf",
                    "sourceDate": None,
                    "reject_for": "Published June 2023 ≠ MY2024; unlabeled 16.6; weighted fuel",
                },
            ],
        ),
        "mg-hs-phev-2023": (
            "June 2023 EHS brochure matches 119 kW but unlabeled battery, weighted fuel, and month-only date.",
            [
                {
                    "url": "https://cdn.mgmotor.eu/images/model/brochure/EHS-brochure-EU-06-2023.pdf",
                    "sourceDate": None,
                    "reject_for": "Published June 2023 month-only; 16.6 unlabeled; WLTP Combined fuel weighted",
                }
            ],
        ),
        "mg-hs-phev-2022": (
            "1 Oct 2022 FR fiche: Capacité brute (gross), weighted combined fuel, autonomie not EAER combined.",
            [
                {
                    "url": "https://cdn.mgmotor.eu/images/model/product-sheets/Fiche-Produit-EHS-au-01-10-2022.pdf",
                    "sourceDate": "2022-10-01",
                    "reject_for": "Capacité brute not net; fuel WLTP combinée weighted; no EAER combined label",
                }
            ],
        ),
        "mazda-cx-60-phev-2024": (
            "No clean 2024-dated Mazda sheet: Sep 2024 AT list is month-only / CreationDate Aug; Dec 2024 DE list is MY2025.",
            [
                {
                    "url": "https://media-assets.mazda.eu/raw/upload/mazdaat/globalassets/01-global/downloads/preisliste/2024/09_24/mazdacx60_pl_09_2024_web.pdf",
                    "sourceDate": "2024-08-13",
                    "reject_for": "STAND SEPTEMBER 2024 month-only; CreationDate 2024-08-13 before stand",
                },
                {
                    "url": "https://media-assets.mazda.eu/raw/upload/mazdade/globalassets/pdfs/brochure/cx-60/02-12-2024_preisliste_2025_mazda-cx-60.pdf",
                    "sourceDate": "2024-12-02",
                    "reject_for": "Modelljahr 2025 Preisliste — not MY2024 catalog row",
                },
            ],
        ),
        "mercedes-benz-classe-a-phev-a-250-e-2024": (
            "No OEM-hosted dated Preisliste/tech PDF retrieved. Tables with nutzbar/EAER/entladener Batterie appear only on third-party mirrors (mbpassion.de) after Mercedes withdrew public hosting — rejected.",
            [
                {
                    "url": "https://media.mbpassion.de/preisliste/mbpassion.de-mercedes-benz-verzichtet-vollstaendig-auf-preislisten-mercedes-benz-preisliste-a-klasse-limousine-kompaktlimousine-wv177-2.pdf",
                    "sourceDate": "2024-07-11",
                    "reject_for": "third-party mbpassion.de host — not official Mercedes/media.mercedes-benz.com",
                }
            ],
        ),
        "mercedes-benz-classe-a-phev-a-250-e-2023": (
            "No OEM-hosted MY2023 Preisliste; kunzmann.de dealer mirror rejected as non-OEM host.",
            [
                {
                    "url": "https://www.kunzmann.de/tiny/Marken/Mercedes_Benz/A_Klasse/Mercedes-Benz-Preisliste-A-Klasse-Limousine-Kompakt.pdf",
                    "sourceDate": None,
                    "reject_for": "dealer mirror kunzmann.de — not OEM host",
                }
            ],
        ),
        "mercedes-benz-classe-a-phev-a-250-e-2022": (
            "No MY2022-dated OEM sheet with nutzbar battery / EAER combined / CS discharged.",
            [
                {
                    "url": "https://media.mercedes-benz.com/article/5a7fb814-8d6e-43ff-8532-f0b085464f1d",
                    "sourceDate": None,
                    "reject_for": "early EQ Power press: Gesamtkapazität 15,6 only; weighted/combined figures; undated for MY2022 fills",
                }
            ],
        ),
        "mercedes-benz-gla-phev-250-e-2024": (
            "No OEM-hosted MY2024 GLA Preisliste; mercedes-hummel.at dealer PDF rejected.",
            [
                {
                    "url": "https://mercedes-hummel.at/dokumente/Mercedes-Benz-Preisliste-2024-GLA.pdf",
                    "sourceDate": None,
                    "reject_for": "dealer host — not OEM",
                }
            ],
        ),
        "mercedes-benz-glc-phev-300-de-2023": (
            "No OEM-hosted MY2023 GLC Preisliste; kunzmann.de mirror rejected.",
            [
                {
                    "url": "https://www.kunzmann.de/tiny/Marken/Mercedes_Benz/GLC/GLC_SUV/Mercedes-Benz-Preisliste-GLC-SUV-X254.pdf",
                    "sourceDate": None,
                    "reject_for": "dealer mirror — not OEM",
                }
            ],
        ),
        "mercedes-benz-glc-phev-300-de-2022": (
            "No MY2022 OEM sheet with WLTP EAER / nutzbar / CS discharged for GLC 300 de.",
            [
                {
                    "url": "https://www.kunzmann.de/tiny/Marken/Mercedes_Benz/GLC/GLC_SUV/20210708_Mercedes-Benz-Preisliste-GLC.pdf",
                    "sourceDate": "2021-07-08",
                    "reject_for": "gültig ab 8. Juli 2021 ≠ MY2022; dealer host",
                }
            ],
        ),
        "mercedes-benz-gle-phev-350-de-2024": (
            "No OEM-hosted MY2024 GLE Preisliste; mbpassion.de mirror rejected.",
            [
                {
                    "url": "https://media.mbpassion.de/preisliste/mbpassion.de-mercedes-benz-verzichtet-vollstaendig-auf-preislisten-mercedes-benz-preisliste-gle.pdf",
                    "sourceDate": None,
                    "reject_for": "third-party mbpassion host — not OEM",
                }
            ],
        ),
        "mercedes-benz-gle-phev-350-de-2023": (
            "No OEM-hosted MY2023 GLE Preisliste; kunzmann.de mirror rejected.",
            [
                {
                    "url": "https://www.kunzmann.de/tiny/Marken/Mercedes_Benz/GLE/GLE_SUV/Mercedes-Benz-Preisliste-GLE-SUV-V167.pdf",
                    "sourceDate": None,
                    "reject_for": "dealer mirror — not OEM",
                }
            ],
        ),
        "mercedes-benz-gle-coupe-phev-350-de-2024": (
            "No OEM-hosted MY2024 GLE Coupé Preisliste; mbpassion.de mirror rejected.",
            [
                {
                    "url": "https://media.mbpassion.de/preisliste/mbpassion.de-mercedes-benz-verzichtet-vollstaendig-auf-preislisten-mercedes-benz-preisliste-gle-coupe.pdf",
                    "sourceDate": None,
                    "reject_for": "third-party mbpassion host — not OEM",
                }
            ],
        ),
        "mercedes-benz-gle-coupe-phev-350-de-2023": (
            "No OEM-hosted MY2023 GLE Coupé Preisliste; kunzmann.de mirror rejected.",
            [
                {
                    "url": "https://www.kunzmann.de/tiny/Marken/Mercedes_Benz/GLE/GLE_Coupe/Mercedes-Benz-Preisliste-GLE-Coupe-C167.pdf",
                    "sourceDate": None,
                    "reject_for": "dealer mirror — not OEM",
                }
            ],
        ),
        "opel-grandland-phev-2023": (
            "FR Stellantis MY23 tariffs: weighted mixte fuel, autonomie électrique pure + EAER-City only, unlabeled 14.2 kWh; petrol powers 133/147 kW ≠ catalog 141.8.",
            [
                {
                    "url": "https://www.media.stellantis.com/uploads/fr/model-document/tarifsgrandlandmy23aamg0applicablesau1erfevrier2023-63db7b94d243b.pdf",
                    "sourceDate": "2023-02-01",
                    "reject_for": "mixte weighted; EAER-City only; 14,2 unlabeled; power mismatch vs 141.8",
                }
            ],
        ),
        "peugeot-308-phev-2022": (
            "No MY2022 OEM sheet with net battery / CS discharged / datable EAER combined MIN. Apr 2023 UK guide is MY 2023.25.",
            [
                {
                    "url": "https://www.media.stellantis.com/uploads/uk/model-pricelist/peugeot308pricespecapr23-6455a56f26ccf.pdf",
                    "sourceDate": "2023-04-01",
                    "reject_for": "2023.25 Model Year — cannot date MY2022",
                }
            ],
        ),
        "porsche-cayenne-phev-e-hybrid-2024": (
            "EU tech sheet matching ICE 224 kW / weighted 1.8–1.5 is CreationDate 2023-11-29 (MY R 04/2023) — no 2024 dating token. Battery Energy capacity 25.9 unlabeled; no depleted CS on that sheet. Live e-performance page continuous.",
            [
                {
                    "url": "https://newsroom.porsche.com/dam/jcr:0d48c8ff-e3a3-4d70-b51a-3d27a27f47e4/pag-cayenne-e-hybrid-td-en",
                    "sourceDate": "2023-11-29",
                    "reject_for": "CreationDate 2023 / MY R 04/2023 — cannot date MY2024; Energy capacity unlabeled",
                }
            ],
        ),
        "porsche-cayenne-phev-e-hybrid-2023": (
            "Seed power 239.1 / weighted 2.511 do not match new-gen EU sheet (ICE 224 / weighted 1.8–1.5). Apr 2023 press kit EAER 66–74 is for the new gen; battery stated as gross 25.9.",
            [
                {
                    "url": "https://newsroom.porsche.com/dam/jcr:ac5f3c6c-3e92-40ab-8b3e-c0b4ac23c055/20230424_Pressemappe_Porsche_Cayenne_2023_en_neu.pdf.PDF",
                    "sourceDate": "2023-04-24",
                    "reject_for": "power/weighted mismatch vs seed 239.1/2.511; battery gross 25.9; no CS depleted on kit",
                }
            ],
        ),
        "porsche-cayenne-phev-e-hybrid-2022": (
            "Previous-gen EU sheet matches ICE ~250 kW but CreationDate 2021 — cannot date MY2022. No 2022-dated OEM PDF with net/CS/EAER MIN verified.",
            [
                {
                    "url": "https://newsroom.porsche.com/dam/jcr:c8bd6fb1-ba9e-4d7b-baef-a1cfbe33b565/PAG_Cayenne_E-Hybrid_TD_EN.pdf",
                    "sourceDate": "2021-03-15",
                    "reject_for": "CreationDate 2021-03-15 ≠ MY2022; 17.9 kWh unlabeled; EAER City only; no CS discharged",
                },
                {
                    "url": "https://newsroom.porsche.com/dam/jcr:8955262e-512e-4df6-b562-147cb4c15495/PI20201028e_A%20greater%20electric%20range%20for%20the%20Cayenne%20E-Hybrid.pdf",
                    "sourceDate": "2020-10-28",
                    "reject_for": "28 Oct 2020 press — wrong year; gross 17.9; up-to EAER City",
                },
            ],
        ),
        "renault-captur-phev-e-tech-phev-2023": (
            "No 2023-dated Renault Group fiche with net battery, CS discharged, or EAER combined MIN for Captur E-Tech plug-in. NL 21 Apr 2023 prijslijst is prices/CO2 only.",
            [
                {
                    "url": "https://cdn.group.renault.com/ren/nl/brochures-en-prijslijsten/prijzenarchief/captur/RENAULT_CAPTUR_21_APRIL_2023_WEB.pdf",
                    "sourceDate": "2023-04-21",
                    "reject_for": "official NL prijslijst 21 april 2023 — prices/CO2 only; no net kWh, CS discharged, or EAER combined",
                },
                {
                    "url": "https://media.renault.com/a-unique-e-tech-hybrid-range-to-drive/?lang=eng",
                    "sourceDate": "2020-06-12",
                    "reject_for": "12 June 2020 media — wrong year; up-to range; no net/CS",
                },
            ],
        ),
        "toyota-rav4-phev-2024": (
            "No MY2024 Toyota EU/IT sheet with net/usable battery, CS discharged, or datable EAER combined MIN for the 18.1 kWh generation.",
            [
                {
                    "url": "https://newsroom.toyota.eu/download/925553/rav4-plug-in-hybrid.pdf",
                    "sourceDate": "2020-09-14",
                    "reject_for": "CreationDate 2020 ≠ MY2024; capacity 18.1 unlabeled; fuel UF Weighted",
                },
                {
                    "url": "https://newsroom.toyota.it/download/1bc2f945-9cd5-4dca-901f-fa922ae41283/rav4my25-schedatecnicaequipment.pdf",
                    "sourceDate": "2024-10-31",
                    "reject_for": "RAV4 MY25 listino — not MY2024",
                },
            ],
        ),
        "toyota-rav4-phev-2023": (
            "MY23 IT scheda (CreationDate 2023-01-03) matches car but Litio Capacità 18.1 unlabeled (scrubbed); WLTP 1.00 weighted; no EAER on sheet. EAER Combined 75 only on 2020 EU PDF.",
            [
                {
                    "url": "https://newsroom.toyota.it/download/1316286/20230101rav4plug-inhybridmy23schedatecnica.pdf",
                    "sourceDate": "2023-01-03",
                    "reject_for": "18.1 unlabeled → scrubbed; weighted fuel; no EAER",
                },
                {
                    "url": "https://newsroom.toyota.eu/download/925553/rav4-plug-in-hybrid.pdf",
                    "sourceDate": "2020-09-14",
                    "reject_for": "2020 ≠ MY2023 for EAER 75 fill",
                },
            ],
        ),
        "toyota-rav4-phev-2022": (
            "No 2022-dated Toyota sheet with net battery / CS / datable EAER combined MIN.",
            [
                {
                    "url": "https://newsroom.toyota.eu/download/925553/rav4-plug-in-hybrid.pdf",
                    "sourceDate": "2020-09-14",
                    "reject_for": "2020 ≠ MY2022",
                }
            ],
        ),
        "volkswagen-golf-gte-phev-2024": (
            "VW Newsroom Golf GTE press uses up-to range and weighted energy; no net battery / CS discharged / EAER MIN on a MY2024-dated OEM PDF.",
            [
                {
                    "url": "https://www.volkswagen-newsroom.com/en/press-releases/dynamic-and-with-a-long-range-golf-gte-and-golf-r-variant",
                    "sourceDate": "2024-05-16",
                    "reject_for": "up-to range; weighted energy; no net kWh / CS discharged on dated sheet",
                }
            ],
        ),
        "volkswagen-tiguan-phev-ehybrid-2024": (
            "2024 VW Newsroom press for new Tiguan PHEV uses bis zu / circa ranges and weighted energy; no CS discharged + EAER combined MIN pair usable for this seed row.",
            [
                {
                    "url": "https://www.volkswagen-newsroom.com/de/pressemitteilungen/ab-sofort-bestellbar-reichweitenstarke-plug-in-hybridantriebe-fuer-den-neuen-tiguan-18101",
                    "sourceDate": "2024-02-22",
                    "reject_for": "bis zu ca. 120 km; fuel not labeled entladener Batterie; new-generation packaging",
                },
                {
                    "url": "https://www.volkswagen-newsroom.com/de/publikationen/weitere/der-neue-tiguan-2625/download",
                    "sourceDate": "2024-09-01",
                    "reject_for": "Stand Sept 2024 booklet — circa/Prognose range; electricity gewichtet only",
                },
            ],
        ),
        "volkswagen-tiguan-phev-ehybrid-2023": (
            "No 2023-dated VW OEM sheet for previous Tiguan eHybrid with net/CS/EAER MIN. 2024 new-Tiguan booklet mentions predecessor 10.6 netto / rund 60 only as comparison.",
            [
                {
                    "url": "https://www.volkswagen-newsroom.com/de/publikationen/weitere/der-neue-tiguan-2625/download",
                    "sourceDate": "2024-09-01",
                    "reject_for": "Stand Sept 2024 ≠ MY2023; predecessor 10.6 netto / rund 60 is comparison text not a MY2023 sheet",
                },
                {
                    "url": "https://www.volkswagen-newsroom.com/de/pressemitteilungen/ab-sofort-bestellbar-reichweitenstarke-plug-in-hybridantriebe-fuer-den-neuen-tiguan-18101",
                    "sourceDate": "2024-02-22",
                    "reject_for": "new Tiguan 2024 press — wrong generation/year for MY2023",
                },
            ],
        ),
        "volkswagen-tiguan-phev-ehybrid-2022": (
            "No 2022-dated VW OEM sheet with net/CS/EAER MIN for Tiguan eHybrid. 2024 booklet predecessor figures are not a MY2022-dated source.",
            [
                {
                    "url": "https://www.volkswagen-newsroom.com/de/publikationen/weitere/der-neue-tiguan-2625/download",
                    "sourceDate": "2024-09-01",
                    "reject_for": "2024 booklet ≠ MY2022; predecessor 10.6 netto / rund 60 not a 2022 combined-minimum sheet",
                },
                {
                    "url": "https://www.volkswagen-newsroom.com/en/publications/more/the-all-new-tiguan-2625/download",
                    "sourceDate": "2024-09-01",
                    "reject_for": "English 2024 booklet — same dating failure for MY2022",
                },
            ],
        ),
        "volvo-xc60-phev-recharge-2022": (
            "Volvo media press for MY2022 cites Speicherkapazität 18.8 kWh (not usable/net) and bis zu 78 km; fuel figures gewichtet. Live specs page continuous / later Long Range.",
            [
                {
                    "url": "https://www.volvocars.com/de/media/press-releases/BCFB22DCF4F36477/",
                    "sourceDate": None,
                    "reject_for": "18.8 Speicherkapazität unlabeled usable; bis zu 78; kraftstoff gewichtet; undated day for fill",
                },
                {
                    "url": "https://www.volvocars.com/de/cars/xc60-hybrid/specifications/",
                    "sourceDate": None,
                    "reject_for": "live continuous specs — invalid for past MY2022",
                },
            ],
        ),
    }

    # Evoque 2023 / mazda / mitsu / peugeot 2023 already in partial — also add nil reasons for their remaining fields via left_nil notes only.
    for rid in batch3_ids:
        if rid in filled_ids:
            continue
        if rid == "toyota-rav4-phev-2023":
            # scrubbed; still incomplete — document as left_nil
            reason, consulted = nil_reasons[rid]
            left_nil.append(nil_entry(by_id[rid], reason=reason, consulted=consulted))
            continue
        if rid not in nil_reasons:
            raise SystemExit(f"missing nil reason for {rid}")
        reason, consulted = nil_reasons[rid]
        # filter generic hubs from consulted (still allow documenting but prefer specific)
        left_nil.append(nil_entry(by_id[rid], reason=reason, consulted=consulted))

    # Also document remaining gaps on partial rows? Manifest left_nil is for fully-unfilled rows only.
    # Partial rows already listed.

    covered = {e["id"] for e in partial + completed + homolog_reuse + left_nil}
    missing = [i for i in batch3_ids if i not in covered]
    if missing:
        raise SystemExit(f"uncovered batch3 ids: {missing}")

    # Finalize untouched lotto rows that stayed fully nil (already finalized only for fills/scrub)
    for rid in batch3_ids:
        if rid in filled_ids or rid == "toyota-rav4-phev-2023":
            continue
        finalize(by_id[rid])

    # Invariants
    if [r["id"] for r in seed] != ids_before:
        raise SystemExit("id order drift")
    for rid, blob in outside_before.items():
        now = json.dumps(by_id[rid], sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        if now != blob:
            raise SystemExit(f"non-lotto drift: {rid}")
    for rid, blob in m3_before.items():
        now = json.dumps(by_id[rid], sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        if now != blob:
            raise SystemExit(f"m3 drift: {rid}")
    non_phev_sha = hashlib.sha256(
        tech_blob([r for r in seed if r.get("powertrain") != "phev"]).encode()
    ).hexdigest()
    if non_phev_sha != NON_PHEV_SHA:
        raise SystemExit(f"non-PHEV SHA drift {non_phev_sha}")

    # Write seed + CDN (compact separators — match wave2 seed on-disk format)
    payload = json.dumps(seed, separators=(",", ":"), ensure_ascii=False)
    SEED.write_text(payload, encoding="utf-8")
    raw = SEED.read_bytes()
    prev = json.loads(CDN.read_text(encoding="utf-8"))
    cdn = dict(prev)
    cdn.update(
        {
            "rows": 6977,
            "bytes": len(raw),
            "source": "vehicles.seed.quality.json",
            "updatedAt": datetime.now(timezone.utc).isoformat(),
            "seedVersion": 87,
            "prevSeedVersion": 86,
            "note": (
                "seedVersion 87: PHEV wave2 batch3 research — Evoque usable 12.1; "
                "Mazda CX-60 EAER 63; Mitsubishi Eclipse pure CD 0.175; Peugeot 308 EAER 59; "
                "RAV4 2023 unlabeled battery scrubbed; api/static sync deferred at seed 77"
            ),
        }
    )
    CDN.write_text(json.dumps(cdn, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    counts = {
        "completed": len(completed),
        "partial": len(partial),
        "homolog_reuse": len(homolog_reuse),
        "left_nil": len(left_nil),
    }
    man = {
        "seedVersion": 87,
        "prevSeedVersion": 86,
        "ids_before": ids_before,
        "batch3_ids": batch3_ids,
        "completed": completed,
        "partial": partial,
        "extras": [],
        "homolog_reuse": homolog_reuse,
        "left_nil": left_nil,
        "changed_fields": changed_fields,
        "counts": counts,
        "non_phev_tech_sha": NON_PHEV_SHA,
        "m3_ids": sorted(m3_before.keys()),
        "sourceDay": SOURCE_DAY,
        "selection": inv.get("selection"),
        "prKind": "research",
        "battery_convention": {
            "catalogConvention": "net/usable",
            "thisPass": battery_convention_pass
            + [
                {
                    "id": "toyota-rav4-phev-2023",
                    "batteryKWh": None,
                    "note": "scrubbed unlabeled Litio Capacità 18.1",
                }
            ],
        },
        "prevManifestSeed": 86,
        "cdn_bytes": len(raw),
    }
    MANIFEST.write_text(json.dumps(man, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "seedVersion": 87,
                "bytes": len(raw),
                "counts": counts,
                "changed": len(changed_fields),
                "non_phev_tech_sha": non_phev_sha,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
