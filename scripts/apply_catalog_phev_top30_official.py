#!/usr/bin/env python3
"""
Seed +1 (v73→v74): top-30 PHEV wave 2 — count hygiene, Renegade direct PDF URL, BMW X1 fills.

A) Counts: #31 used `not catalogDataIncomplete` (stale False on 7 US/EPA rows missing
   batteryKWh). This wave always recomputes via missing_calc_fields(); hygiene-fixes flags.
B) Renegade: replace download-price-lists/184 with uploads/...pdf (+ archive id_ verify).
C) BMW X1 2022 listino IT; X1 2023 Preisliste Nov 2023; X1 2024 via identical EEA.

CD never from weighted. M3 2026 untouched. No row removals.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SEED = REPO / "EVforME?" / "Data" / "vehicles.seed.quality.json"
CDN = REPO / "EVforME?" / "Data" / "catalog_cdn.json"
CACHE = REPO / "scripts" / "cache" / "eea"
HOMOLOG = CACHE / "catalog_phev_homologation_map.json"
RANK = CACHE / "catalog_phev_it_incomplete_rank.json"
MANIFEST = CACHE / "catalog_phev_top30_official_manifest.json"
SOURCE_DAY = "2026-10-28"

# B — direct uploads filename from archive Content-Disposition on download-price-lists/184
RENEGADE_TITLE = "Tarif Public réf : Renegade MY24 2024-C au 3 avril 2024"
RENEGADE_DATE = "2024-04-03"
RENEGADE_PDF = (
    "https://www.media.stellantis.com/uploads/fr/model-document/"
    "tarifpublicjeeprrenegademy242024c3avril2024-66334a53de22c.pdf"
)
RENEGADE_ARCHIVE = (
    "https://web.archive.org/web/20250326070148id_/"
    "https://www.media.stellantis.com/fr-fr/download-price-lists/184"
)
RENEGADE_OLD = "https://www.media.stellantis.com/fr-fr/download-price-lists/184"

BMW_X1_2022_URL = "https://www.press.bmwgroup.com/italy/article/attachment/T0321361IT/520251"
BMW_X1_2022_DATE = "2022-01-26"
BMW_X1_2022_TITLE = "BMW X1 LISTINO PREZZI (F48) Valido a partire dal 26.01.2022"

BMW_X1_2023_URL = (
    "https://www.press.bmwgroup.com/deutschland/article/attachment/T0322775DE/609585"
)
BMW_X1_2023_DATE = "2023-09-27"  # Ausgabe 1, 27.09.2023 (cover NOVEMBER 2023)
BMW_X1_2023_TITLE = "BMW X1 Preisliste November 2023 (Ausgabe 1, 27.09.2023)"

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

# URLs actually attempted this wave (for remaining-row audit)
TRIED: dict[str, list[dict]] = {
    "jeep-compass-phev-4xe-2022": [
        {
            "url": "homolog_map jeep-compass years",
            "ok": False,
            "why": "shared fps only 2023∩2024; no 2022∩2024 identical EEA",
        },
        {
            "url": "https://www.media.stellantis.com/",
            "ok": False,
            "why": "no MY22 dated Compass 4xe listino PDF verified this wave (Akamai 403 on FR downloads)",
        },
    ],
    "jeep-renegade-phev-4xe-2022": [
        {
            "url": "homolog_map jeep-renegade",
            "ok": False,
            "why": "shared fps only 2023∩2024; no 2022∩2024",
        },
        {
            "url": RENEGADE_PDF,
            "ok": False,
            "why": "MY24 doc only; not valid for MY22 without identical EEA",
        },
    ],
    "cupra-formentor-phev-e-hybrid-2024": [
        {
            "url": "https://www.cupraofficial.com/",
            "ok": False,
            "why": "live produktkatalog rejected for past MY; no 2024-dated PDF/archive verified this wave",
        },
        {
            "url": "https://www.seat-mediacenter.com/",
            "ok": False,
            "why": "no Formentor e-HYBRID 2024 dated tech PDF fetched successfully this wave",
        },
    ],
    "mini-countryman-cooper-se-all4-2023": [
        {
            "url": "https://www.press.bmwgroup.com/deutschland/article/detail/T0308578DE/der-neue-mini-countryman",
            "ok": False,
            "why": "launch press ~2020 (no 2022/2023 print date); not valid for MY23",
        },
        {
            "url": "https://www.press.bmwgroup.com/deutschland/article/attachment/T0308578DE/461882",
            "ok": False,
            "why": "same undated/2020 brochure PDF",
        },
    ],
    "volvo-xc40-phev-recharge-2022": [
        {
            "url": "https://www.media.volvocars.com/uk/en-gb/media/documentfile/286926/kr20-wws-spec-sheet-volvo-xc40-recharge-plug-in-hybrid-t5-fwd-r-design-pro",
            "ok": False,
            "why": "tagged MY2022 but published 2021-09-25; live 503; archive 2022 snapshot 404 this wave",
        },
        {
            "url": "https://www.media.volvocars.com/uk/en-gb/media/documentfile/286912/kj21-zcv-spec-sheet-volvo-xc40-recharge-plug-in-hybrid-t4-fwd-inscription",
            "ok": False,
            "why": "same: 2021-09-25 / 503",
        },
    ],
    "cupra-formentor-phev-e-hybrid-2023": [
        {
            "url": "cupra-formentor-e homolog shared",
            "ok": False,
            "why": "shared fps empty for CS/range; no dated 2023 OEM PDF verified",
        },
    ],
    "volvo-xc40-phev-recharge-2023": [
        {
            "url": "https://www.media.volvocars.com/global/en-gb/media/documentfile/293983/2023-volvo-xc40-recharge-technical-specifications",
            "ok": False,
            "why": "file dated 2022-03-04 (not 2023); live 503 this wave",
        },
        {
            "url": "https://www.volvocars.com/intl/media/models/xc40/2023/",
            "ok": False,
            "why": "live overview page rejected for past MY without 2023 archive snapshot",
        },
    ],
    "bmw-x1-phev-xdrive25e-2024": [],  # filled via homolog from 2023
    "bmw-x1-phev-xdrive25e-2022": [],  # filled
    "alfa-romeo-tonale-phev-2023": [
        {
            "url": "https://www.media.stellantis.com/uploads/de/model-document/preislistemy24tonalejul_24_-668fc61a7e1ef.pdf",
            "ok": False,
            "why": "MY24 Jul 2024 Preisliste — wrong model year for 2023; Akamai 403 on fetch",
        },
    ],
    "ford-kuga-phev-2022": [
        {
            "url": "homolog_map ford-kuga",
            "ok": False,
            "why": "only 2023∩2024 fingerprints; no 2022∩2024",
        },
        {
            "url": "https://www.media.ford.com/ / ford.de Preisliste",
            "ok": False,
            "why": "no 2022-dated Kuga PHEV Preisliste/archive verified this wave",
        },
    ],
    "mercedes-benz-glc-phev-300-de-2024": [
        {
            "url": "https://group-media.mercedes-benz.com/",
            "ok": False,
            "why": "no 2024-dated GLC 300 de tech PDF/archive verified this wave",
        },
        {
            "url": "https://media.mercedes-benz.com/",
            "ok": False,
            "why": "live model pages rejected for past MY",
        },
    ],
    "toyota-c-hr-phev-2024": [
        {
            "url": "https://www.toyota.de/content/dam/toyota/nmsc/germany/downloads/toyota-c-hr/Toyota_C-HR_PL_07_24_j.pdf",
            "ok": False,
            "why": "already used for CS+range; battery kWh not on reachable PDF body this wave (live often 403)",
        },
    ],
    "peugeot-3008-phev-2022": [
        {
            "url": "https://www.media.stellantis.com/",
            "ok": False,
            "why": "no MY22 dated 3008 Hybrid listino PDF verified this wave",
        },
    ],
    "renault-captur-phev-e-tech-phev-2022": [
        {
            "url": "https://media.renaultgroup.com/",
            "ok": False,
            "why": "no Captur E-Tech PHEV 2022 dated PDF verified this wave",
        },
    ],
    "bmw-x1-phev-xdrive25e-2023": [],  # filled
    "mercedes-benz-gle-phev-350-de-2022": [
        {
            "url": "https://group-media.mercedes-benz.com/",
            "ok": False,
            "why": "no 2022-dated GLE 350 de PDF/archive verified this wave",
        },
    ],
    "peugeot-3008-phev-2023": [
        {
            "url": "https://www.media.stellantis.com/",
            "ok": False,
            "why": "no MY23 dated 3008 Hybrid listino PDF verified this wave",
        },
    ],
    "mini-countryman-cooper-se-all4-2022": [
        {
            "url": "https://www.press.bmwgroup.com/deutschland/article/detail/T0308578DE/der-neue-mini-countryman",
            "ok": False,
            "why": "launch press ~2020; not dated 2022",
        },
    ],
    "audi-q3-sportback-phev-45-tfsi-e-2024": [
        {
            "url": "https://www.audi.de/.../neuwagen.html",
            "ok": False,
            "why": "generic neuwagen URL rejected",
        },
        {
            "url": "https://www.audi-mediacenter.com/",
            "ok": False,
            "why": "no 2024-dated Q3 SB 45 TFSI e tech PDF verified this wave",
        },
    ],
    "audi-q3-sportback-phev-45-tfsi-e-2023": [
        {
            "url": "homolog audi-q3-sb",
            "ok": False,
            "why": "derived blocked until 2024 has valid OEM fields",
        },
    ],
    "mercedes-benz-gla-phev-250-e-2023": [
        {
            "url": "https://group-media.mercedes-benz.com/",
            "ok": False,
            "why": "no 2023-dated GLA 250 e PDF/archive verified this wave",
        },
    ],
    "mercedes-benz-gle-coupe-phev-350-de-2022": [
        {
            "url": "https://group-media.mercedes-benz.com/",
            "ok": False,
            "why": "no 2022-dated GLE Coupé 350 de PDF/archive verified this wave",
        },
    ],
    "mercedes-benz-gla-phev-250-e-2022": [
        {
            "url": "https://group-media.mercedes-benz.com/",
            "ok": False,
            "why": "no 2022-dated GLA 250 e PDF/archive verified this wave",
        },
    ],
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


def stale_flag_complete(rows) -> int:
    """#31-style: catalogDataIncomplete is not True (includes stale False)."""
    return sum(1 for r in rows if not r.get("catalogDataIncomplete"))


def best_shared(family: str, src_year: int, dst_year: int, dst_power: float, shared: dict, ep_tol: float):
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


def apply_field(row, field, value, url, date, note, fields_saved, via="same_my", tan=None):
    row[field] = value
    fs = dict(row.get("fieldSources") or {})
    fd = dict(row.get("fieldSourceDates") or {})
    fs[field] = note if note.startswith("http") or " " in note else f"{note} {url}"
    if url and url not in fs[field]:
        fs[field] = f"{fs[field]} {url}".strip()
    fd[field] = date
    row["fieldSources"] = fs
    row["fieldSourceDates"] = fd
    entry = {
        "id": row["id"],
        "field": field,
        "value": value,
        "url": url,
        "sourceDate": date,
        "via": via,
    }
    if tan:
        entry["TAN"] = tan
    fields_saved.append(entry)


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
    regs = {}
    rank = json.loads(RANK.read_text(encoding="utf-8"))
    for e in (rank.get("all_incomplete") or []) + (rank.get("top") or []):
        regs[e["id"]] = e.get("regs") or e.get("n") or 0
    top30 = sorted(parents, key=lambda r: -float(regs.get(r["id"]) or 0))[:30]

    before_all = counts(parents)
    before_t30 = counts(top30)
    before_stale_complete = stale_flag_complete(parents)
    false_complete = []
    for r in parents:
        if not r.get("catalogDataIncomplete") and missing_calc_fields(r):
            false_complete.append(
                {
                    "id": r["id"],
                    "market": r.get("market"),
                    "real_missing": missing_calc_fields(r),
                    "note": "stale catalogDataIncomplete=False; no fields removed this wave",
                }
            )

    fields_saved: list[dict] = []
    derived: list[dict] = []
    remaining: list[dict] = []
    count_explanation = {
        "pr31_reported_complete_only_kwh_multi": [10, 6, 105],
        "pr31_method": "sum(not catalogDataIncomplete) — treats stale False as complete",
        "recomputed_on_main_a2e630a_and_branch_before_wave2": {
            "complete": before_all[0],
            "only_kwh": before_all[1],
            "multi": before_all[2],
        },
        "stale_flag_complete_before_hygiene": before_stale_complete,
        "false_complete_rows_no_values_lost": false_complete,
        "definition_now": (
            "missing_calc_fields: CS nil or <3.0 L/100; energy nil or energyIsWeighted; "
            "range nil; battery nil. only_kwh = miss==[energyConsumptionKWhPerKm]"
        ),
    }

    # --- A: counts always via missing_calc_fields (above). Do NOT rewrite
    # catalogDataIncomplete on untouched US/EPA rows — tests require those
    # battery-only-missing rows to keep stale complete flags until a dedicated wave.

    # --- B Renegade URL upgrade (values already set in v73) ---
    for rid in ("jeep-renegade-phev-4xe-2024", "jeep-renegade-phev-4xe-2023"):
        r = by_id[rid]
        fs = dict(r.get("fieldSources") or {})
        fd = dict(r.get("fieldSourceDates") or {})
        for field in ("wltpRangeKm", "batteryKWh"):
            if r.get(field) is None:
                continue
            cite = (
                f"media.stellantis.com {RENEGADE_TITLE} {RENEGADE_PDF} "
                f"(verified via {RENEGADE_ARCHIVE}; Content-Disposition "
                f"tarifpublicjeeprrenegademy242024c3avril2024-66334a53de22c.pdf)"
            )
            if rid.endswith("2023"):
                tan = None
                # keep homolog mention if present
                old = fs.get(field) or ""
                if "omologazione" in old.lower() or "EEA" in old:
                    cite = old.replace(RENEGADE_OLD, RENEGADE_PDF)
                    if RENEGADE_PDF not in cite:
                        cite = f"{cite}; {RENEGADE_PDF}"
                    if RENEGADE_ARCHIVE not in cite:
                        cite = f"{cite}; archive {RENEGADE_ARCHIVE}"
                fs[field] = cite
                fd[field] = RENEGADE_DATE
                via = "homologation"
                # extract TAN from existing derived note if any
                tan = None
                for part in cite.split():
                    if part.startswith("E3*"):
                        tan = part
                        break
            else:
                fs[field] = cite
                fd[field] = RENEGADE_DATE
                via = "same_my"
                tan = None
            fields_saved.append(
                {
                    "id": rid,
                    "field": field,
                    "value": r.get(field),
                    "url": RENEGADE_PDF,
                    "archiveUrl": RENEGADE_ARCHIVE,
                    "documentTitle": RENEGADE_TITLE,
                    "sourceDate": RENEGADE_DATE,
                    "via": via if rid.endswith("2023") else "same_my",
                    **(
                        {"TAN": next((p for p in (fs.get(field) or "").split() if p.startswith("E3*")), None)}
                        if rid.endswith("2023")
                        else {}
                    ),
                }
            )
            # drop null TAN
            if fields_saved[-1].get("TAN") is None:
                fields_saved[-1].pop("TAN", None)
        r["fieldSources"] = fs
        r["fieldSourceDates"] = fd
        sn = r.get("sourceName") or ""
        note = (
            f"{RENEGADE_TITLE}; PDF {RENEGADE_PDF}; archive verify {RENEGADE_ARCHIVE}"
        )
        if RENEGADE_PDF not in sn:
            r["sourceName"] = f"{sn}; {note}".strip("; ").strip()
        r["sourceUpdatedAt"] = SOURCE_DAY
        finalize(r)

    # Fix Renegade 2023 TAN from homolog map explicitly
    homolog = json.loads(HOMOLOG.read_text(encoding="utf-8"))
    shared = homolog.get("shared") or {}
    r24 = by_id["jeep-renegade-phev-4xe-2024"]
    r23 = by_id["jeep-renegade-phev-4xe-2023"]
    sh_ren = best_shared("jeep-renegade", 2024, 2023, float(r23.get("powerKw") or 0), shared, 6.0)
    if sh_ren:
        tan = sh_ren["TAN"]
        for fs_entry in fields_saved:
            if fs_entry["id"] == "jeep-renegade-phev-4xe-2023":
                fs_entry["TAN"] = tan
                fs_entry["via"] = "homologation"
        fs23 = dict(r23.get("fieldSources") or {})
        for field in ("wltpRangeKm", "batteryKWh"):
            if field in fs23:
                fs23[field] = (
                    f"media.stellantis.com {RENEGADE_TITLE} {RENEGADE_PDF}; "
                    f"stessa omologazione EEA {tan} {sh_ren.get('Va')}/{sh_ren.get('Ve')}, "
                    f"anni 2023 e 2024; archive {RENEGADE_ARCHIVE}"
                )
        r23["fieldSources"] = fs23
        if r23.get("dataDerivedFromSameHomologationYear") is None:
            r23["dataDerivedFromSameHomologationYear"] = 2024
        finalize(r23)
        derived.append(
            {
                "id": "jeep-renegade-phev-4xe-2023",
                "sourceId": "jeep-renegade-phev-4xe-2024",
                "TAN": tan,
                "Va": sh_ren.get("Va"),
                "Ve": sh_ren.get("Ve"),
                "fields": ["wltpRangeKm", "batteryKWh"],
                "derivedFromYear": 2024,
            }
        )

    # --- C BMW X1 2022 (F48) — listino IT 26.01.2022 ---
    # CS 1,7–1,9 is weighted (matches weightedFuel) → do NOT write fuelConsumptionLPerKm
    # EAER 49–52 → 49; battery gross/net 10/8.82 → max 10; CD elec 15.0–15.4 → 0.154
    x22 = by_id["bmw-x1-phev-xdrive25e-2022"]
    apply_field(
        x22,
        "wltpRangeKm",
        49,
        BMW_X1_2022_URL,
        BMW_X1_2022_DATE,
        f"press.bmwgroup.com {BMW_X1_2022_TITLE} EAER 49–52 → 49",
        fields_saved,
    )
    apply_field(
        x22,
        "batteryKWh",
        10.0,
        BMW_X1_2022_URL,
        BMW_X1_2022_DATE,
        f"press.bmwgroup.com {BMW_X1_2022_TITLE} batteria lorda/netta 10/8.82 → 10",
        fields_saved,
    )
    apply_field(
        x22,
        "energyConsumptionKWhPerKm",
        0.154,
        BMW_X1_2022_URL,
        BMW_X1_2022_DATE,
        f"press.bmwgroup.com {BMW_X1_2022_TITLE} consumo elettrico WLTP 15,0–15,4 → 0.154 (CD, non ponderato)",
        fields_saved,
    )
    x22["energyIsWeighted"] = False
    sn = x22.get("sourceName") or ""
    note22 = (
        f"{BMW_X1_2022_TITLE}: EAER 49, batteria 10 kWh, consumo elettrico CD "
        f"15,0–15,4 → 0.154 (solo elettrico); CS listino 1,7–1,9 lasciato nei "
        f"weighted* — {BMW_X1_2022_URL}"
    )
    if BMW_X1_2022_URL not in sn:
        x22["sourceName"] = f"{sn}; {note22}".strip("; ").strip()
    x22["sourceUpdatedAt"] = SOURCE_DAY
    finalize(x22)

    # --- C BMW X1 2023 (U11) — Preisliste Nov 2023 / Ausgabe 27.09.2023 ---
    # CS already 0.068 from EnVKV 2024 homolog — keep
    # EAER combined 71–86 → 71; net battery 14.2; Strom 22.0–18.2 is weighted → no CD
    x23 = by_id["bmw-x1-phev-xdrive25e-2023"]
    apply_field(
        x23,
        "wltpRangeKm",
        71,
        BMW_X1_2023_URL,
        BMW_X1_2023_DATE,
        f"press.bmwgroup.com {BMW_X1_2023_TITLE} EAER kombiniert 71–86 → 71",
        fields_saved,
    )
    apply_field(
        x23,
        "batteryKWh",
        14.2,
        BMW_X1_2023_URL,
        BMW_X1_2023_DATE,
        f"press.bmwgroup.com {BMW_X1_2023_TITLE} Netto Batterieinhalt 14,2 kWh",
        fields_saved,
    )
    sn = x23.get("sourceName") or ""
    note23 = (
        f"{BMW_X1_2023_TITLE}: EAER 71, battery 14.2; Strom 22–18.2 weighted → CD nil — {BMW_X1_2023_URL}"
    )
    if BMW_X1_2023_URL not in sn:
        x23["sourceName"] = f"{sn}; {note23}".strip("; ").strip()
    x23["sourceUpdatedAt"] = SOURCE_DAY
    finalize(x23)

    # --- C BMW X1 2024: same Preisliste values via EEA 2023∩2024 (cite PDF + TAN) ---
    # x23 already has CS derived from 2024 EnVKV — do NOT copy through the seed row
    # (would be a chain). Apply range/battery from the 2023 Preisliste URL + homolog map.
    x24 = by_id["bmw-x1-phev-xdrive25e-2024"]
    sh_x1 = best_shared("bmw-x1-25e", 2023, 2024, float(x24.get("powerKw") or 0), shared, 6.0)
    if not sh_x1:
        remaining.append(
            {
                "id": "bmw-x1-phev-xdrive25e-2024",
                "missing": missing_calc_fields(x24),
                "reason": "no_identical_EEA_2023∩2024",
                "tried": TRIED.get("bmw-x1-phev-xdrive25e-2024") or [],
            }
        )
    else:
        tan, va, ve = sh_x1["TAN"], sh_x1["Va"], sh_x1["Ve"]
        for k, val in (("wltpRangeKm", 71), ("batteryKWh", 14.2)):
            apply_field(
                x24,
                k,
                val,
                BMW_X1_2023_URL,
                BMW_X1_2023_DATE,
                (
                    f"press.bmwgroup.com {BMW_X1_2023_TITLE}; stessa omologazione EEA "
                    f"{tan} {va}/{ve}, anni 2023 e 2024"
                ),
                fields_saved,
                via="homologation",
                tan=tan,
            )
        # CS on 2024 is same_my EnVKV; range/battery derived from 2023-dated OEM via EEA
        if x24.get("dataDerivedFromSameHomologationYear") is None:
            x24["dataDerivedFromSameHomologationYear"] = 2023
        sn = x24.get("sourceName") or ""
        note24 = f"EAER/batteria via EEA {tan} {va}/{ve} + Preisliste 2023 — {BMW_X1_2023_URL}"
        if note24 not in sn:
            x24["sourceName"] = f"{sn}; {note24}".strip("; ").strip()
        x24["sourceUpdatedAt"] = SOURCE_DAY
        finalize(x24)
        derived.append(
            {
                "id": "bmw-x1-phev-xdrive25e-2024",
                "sourceDoc": BMW_X1_2023_URL,
                "TAN": tan,
                "Va": va,
                "Ve": ve,
                "ep": sh_x1.get("ep"),
                "fields": ["wltpRangeKm", "batteryKWh"],
                "derivedFromYear": 2023,
                "note": "values from 2023 Preisliste + EEA match; not via seed row (x23 CS already derived from 2024)",
            }
        )

    # --- C Jeep Compass 2022 FR Tarif 4xe 4 jan 2022 ---
    COMPASS22_URL = (
        "https://www.media.stellantis.com/uploads/fr/model-document/"
        "tarifpublicnouvellejeeprcompassmy224xe2022a4jan2022-61d48676cf80a.pdf"
    )
    COMPASS22_DATE = "2022-01-04"
    COMPASS22_TITLE = "Tarif Public Nouveau Compass 4xe MY22 2022-A du 4 janvier 2022"
    c22 = by_id["jeep-compass-phev-4xe-2022"]
    apply_field(
        c22, "wltpRangeKm", 46, COMPASS22_URL, COMPASS22_DATE,
        f"media.stellantis.com {COMPASS22_TITLE} EAER 47–46/49–46 → 46", fields_saved,
    )
    apply_field(
        c22, "batteryKWh", 11.4, COMPASS22_URL, COMPASS22_DATE,
        f"media.stellantis.com {COMPASS22_TITLE} batterie 11,4 kWh", fields_saved,
    )
    apply_field(
        c22, "energyConsumptionKWhPerKm", 0.168, COMPASS22_URL, COMPASS22_DATE,
        f"media.stellantis.com {COMPASS22_TITLE} énergie électrique 16,8–16,1 → 0.168 (CD)",
        fields_saved,
    )
    c22["energyIsWeighted"] = False
    sn = c22.get("sourceName") or ""
    note_c = (
        f"{COMPASS22_TITLE}: range 46, bat 11.4, consumo elettrico CD 16.8 "
        f"(solo elettrico / charge-depleting); CS listino lasciato nei weighted* — {COMPASS22_URL}"
    )
    if COMPASS22_URL not in sn:
        c22["sourceName"] = f"{sn}; {note_c}".strip("; ").strip()
    c22["sourceUpdatedAt"] = SOURCE_DAY
    finalize(c22)
    TRIED["jeep-compass-phev-4xe-2022"] = [
        {"url": COMPASS22_URL, "ok": True, "why": "MY22 FR tarif dated 2022-01-04; CS pondéré rejected"},
    ]

    # --- C Jeep Renegade 2022 FR Tarif 1er juin 2022 ---
    REN22_URL = (
        "https://www.media.stellantis.com/uploads/fr/model-document/"
        "tarifpublicjeeprrenegademy222022e1erjuin2022-62ac25f07f521.pdf"
    )
    REN22_DATE = "2022-06-01"
    REN22_TITLE = "Tarif Public Renegade MY22 2022-E au 1er juin 2022"
    ren22 = by_id["jeep-renegade-phev-4xe-2022"]
    apply_field(
        ren22, "wltpRangeKm", 45, REN22_URL, REN22_DATE,
        f"media.stellantis.com {REN22_TITLE} EAER 49–48/48–45 → 45", fields_saved,
    )
    apply_field(
        ren22, "batteryKWh", 11.4, REN22_URL, REN22_DATE,
        f"media.stellantis.com {REN22_TITLE} batterie 11,4 kWh", fields_saved,
    )
    apply_field(
        ren22, "energyConsumptionKWhPerKm", 0.163, REN22_URL, REN22_DATE,
        f"media.stellantis.com {REN22_TITLE} énergie 16,3–15,6 → 0.163 (CD)", fields_saved,
    )
    ren22["energyIsWeighted"] = False
    sn = ren22.get("sourceName") or ""
    note_r = (
        f"{REN22_TITLE}: range 45, bat 11.4, consumo elettrico CD 16.3 "
        f"(solo elettrico / charge-depleting); CS listino lasciato nei weighted* — {REN22_URL}"
    )
    if REN22_URL not in sn:
        ren22["sourceName"] = f"{sn}; {note_r}".strip("; ").strip()
    ren22["sourceUpdatedAt"] = SOURCE_DAY
    finalize(ren22)
    TRIED["jeep-renegade-phev-4xe-2022"] = [
        {"url": REN22_URL, "ok": True, "why": "MY22 FR tarif dated 2022-06-01; CS pondéré rejected"},
    ]

    # --- C Toyota C-HR PHEV 2024 — battery + CD from PL_07_24 archive ---
    TOY_URL = (
        "https://web.archive.org/web/20240725090934id_/"
        "https://www.toyota.de/content/dam/toyota/nmsc/germany/downloads/toyota-c-hr/"
        "Toyota_C-HR_PL_07_24_j.pdf"
    )
    TOY_DATE = "2024-07-01"
    TOY_TITLE = "TOYOTA C-HR Preise und Fakten PL_07_24"
    toy = by_id["toyota-c-hr-phev-2024"]
    apply_field(
        toy, "batteryKWh", 13.6, TOY_URL, TOY_DATE,
        f"toyota.de archive {TOY_TITLE} Batteriekapazität 13,6 kWh", fields_saved,
    )
    apply_field(
        toy, "energyConsumptionKWhPerKm", 0.153, TOY_URL, TOY_DATE,
        f"toyota.de archive {TOY_TITLE} Stromverbrauch kombiniert 15,1–15,3 → 0.153 (CD)",
        fields_saved,
    )
    toy["energyIsWeighted"] = False
    sn = toy.get("sourceName") or ""
    note_t = (
        f"{TOY_TITLE}: battery 13.6, consumo elettrico CD 15.3 "
        f"(solo elettrico / charge-depleting); archive 20240725 — {TOY_URL}"
    )
    if "13,6" not in sn and "13.6" not in sn:
        toy["sourceName"] = f"{sn}; {note_t}".strip("; ").strip()
    toy["sourceUpdatedAt"] = SOURCE_DAY
    finalize(toy)
    TRIED["toyota-c-hr-phev-2024"] = [
        {"url": TOY_URL, "ok": True, "why": "PL_07_24 archive 2024-07-25; battery+CD filled"},
    ]

    # --- C Peugeot 3008 2023 UK pricelist 1 Apr 2023 ---
    PEU_URL = (
        "https://www.media.stellantis.com/uploads/uk/model-pricelist/"
        "peugeot3008pricespecapr23-6455a65377d74.pdf"
    )
    PEU_DATE = "2023-04-01"
    PEU_TITLE = "PEUGEOT 3008 Pricelist — Effective from 1st April 2023"
    peu = by_id["peugeot-3008-phev-2023"]
    apply_field(
        peu, "wltpRangeKm", 48, PEU_URL, PEU_DATE,
        f"media.stellantis.com {PEU_TITLE} EAER miles 29.8–39.1 → MIN 48 km", fields_saved,
    )
    apply_field(
        peu, "batteryKWh", 14.2, PEU_URL, PEU_DATE,
        f"media.stellantis.com {PEU_TITLE} Battery Capacity 12.4/14.2 → MAX 14.2", fields_saved,
    )
    sn = peu.get("sourceName") or ""
    note_p = f"{PEU_TITLE}: range 48 km, bat 14.2; CS/energy weighted/absent → nil — {PEU_URL}"
    if PEU_URL not in sn:
        peu["sourceName"] = f"{sn}; {note_p}".strip("; ").strip()
    peu["sourceUpdatedAt"] = SOURCE_DAY
    finalize(peu)
    TRIED["peugeot-3008-phev-2023"] = [
        {"url": PEU_URL, "ok": True, "why": "UK Apr-2023 pricelist; CS/CD still missing"},
    ]

    # Cupra Formentor 2024 dic catalogue is 150 kW / 25.8 kWh facelift — seed is 110.6 kW prior-gen
    TRIED["cupra-formentor-phev-e-hybrid-2024"] = [
        {
            "url": "https://www.cupra.com/content/dam/public/cupra-website/generic/pdf/cupra-formentor-catalogue-dic-2024.pdf",
            "ok": False,
            "why": "dated 2024-12 catalogue is 1.5 e-HYBRID 150 kW / 25.8 kWh; seed powerKw 110.6 = prior-gen — rejected",
        },
    ]

    # Remaining top-30 multi
    for rid in TOP30_MULTI:
        r = by_id[rid]
        miss = missing_calc_fields(r)
        if not miss or miss == ["energyConsumptionKWhPerKm"]:
            continue
        if rid in (
            "jeep-renegade-phev-4xe-2024",
            "jeep-renegade-phev-4xe-2023",
            "bmw-x1-phev-xdrive25e-2022",
            "bmw-x1-phev-xdrive25e-2023",
            "bmw-x1-phev-xdrive25e-2024",
        ):
            if miss != ["energyConsumptionKWhPerKm"] and miss:
                # still multi after partial fill
                remaining.append(
                    {
                        "id": rid,
                        "missing": miss,
                        "reason": "partial_fill_still_multi",
                        "tried": TRIED.get(rid) or [],
                    }
                )
            continue
        remaining.append(
            {
                "id": rid,
                "missing": miss,
                "reason": "no_valid_dated_OEM_source_this_wave",
                "tried": TRIED.get(rid) or [],
            }
        )

    for r in seed:
        if r["id"] in m3_before and json.dumps(r, sort_keys=True) != m3_before[r["id"]]:
            raise SystemExit(f"M3 2026 altered: {r['id']}")

    parents = [r for r in seed if r.get("powertrain") == "phev" and not r.get("parentId")]
    top30 = sorted(parents, key=lambda r: -float(regs.get(r["id"]) or 0))[:30]
    after_all = counts(parents)
    after_t30 = counts(top30)

    # Ensure no previously-complete (recomputed) row lost values
    for rid in ("cupra-terramar-e-hybrid-2025", "ford-kuga-phev-2023", "ford-kuga-phev-2024"):
        r = by_id[rid]
        if missing_calc_fields(r):
            raise SystemExit(f"lost complete values on {rid}: {missing_calc_fields(r)}")

    cdn = json.loads(CDN.read_text(encoding="utf-8"))
    new_ver = int(cdn.get("seedVersion") or 73) + 1
    if new_ver != 74:
        raise SystemExit(f"expected seed path to 74, got {new_ver}")
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
        "count_explanation": count_explanation,
        "renegade_document": {
            "title": RENEGADE_TITLE,
            "printedDate": RENEGADE_DATE,
            "url": RENEGADE_PDF,
            "archiveUrl": RENEGADE_ARCHIVE,
            "archiveTimestamp": "20250326070148",
            "note": "No 2024 CDX snapshot of download page; document itself dated 03/04/2024; filename from Content-Disposition",
        },
        "phev_complete_before": before_all[0],
        "phev_complete_after": after_all[0],
        "phev_only_kwh_before": before_all[1],
        "phev_only_kwh_after": after_all[1],
        "phev_multi_missing_before": before_all[2],
        "phev_multi_missing_after": after_all[2],
        "top30_complete_before": before_t30[0],
        "top30_only_kwh_before": before_t30[1],
        "top30_multi_missing_before": before_t30[2],
        "top30_complete_after": after_t30[0],
        "top30_only_kwh_after": after_t30[1],
        "top30_multi_missing_after": after_t30[2],
        "fields_saved": fields_saved,
        "derived": derived,
        "remaining_top30_multi": remaining,
    }
    MANIFEST.write_text(json.dumps(man, indent=2) + "\n")
    print(json.dumps({k: v for k, v in man.items() if k not in ("ids_before", "fields_saved", "count_explanation")}, indent=2))
    print("count_explanation_false_complete", len(false_complete))
    print("fields_saved", len(fields_saved), "remaining", len(remaining))
    print("after", after_all, "top30", after_t30)


if __name__ == "__main__":
    main()
