#!/usr/bin/env python3
"""
PHEV wave2 batch2 CHANGES NEEDED corr2 (seed 85→86).

- DS7 2024: CS → MAX across E-TENSE 225/300/360 = 0.082 (not 225-only 0.071)
- BYD Seal U 2024: sourceDate → PDF CreationDate 2024-05-23 (metadata), not invented 05-01
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

DS7_DE_MAR24 = (
    "https://www.media.stellantis.com/uploads/de/model-document/"
    "preisliste_ds_7_my42_25marz2024-6616563ea3f2c.pdf"
)
BYD_0524 = (
    "https://www.byd.com/material/byd-site/eu/pdfs/seal-u-dm-i/"
    "Seal-U-DM-i-0524-BPS-EN-2car-V4-web.pdf"
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


def scrub_source(row: dict, drop_substrings: list[str], append: str) -> None:
    parts = [p.strip() for p in (row.get("sourceName") or "").split(";") if p.strip()]
    keep = []
    for p in parts:
        low = p.lower()
        if any(s.lower() in low for s in drop_substrings):
            continue
        keep.append(p)
    keep.append(append)
    seen: set[str] = set()
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
    if int(cdn.get("seedVersion") or 0) != 85:
        raise SystemExit(f"expected seed 85 baseline, got {cdn.get('seedVersion')}")

    old_man = json.loads(MANIFEST.read_text(encoding="utf-8"))
    inv = json.loads(INVENTORY.read_text(encoding="utf-8"))
    batch2_ids = [x["id"] for x in inv["batch2_candidates"]]
    lotto = set(batch2_ids)

    batch1_inv = json.loads(
        (CACHE / "catalog_phev_wave2_batch1_inventory.json").read_text(encoding="utf-8")
    )
    batch1_ids = {x["id"] for x in batch1_inv["batch1_candidates"]} | {
        "bmw-330e-phev-2024",
        "jeep-grand-cherokee-4xe-2023",
    }
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
    outside_before = {
        r["id"]: json.dumps(r, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        for r in seed
        if r["id"] not in lotto
    }

    # Freeze OK rows (calc + provenance) — must not change
    freeze_ids = [
        "bmw-x3-phev-xdrive30e-2024",
        "bmw-x1-phev-xdrive30e-2023",
        "citroen-c5-aircross-phev-2022",
        "kia-sportage-phev-2023",
        "kia-sportage-phev-2024",
        "audi-q5-sportback-phev-50-tfsi-e-2024",
        "bmw-serie-2-active-tourer-225e-xdrive-2023",
    ]
    freeze = {
        i: json.dumps(
            {
                k: by_id[i].get(k)
                for k in (
                    "fuelConsumptionLPerKm",
                    "energyConsumptionKWhPerKm",
                    "wltpRangeKm",
                    "batteryKWh",
                    "fieldSources",
                    "fieldSourceDates",
                )
            },
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        for i in freeze_ids
    }

    changed_fields: list[dict] = []

    # --- DS7 2024: CS MAX across variants 225/300/360 ------------------------------------
    ds7 = by_id["ds-7-phev-e-tense-2024"]
    cite_ds7_bat = (
        "DS Automobiles DE Preisliste DS 7 MY42 Stand März 2024 / 25. März 2024 — "
        "E-TENSE 225 / 4x4 300 / 4x4 360: Kapazität Hochvolt Batterie Netto (Richtwert) 13 "
        f"(identical across PHEV columns) {DS7_DE_MAR24}"
    )
    cite_ds7_cs = (
        "DS Automobiles DE Preisliste DS 7 MY42 Stand März 2024 / 25. März 2024 — aggregate "
        "seed row (trim E-TENSE, powerKw 139.9): Kraftstoffverbrauch bei entladener Batterie "
        "WLTP across columns E-TENSE 225 = 7,0–7,1; 4x4 300 = 6,7–6,8; 4x4 360 = 8,2 → "
        f"prudent MAX 8.2 L/100 = 0.082 (not 225-only) {DS7_DE_MAR24}"
    )
    set_field(ds7, "batteryKWh", 13.0, cite_ds7_bat, "2024-03-25")
    set_field(ds7, "fuelConsumptionLPerKm", 0.082, cite_ds7_cs, "2024-03-25")
    scrub_source(
        ds7,
        drop_substrings=["wave2-batch2-corr1 DS7", "CS 0.071", "E-TENSE 225 DE listino"],
        append=(
            "wave2-batch2-corr2 DS7 aggregate E-TENSE DE listino 2024-03-25 "
            f"net 13 / CS MAX 0.082 across 225/300/360 — {DS7_DE_MAR24}"
        ),
    )
    ds7["sourceUpdatedAt"] = SOURCE_DAY
    finalize(ds7)
    changed_fields.append(
        {
            "id": ds7["id"],
            "field": "fuelConsumptionLPerKm",
            "value": 0.082,
            "was": 0.071,
            "url": DS7_DE_MAR24,
            "sourceDate": "2024-03-25",
            "note": "MAX across 225/300/360 discharged columns",
        }
    )
    changed_fields.append(
        {
            "id": ds7["id"],
            "field": "batteryKWh",
            "value": 13.0,
            "url": DS7_DE_MAR24,
            "sourceDate": "2024-03-25",
            "note": "Netto 13 identical on all PHEV columns; cite refreshed",
        }
    )

    # --- BYD: real PDF CreationDate 2024-05-23 -------------------------------------------
    byd = by_id["byd-seal-u-phev-dm-i-2024"]
    cite_byd = (
        "BYD Europe Seal U DM-i specification sheet 0524-BPS-EN-V4 "
        "(filename Seal-U-DM-i-0524…); data da metadati PDF CreationDate "
        "D:20240523100830+08'00' → 2024-05-23 — Boost+Design: Fuel Consumption - combined "
        "MAX 7.4 L/100 (Design) → 0.074; Electric range - combined MIN 70 km (Design); "
        "Battery capacity 18.3 kWh unlabeled → battery nil; Electric consumption - combined "
        f"not pure-CD labeled → CD nil {BYD_0524}"
    )
    set_field(byd, "fuelConsumptionLPerKm", 0.074, cite_byd, "2024-05-23")
    set_field(byd, "wltpRangeKm", 70, cite_byd, "2024-05-23")
    scrub_source(
        byd,
        drop_substrings=["wave2-batch2-corr1 Seal U", "0524 BPS CS"],
        append=(
            "wave2-batch2-corr2 Seal U DM-i 0524 BPS CreationDate 2024-05-23 "
            f"CS 0.074 / EAER 70 — {BYD_0524}"
        ),
    )
    byd["sourceUpdatedAt"] = SOURCE_DAY
    finalize(byd)
    changed_fields.append(
        {
            "id": byd["id"],
            "field": "fuelConsumptionLPerKm",
            "value": 0.074,
            "url": BYD_0524,
            "sourceDate": "2024-05-23",
            "note": "date from PDF CreationDate metadata (was invented 2024-05-01)",
        }
    )
    changed_fields.append(
        {
            "id": byd["id"],
            "field": "wltpRangeKm",
            "value": 70,
            "url": BYD_0524,
            "sourceDate": "2024-05-23",
            "note": "date from PDF CreationDate metadata",
        }
    )

    # Freeze check
    for i, blob in freeze.items():
        now = json.dumps(
            {
                k: by_id[i].get(k)
                for k in (
                    "fuelConsumptionLPerKm",
                    "energyConsumptionKWhPerKm",
                    "wltpRangeKm",
                    "batteryKWh",
                    "fieldSources",
                    "fieldSourceDates",
                )
            },
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        if now != blob:
            raise SystemExit(f"frozen row mutated: {i}")

    # Rebuild manifest outcomes from previous + patch DS7/BYD partials
    partial = []
    for entry in old_man.get("partial") or []:
        e = dict(entry)
        if e["id"] == "ds-7-phev-e-tense-2024":
            e["filled"] = {"batteryKWh": 13.0, "fuelConsumptionLPerKm": 0.082}
            e["left_nil"] = ["energyConsumptionKWhPerKm", "wltpRangeKm"]
            e["note"] = (
                "corr2: CS MAX 0.082 across 225/300/360 discharged columns on aggregate row; "
                "net 13 identical; no combined EAER"
            )
        if e["id"] == "byd-seal-u-phev-dm-i-2024":
            e["note"] = (
                "corr2: sourceDate 2024-05-23 from PDF CreationDate metadata; "
                "battery capacity unlabeled 18.3; pure CD unlabeled"
            )
        partial.append(e)

    left_nil = old_man.get("left_nil") or []
    completed = old_man.get("completed") or []
    homolog_reuse = old_man.get("homolog_reuse") or []

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

    battery_convention = dict(old_man.get("battery_convention") or {})
    this_pass = list(battery_convention.get("thisPass") or [])
    # refresh DS7 note
    refreshed = []
    for e in this_pass:
        if e.get("id") == "ds-7-phev-e-tense-2024":
            refreshed.append(
                {
                    "id": "ds-7-phev-e-tense-2024",
                    "batteryKWh": 13.0,
                    "note": "Kapazität Hochvolt Batterie Netto (Richtwert) 13 — all PHEV columns",
                }
            )
        else:
            refreshed.append(e)
    battery_convention["thisPass"] = refreshed
    battery_convention["catalogConvention"] = "net/usable"

    new_ver = 86
    cdn["seedVersion"] = new_ver
    cdn["prevSeedVersion"] = 85
    cdn["rows"] = len(seed)
    payload = json.dumps(seed, separators=(",", ":"), ensure_ascii=False)
    cdn["bytes"] = len(payload.encode())
    cdn["updatedAt"] = datetime.now(timezone.utc).isoformat()
    cdn["note"] = (
        "seedVersion 86: PHEV wave2 batch2 corr2 — DS7 aggregate CS MAX 0.082 across "
        "225/300/360; BYD Seal U sourceDate from PDF CreationDate 2024-05-23; "
        "api/static sync deferred at seed 77"
    )
    SEED.write_text(payload)
    CDN.write_text(json.dumps(cdn, indent=2) + "\n")
    if SEED.stat().st_size != cdn["bytes"]:
        raise SystemExit(f"CDN bytes mismatch {cdn['bytes']} vs {SEED.stat().st_size}")

    man = {
        "seedVersion": new_ver,
        "prevSeedVersion": 85,
        "ids_before": ids_before,
        "batch2_ids": batch2_ids,
        "completed": completed,
        "partial": partial,
        "extras": [],
        "homolog_reuse": homolog_reuse,
        "left_nil": left_nil,
        "changed_fields": (old_man.get("changed_fields") or []) + changed_fields,
        "corr2_changed_fields": changed_fields,
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
            "corr2: DS7 CS MAX 0.082 across variants on aggregate row",
            "corr2: BYD sourceDate 2024-05-23 from PDF CreationDate metadata",
            "corr2: checker homolog best_shared_exact fail-closed when family/fingerprint missing",
        ],
        "prKind": "research-corr2",
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
                "corr2_changed_fields": changed_fields,
                "non_phev_tech_sha": non_phev_sha,
            },
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
