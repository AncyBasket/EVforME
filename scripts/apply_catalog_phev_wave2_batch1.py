#!/usr/bin/env python3
"""
PHEV wave2 batch1 (seed 77→78).

Batch = top ~40 incomplete IT/EU PHEV by EEA diffusion rank (see inventory).
Only official OEM / identical-EEA homolog fills. No estimates. No api/ touches.
M3 IT2026 + non-PHEV rows byte-identical. No chain derivation.
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
from lib.phev_manus_v76_validate import (  # noqa: E402
    has_pure_energy_label,
    missing_calc_fields,
)

SEED = REPO / "EVforME?" / "Data" / "vehicles.seed.quality.json"
CDN = REPO / "EVforME?" / "Data" / "catalog_cdn.json"
CACHE = REPO / "scripts" / "cache" / "eea"
HOMOLOG = CACHE / "catalog_phev_homologation_map.json"
INVENTORY = CACHE / "catalog_phev_wave2_batch1_inventory.json"
MANIFEST = CACHE / "catalog_phev_wave2_batch1_manifest.json"
SOURCE_DAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")

FORD_TECH = (
    "https://www.ford.de/content/dam/guxeu/de/documents/price-list/cars/new-kuga/"
    "Technische_Daten_des_Ford_Kuga.pdf"
)
FORD_PREIS = (
    "https://www.ford.de/content/dam/guxeu/de/documents/price-list/cars/new-kuga/"
    "der-Ford-Kuga_gültig_ab_01_05_2024.pdf"
)
BMW_330E_PRESS = "https://www.press.bmwgroup.com/global/article/attachment/T0442333EN/620071"
JEEP_HYBRID_ARCH = "https://web.archive.org/web/20240620055110/https://www.jeep.de/hybrid-suv"

COPY_FIELDS = (
    "fuelConsumptionLPerKm",
    "energyConsumptionKWhPerKm",
    "energyIsWeighted",
    "weightedFuelConsumptionLPerKm",
    "weightedEnergyConsumptionKWhPerKm",
    "wltpRangeKm",
    "batteryKWh",
)


def fp_tuple(r: dict) -> tuple:
    return (
        (r.get("TAN") or "").upper(),
        r.get("Va") or "",
        r.get("Ve") or "",
        r.get("ep"),
        r.get("ec"),
        r.get("m"),
        r.get("Mt"),
        r.get("Ew"),
        r.get("Fc"),
    )


def best_shared(family: str, src_year: int, dst_year: int, dst_power_kw: float, shared: dict) -> dict | None:
    cands = []
    for sh in shared.get(family) or []:
        years = {int(y): n for y, n in (sh.get("years") or {}).items()}
        if src_year not in years or dst_year not in years:
            continue
        ep = sh.get("ep")
        if ep is None or abs(float(ep) - float(dst_power_kw)) > 20.0:
            continue
        if not (sh.get("TAN") or "").strip():
            continue
        score = float(years[src_year]) + float(years[dst_year])
        cands.append((score, sh))
    if not cands:
        return None
    cands.sort(key=lambda x: -x[0])
    return cands[0][1]


def finalize(row: dict) -> None:
    miss = missing_calc_fields(row)
    row["missingCalcFields"] = miss
    row["catalogDataIncomplete"] = bool(miss)
    score, ev = assess_confidence(row)
    row["confidenceScore"] = score
    row["confidenceEvidence"] = ev
    row["confidencePolicyVersion"] = POLICY_VERSION


def set_field_source(row: dict, field: str, cite: str, date: str) -> None:
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


def main() -> None:
    seed = json.loads(SEED.read_text(encoding="utf-8"))
    by_id = {r["id"]: r for r in seed}
    ids_before = [r["id"] for r in seed]
    assert len(seed) == 6977, len(seed)

    m3_before = {
        r["id"]: json.dumps(r, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        for r in seed
        if r["id"].startswith("tesla-model-3") and r.get("year") == 2026
    }
    assert len(m3_before) == 4, len(m3_before)

    non_phev_before = tech_blob([r for r in seed if r.get("powertrain") != "phev"])
    non_phev_sha_before = hashlib.sha256(non_phev_before.encode()).hexdigest()

    inv = json.loads(INVENTORY.read_text(encoding="utf-8"))
    batch1_ids = [x["id"] for x in inv["batch1_candidates"]]
    assert len(batch1_ids) == 40, len(batch1_ids)

    homolog = json.loads(HOMOLOG.read_text(encoding="utf-8"))
    shared = homolog.get("shared") or {}

    completed: list[dict] = []
    partial: list[dict] = []
    homolog_reuse: list[dict] = []
    left_nil: list[dict] = []

    # --- 1) Ford Kuga 2022 COMPLETE via identical EEA homolog from MY2024 (no chain) ---
    src = by_id["ford-kuga-phev-2024"]
    dst = by_id["ford-kuga-phev-2022"]
    if src.get("catalogDataIncomplete"):
        raise SystemExit("ford-kuga-2024 incomplete")
    if src.get("dataDerivedFromSameHomologationYear") is not None:
        raise SystemExit("chain: ford-kuga-2024 is derived")
    if dst.get("dataDerivedFromSameHomologationYear") is not None:
        raise SystemExit("dst already derived")
    cd_cite = (src.get("fieldSources") or {}).get("energyConsumptionKWhPerKm") or ""
    if not has_pure_energy_label(cd_cite):
        raise SystemExit("donor CD cite lacks pure-electric label")
    sh = best_shared("ford-kuga", 2024, 2022, float(dst.get("powerKw") or 0), shared)
    if not sh:
        raise SystemExit("no identical homolog ford-kuga 2024→2022")
    for f in COPY_FIELDS:
        dst[f] = src[f]
    dst["energyIsWeighted"] = False
    dst["dataDerivedFromSameHomologationYear"] = 2024
    dst["sourceUpdatedAt"] = SOURCE_DAY
    tan, va, ve = sh["TAN"], sh["Va"], sh["Ve"]
    for field, value, note in (
        (
            "fuelConsumptionLPerKm",
            dst["fuelConsumptionLPerKm"],
            f"CS max 6,1 L/100 via stessa omologazione EEA {tan} {va}/{ve}; OEM MY2024 {FORD_TECH}",
        ),
        (
            "energyConsumptionKWhPerKm",
            dst["energyConsumptionKWhPerKm"],
            f"Stromverbrauch bei rein elektrischem Betrieb kombiniert 20,9–18,4 → 0.209 "
            f"(solo elettrico / charge-depleting) via stessa omologazione EEA {tan} {va}/{ve}; "
            f"OEM MY2024 {FORD_TECH}",
        ),
        (
            "wltpRangeKm",
            dst["wltpRangeKm"],
            f"EAER combinato MIN 60 km (60–68) via stessa omologazione EEA {tan} {va}/{ve}; "
            f"OEM MY2024 {FORD_TECH}",
        ),
        (
            "batteryKWh",
            dst["batteryKWh"],
            f"Batterie 14,4 kWh installiert via stessa omologazione EEA {tan} {va}/{ve}; "
            f"OEM MY2024 {FORD_TECH}",
        ),
    ):
        set_field_source(dst, field, note, "2024-05-01")
    dst["sourceName"] = (
        f"Ford DE EnVKV Kuga 2,5 l Duratec PHEV via stessa omologazione EEA {tan} {va}/{ve}, "
        f"anni 2022 e 2024: Kraftstoffverbrauch bei entladener Batterie 6,1–5,2 L/100; "
        f"Stromverbrauch bei rein elektrischem Betrieb kombiniert 20,9–18,4 kWh/100 "
        f"(solo elettrico / charge-depleting); EAER 60–68 km; Batterie 14,4 kWh — "
        f"{FORD_TECH}; Preisliste MY24.5 ab 01.05.2024 {FORD_PREIS}"
    )
    finalize(dst)
    if dst["catalogDataIncomplete"]:
        raise SystemExit(f"kuga 2022 still incomplete: {dst['missingCalcFields']}")
    completed.append(
        {
            "id": dst["id"],
            "kind": "homolog_complete",
            "fields": {
                "fuelConsumptionLPerKm": dst["fuelConsumptionLPerKm"],
                "energyConsumptionKWhPerKm": dst["energyConsumptionKWhPerKm"],
                "wltpRangeKm": dst["wltpRangeKm"],
                "batteryKWh": dst["batteryKWh"],
            },
            "sources": dst["fieldSources"],
            "sourceDates": dst["fieldSourceDates"],
            "TAN": tan,
            "Va": va,
            "Ve": ve,
            "derivedFromYear": 2024,
            "sourceId": "ford-kuga-phev-2024",
        }
    )
    homolog_reuse.append(completed[-1])

    # --- 2) BMW 330e 2024: battery usable 19.5 kWh (press 2024-05-29); CD stays nil ---
    b330 = by_id["bmw-330e-phev-2024"]
    if b330.get("batteryKWh") is None:
        b330["batteryKWh"] = 19.5
        set_field_source(
            b330,
            "batteryKWh",
            "press.bmwgroup.com new BMW 330e: high-voltage battery with 19.5 kWh of usable energy "
            f"(ab 05/2024) {BMW_330E_PRESS}",
            "2024-05-29",
        )
        b330["sourceUpdatedAt"] = SOURCE_DAY
        b330["sourceName"] = (
            f"{b330.get('sourceName')}; wave2-batch1: batteryKWh=19.5 usable — {BMW_330E_PRESS}"
        )
        finalize(b330)
        partial.append(
            {
                "id": b330["id"],
                "filled": {"batteryKWh": 19.5},
                "stillMissing": b330["missingCalcFields"],
                "reason_remaining": "OEM press labels Stromverbrauch as weighted only; no pure-electric kWh",
                "sources": {"batteryKWh": b330["fieldSources"]["batteryKWh"]},
                "sourceDates": {"batteryKWh": "2024-05-29"},
            }
        )

    # --- 3) Jeep Compass 2022: CS only via identical EEA from MY2024 (donor has CS, no pure CD) ---
    c24 = by_id["jeep-compass-phev-4xe-2024"]
    c22 = by_id["jeep-compass-phev-4xe-2022"]
    if c24.get("fuelConsumptionLPerKm") is None:
        raise SystemExit("compass 2024 missing CS donor")
    if c24.get("dataDerivedFromSameHomologationYear") is not None:
        raise SystemExit("chain: compass 2024 derived")
    sh_c = best_shared("jeep-compass", 2024, 2022, float(c22.get("powerKw") or 0), shared)
    if not sh_c:
        raise SystemExit("no identical homolog jeep-compass 2024→2022")
    if c22.get("fuelConsumptionLPerKm") is None:
        c22["fuelConsumptionLPerKm"] = c24["fuelConsumptionLPerKm"]
        c22["dataDerivedFromSameHomologationYear"] = 2024
        set_field_source(
            c22,
            "fuelConsumptionLPerKm",
            "jeep.de CS bei entladener Batterie 6,9–7,6 → 0.076 via stessa omologazione EEA "
            f"{sh_c['TAN']} {sh_c['Va']}/{sh_c['Ve']}, anni 2022 e 2024; {JEEP_HYBRID_ARCH}",
            "2024-06-20",
        )
        c22["sourceUpdatedAt"] = SOURCE_DAY
        c22["sourceName"] = (
            f"{c22.get('sourceName')}; wave2-batch1: CS via stessa omologazione EEA "
            f"{sh_c['TAN']} {sh_c['Va']}/{sh_c['Ve']} da MY2024"
        )
        finalize(c22)
        partial.append(
            {
                "id": c22["id"],
                "filled": {"fuelConsumptionLPerKm": c22["fuelConsumptionLPerKm"]},
                "stillMissing": c22["missingCalcFields"],
                "reason_remaining": "OEM listini place kWh with weighted CO2/L/100 (no pure-CD label)",
                "sources": {"fuelConsumptionLPerKm": c22["fieldSources"]["fuelConsumptionLPerKm"]},
                "sourceDates": {"fuelConsumptionLPerKm": "2024-06-20"},
                "TAN": sh_c["TAN"],
                "derivedFromYear": 2024,
            }
        )
        homolog_reuse.append(partial[-1])

    # --- 4) Jeep Renegade 2022: CS only via identical EEA from MY2024 ---
    r24 = by_id["jeep-renegade-phev-4xe-2024"]
    r22 = by_id["jeep-renegade-phev-4xe-2022"]
    if r24.get("fuelConsumptionLPerKm") is None:
        raise SystemExit("renegade 2024 missing CS donor")
    if r24.get("dataDerivedFromSameHomologationYear") is not None:
        raise SystemExit("chain: renegade 2024 derived")
    sh_r = best_shared("jeep-renegade", 2024, 2022, float(r22.get("powerKw") or 0), shared)
    if not sh_r:
        raise SystemExit("no identical homolog jeep-renegade 2024→2022")
    if r22.get("fuelConsumptionLPerKm") is None:
        r22["fuelConsumptionLPerKm"] = r24["fuelConsumptionLPerKm"]
        r22["dataDerivedFromSameHomologationYear"] = 2024
        set_field_source(
            r22,
            "fuelConsumptionLPerKm",
            "jeep.de CS bei entladener Batterie 6,9–7,5 → 0.075 via stessa omologazione EEA "
            f"{sh_r['TAN']} {sh_r['Va']}/{sh_r['Ve']}, anni 2022 e 2024; {JEEP_HYBRID_ARCH}",
            "2024-06-20",
        )
        r22["sourceUpdatedAt"] = SOURCE_DAY
        r22["sourceName"] = (
            f"{r22.get('sourceName')}; wave2-batch1: CS via stessa omologazione EEA "
            f"{sh_r['TAN']} {sh_r['Va']}/{sh_r['Ve']} da MY2024"
        )
        finalize(r22)
        partial.append(
            {
                "id": r22["id"],
                "filled": {"fuelConsumptionLPerKm": r22["fuelConsumptionLPerKm"]},
                "stillMissing": r22["missingCalcFields"],
                "reason_remaining": "OEM listini place kWh with weighted CO2/L/100 (no pure-CD label)",
                "sources": {"fuelConsumptionLPerKm": r22["fieldSources"]["fuelConsumptionLPerKm"]},
                "sourceDates": {"fuelConsumptionLPerKm": "2024-06-20"},
                "TAN": sh_r["TAN"],
                "derivedFromYear": 2024,
            }
        )
        homolog_reuse.append(partial[-1])

    touched = {c["id"] for c in completed} | {p["id"] for p in partial}
    for rid in batch1_ids:
        if rid in touched:
            continue
        row = by_id[rid]
        miss = missing_calc_fields(row)
        left_nil.append(
            {
                "id": rid,
                "brand": row.get("brand"),
                "model": row.get("model"),
                "year": row.get("year"),
                "market": row.get("market"),
                "missing": miss,
                "reason": (
                    "no same-MY OEM document with dated pure-electric (rein elektrisch / "
                    "charge-depleting) kWh and/or CS+EAER+battery verified this wave; "
                    "weighted-only kWh kept in weighted* / left nil for CD"
                ),
            }
        )

    # invariants
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

    cdn = json.loads(CDN.read_text(encoding="utf-8"))
    if int(cdn.get("seedVersion") or 0) != 77:
        raise SystemExit(f"expected seed 77 base, got {cdn.get('seedVersion')}")
    new_ver = 78
    cdn["seedVersion"] = new_ver
    cdn["rows"] = len(seed)
    # Preserve explicit JSON nulls (same convention as seed 77 on main).
    payload = json.dumps(seed, separators=(",", ":"), ensure_ascii=False)
    cdn["bytes"] = len(payload.encode())
    cdn["updatedAt"] = datetime.now(timezone.utc).isoformat()
    cdn["note"] = (
        "seedVersion 78: PHEV wave2 batch1 — official/homolog fills on top-40 incomplete; "
        "confidence policy v2 unchanged"
    )

    SEED.write_text(payload)
    CDN.write_text(json.dumps(cdn, indent=2) + "\n")

    man = {
        "seedVersion": new_ver,
        "prevSeedVersion": 77,
        "ids_before": ids_before,
        "batch1_ids": batch1_ids,
        "completed": completed,
        "partial": partial,
        "homolog_reuse": homolog_reuse,
        "left_nil": left_nil,
        "non_phev_tech_sha": non_phev_sha_after,
        "m3_ids": sorted(m3_before),
        "sourceDay": SOURCE_DAY,
    }
    MANIFEST.write_text(json.dumps(man, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({
        "seedVersion": new_ver,
        "completed": len(completed),
        "partial": len(partial),
        "left_nil": len(left_nil),
        "homolog_reuse": len(homolog_reuse),
        "non_phev_tech_sha": non_phev_sha_after,
    }, indent=2))


if __name__ == "__main__":
    main()
