#!/usr/bin/env python3
"""
Seed +1 (v72→v73): top-30 IT PHEV multi-missing — fill only with dated OEM sources.

Wave 1 fills:
  Jeep Renegade 4xe 2024 — Stellantis FR Tarif MY24 3 avril 2024
    EAER combiné 50–48 → 48; batterie 11,4 kWh
  Jeep Renegade 4xe 2023 — identical EEA homologation from 2024 (existing shared map)

Other top-30 multi-missing rows: documented as remaining (no valid dated source yet).
CD unweighted never filled from weighted. M3 2026 untouched. No row removals.
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

RENEGADE_URL = "https://www.media.stellantis.com/fr-fr/download-price-lists/184"
RENEGADE_DATE = "2024-04-03"  # Tarif Public réf Renegade MY24 2024-C au 3 avril 2024

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

    before_all = counts(parents)
    before_t30 = counts(top30)

    fields_saved: list[dict] = []
    remaining: list[dict] = []

    def save(rid, field, url, date, via, tan=None):
        fields_saved.append(
            {
                "id": rid,
                "field": field,
                "value": by_id[rid].get(field),
                "url": url,
                "sourceDate": date,
                "via": via,
                **({"TAN": tan} if tan else {}),
            }
        )

    # --- Renegade 2024 ---
    r24 = by_id["jeep-renegade-phev-4xe-2024"]
    # CS already from hybrid-suv archive; add range + battery from MY24 tariff
    fs = dict(r24.get("fieldSources") or {})
    fd = dict(r24.get("fieldSourceDates") or {})
    r24["wltpRangeKm"] = 48  # prudent min of 50–48
    r24["batteryKWh"] = 11.4
    note = (
        "Jeep Renegade MY24 Tarif FR 03/04/2024 EAER combiné 50–48 → 48; batterie 11,4 kWh "
        f"(pas City) — {RENEGADE_URL} ({RENEGADE_DATE})"
    )
    for field in ("wltpRangeKm", "batteryKWh"):
        fs[field] = f"media.stellantis.com 2024 {RENEGADE_URL}"
        fd[field] = RENEGADE_DATE
        save(r24["id"], field, RENEGADE_URL, RENEGADE_DATE, "same_my")
    r24["fieldSources"] = fs
    r24["fieldSourceDates"] = fd
    sn = r24.get("sourceName") or ""
    if note not in sn:
        r24["sourceName"] = f"{sn}; {note}".strip("; ").strip()
    r24["sourceUpdatedAt"] = SOURCE_DAY
    finalize(r24)

    # --- Renegade 2023 via homologation (no chain: 2024 is same_my OEM) ---
    homolog = json.loads(HOMOLOG.read_text(encoding="utf-8"))
    shared = homolog.get("shared") or {}
    r23 = by_id["jeep-renegade-phev-4xe-2023"]
    if r24.get("dataDerivedFromSameHomologationYear") is not None:
        raise SystemExit("chain: renegade 2024 is derived")
    sh = best_shared("jeep-renegade", 2024, 2023, float(r23.get("powerKw") or 0), shared, 6.0)
    derived = []
    if not sh:
        remaining.append(
            {
                "id": "jeep-renegade-phev-4xe-2023",
                "reason": "no_identical_EEA_fingerprint_for_range_battery_copy",
            }
        )
    else:
        tan, va, ve = sh["TAN"], sh["Va"], sh["Ve"]
        fs23 = dict(r23.get("fieldSources") or {})
        fd23 = dict(r23.get("fieldSourceDates") or {})
        copied = []
        for k in ("wltpRangeKm", "batteryKWh"):
            if r24.get(k) is None:
                continue
            r23[k] = r24[k]
            fs23[k] = (
                f"media.stellantis.com 2024 {RENEGADE_URL}; stessa omologazione EEA {tan} {va}/{ve}, "
                f"anni 2023 e 2024"
            )
            fd23[k] = RENEGADE_DATE
            copied.append(k)
            save(r23["id"], k, RENEGADE_URL, RENEGADE_DATE, "homologation", tan=tan)
        r23["fieldSources"] = fs23
        r23["fieldSourceDates"] = fd23
        # keep existing derivedFrom 2024 from CS wave
        if r23.get("dataDerivedFromSameHomologationYear") is None:
            r23["dataDerivedFromSameHomologationYear"] = 2024
        note23 = (
            f"EAER/batterie MY24 via stessa omologazione EEA {tan} {va}/{ve}, anni 2023 e 2024 — "
            f"{RENEGADE_URL}"
        )
        sn23 = r23.get("sourceName") or ""
        if note23 not in sn23:
            r23["sourceName"] = f"{sn23}; {note23}".strip("; ").strip()
        r23["sourceUpdatedAt"] = SOURCE_DAY
        finalize(r23)
        derived.append(
            {
                "id": "jeep-renegade-phev-4xe-2023",
                "sourceId": "jeep-renegade-phev-4xe-2024",
                "TAN": tan,
                "Va": va,
                "Ve": ve,
                "ep": sh.get("ep"),
                "fields": copied,
                "derivedFromYear": 2024,
            }
        )

    # Remaining top-30 multi (after fills)
    reasons = {
        "jeep-compass-phev-4xe-2022": "no_identical_EEA_2022∩2024_in_homolog_map; no dated same-MY OEM doc found this wave",
        "jeep-renegade-phev-4xe-2022": "no_identical_EEA_2022∩2024_in_homolog_map; no dated same-MY OEM doc found this wave",
        "cupra-formentor-phev-e-hybrid-2024": "live_produktkatalog_only; archive.org offline / no 2024 dated snapshot available this wave",
        "mini-countryman-cooper-se-all4-2023": "no_dated_OEM_PDF_or_archive_2023_found_this_wave",
        "volvo-xc40-phev-recharge-2022": "no_dated_OEM_press_or_PDF_2022_verified_this_wave",
        "cupra-formentor-phev-e-hybrid-2023": "no_dated_OEM_source_2023; cupra-formentor-e shared fps empty for CS/range",
        "volvo-xc40-phev-recharge-2023": "no_dated_OEM_press_or_PDF_2023_verified_this_wave",
        "bmw-x1-phev-xdrive25e-2024": "CS_only_from_EnVKV; live_preisliste_rejected; no_2024_archive_of_X1_pricelist",
        "bmw-x1-phev-xdrive25e-2022": "no_identical_EEA_2022∩2024_fingerprint_in_map; no dated 2022 OEM",
        "alfa-romeo-tonale-phev-2023": "no_dated_OEM_listino_PDF_URL_verified_this_wave",
        "ford-kuga-phev-2022": "homolog_map_only_2023∩2024; no_2022∩2024_identical_fingerprint",
        "mercedes-benz-glc-phev-300-de-2024": "live_mercedes.de_is_current_MY; no_dated_2024_PDF_or_archive_this_wave",
        "toyota-c-hr-phev-2024": "CS+range_already; battery_not_on_reachable_PL_07_24_PDF_this_wave_(live_403_archive_truncated)",
        "peugeot-3008-phev-2022": "no_dated_OEM_PDF_2022_verified_this_wave",
        "renault-captur-phev-e-tech-phev-2022": "no_dated_OEM_PDF_2022_verified_this_wave",
        "bmw-x1-phev-xdrive25e-2023": "CS_from_2024_EnVKV_homolog; range/battery_source_on_2024_still_nil",
        "mercedes-benz-gle-phev-350-de-2022": "no_dated_OEM_PDF_2022_verified_this_wave",
        "peugeot-3008-phev-2023": "no_dated_OEM_PDF_2023_verified_this_wave",
        "mini-countryman-cooper-se-all4-2022": "no_dated_OEM_PDF_2022_verified_this_wave",
        "audi-q3-sportback-phev-45-tfsi-e-2024": "generic_neuwagen_URL_rejected; no_dated_model_PDF_2024",
        "audi-q3-sportback-phev-45-tfsi-e-2023": "derived_blocked_until_2024_has_valid_OEM_fields",
        "mercedes-benz-gla-phev-250-e-2023": "no_dated_OEM_PDF_2023_verified_this_wave",
        "mercedes-benz-gle-coupe-phev-350-de-2022": "no_dated_OEM_PDF_2022_verified_this_wave",
        "mercedes-benz-gla-phev-250-e-2022": "no_dated_OEM_PDF_2022_verified_this_wave",
    }

    for rid in TOP30_MULTI:
        r = by_id[rid]
        miss = missing_calc_fields(r)
        if miss == ["energyConsumptionKWhPerKm"] or not miss:
            continue  # completed enough for multi→only_kwh or complete
        if rid in ("jeep-renegade-phev-4xe-2024", "jeep-renegade-phev-4xe-2023"):
            # still missing energy only after this wave — not "remaining without source" for multi
            if miss != ["energyConsumptionKWhPerKm"]:
                remaining.append({"id": rid, "missing": miss, "reason": "partial_fill_energy_still_nil"})
            continue
        remaining.append(
            {
                "id": rid,
                "missing": miss,
                "reason": reasons.get(rid, "no_valid_dated_OEM_source_this_wave"),
            }
        )

    for r in seed:
        if r["id"] in m3_before and json.dumps(r, sort_keys=True) != m3_before[r["id"]]:
            raise SystemExit(f"M3 2026 altered: {r['id']}")

    parents = [r for r in seed if r.get("powertrain") == "phev" and not r.get("parentId")]
    top30 = sorted(parents, key=lambda r: -float(regs.get(r["id"]) or 0))[:30]
    after_all = counts(parents)
    after_t30 = counts(top30)

    cdn = json.loads(CDN.read_text(encoding="utf-8"))
    new_ver = int(cdn.get("seedVersion") or 72) + 1
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
    print(json.dumps({k: v for k, v in man.items() if k not in ("ids_before", "fields_saved")}, indent=2))
    print("fields_saved", len(fields_saved), "remaining", len(remaining))


if __name__ == "__main__":
    main()
