#!/usr/bin/env python3
"""
PHEV wave2 batch1 RESEARCH correction pass 4 (seed 82→83).

- peugeot-3008-phev-2023: EAER 29.8 mi → floor(29.8×1.609344)=47 km (was 48)
- battery_convention: peugeot-3008-phev-2023 → nil (aggregate covers multiple variants)
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
from catalog_confidence import POLICY_VERSION, assess_confidence  # noqa: E402
from check_catalog_phev_wave2_batch1 import (  # noqa: E402
    cite_dating_ok,
    is_generic_url,
    miles_to_km_floor,
    urls_in,
)
from lib.phev_manus_v76_validate import missing_calc_fields  # noqa: E402

SEED = REPO / "EVforME?" / "Data" / "vehicles.seed.quality.json"
CDN = REPO / "EVforME?" / "Data" / "catalog_cdn.json"
CACHE = REPO / "scripts" / "cache" / "eea"
INVENTORY = CACHE / "catalog_phev_wave2_batch1_inventory.json"
MANIFEST = CACHE / "catalog_phev_wave2_batch1_manifest.json"
SOURCE_DAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")

PEUGEOT_UK_APR23 = (
    "https://www.media.stellantis.com/uploads/uk/model-pricelist/"
    "peugeot3008pricespecapr23-6455a65377d74.pdf"
)

CALC_FIELDS = (
    "fuelConsumptionLPerKm",
    "energyConsumptionKWhPerKm",
    "wltpRangeKm",
    "batteryKWh",
)

HYBRID_180_MIN_MI = 29.8
HYBRID_180_MIN_KM = miles_to_km_floor(HYBRID_180_MIN_MI)  # 47


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


def rewrite_source_name(row: dict, *, drop_substrings: list[str], append: str) -> None:
    sn = row.get("sourceName") or ""
    parts = [p.strip() for p in sn.split(";") if p.strip()]
    kept = []
    for p in parts:
        low = p.lower()
        if any(d.lower() in low for d in drop_substrings):
            continue
        kept.append(p)
    if append and append not in "; ".join(kept):
        kept.append(append)
    if kept:
        row["sourceName"] = "; ".join(kept)
    else:
        row.pop("sourceName", None)


def main() -> None:
    if HYBRID_180_MIN_KM != 47:
        raise SystemExit(f"floor(29.8 mi) expected 47 got {HYBRID_180_MIN_KM}")
    if math.floor(29.8 * 1.609344) != 47:
        raise SystemExit("sanity: 29.8*1.609344 floor must be 47")

    seed = json.loads(SEED.read_text(encoding="utf-8"))
    by_id = {r["id"]: r for r in seed}
    ids_before = [r["id"] for r in seed]
    assert len(seed) == 6977

    cdn = json.loads(CDN.read_text(encoding="utf-8"))
    if int(cdn.get("seedVersion") or 0) != 82:
        raise SystemExit(f"expected seed 82 baseline, got {cdn.get('seedVersion')}")

    m3_before = {
        r["id"]: json.dumps(r, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        for r in seed
        if r["id"].startswith("tesla-model-3") and r.get("year") == 2026
    }
    assert len(m3_before) == 4
    non_phev_sha_before = hashlib.sha256(
        tech_blob([r for r in seed if r.get("powertrain") != "phev"]).encode()
    ).hexdigest()
    if non_phev_sha_before != "6b9038232bc51daabc9e259fc0dab170f787984d4dfb8f597e309fe50155b4dc":
        raise SystemExit(f"non-PHEV SHA unexpected: {non_phev_sha_before}")

    inv = json.loads(INVENTORY.read_text(encoding="utf-8"))
    batch1_ids = [x["id"] for x in inv["batch1_candidates"]]
    assert len(batch1_ids) == 40
    lotto = set(batch1_ids)
    prev_man = json.loads(MANIFEST.read_text(encoding="utf-8"))
    outside_before = {
        r["id"]: json.dumps(r, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        for r in seed
        if r["id"] not in lotto
    }

    changed_fields: list[dict] = []

    # --- Peugeot 3008 2023: floor miles → 47 km -----------------------------------------
    p23 = by_id["peugeot-3008-phev-2023"]
    if p23.get("batteryKWh") is not None:
        raise SystemExit(f"Peugeot 2023 battery unexpected baseline: {p23.get('batteryKWh')}")
    if int(p23.get("wltpRangeKm") or 0) != 48:
        raise SystemExit(f"Peugeot 2023 range unexpected baseline: {p23.get('wltpRangeKm')}")

    p23["wltpRangeKm"] = HYBRID_180_MIN_KM
    range_cite = (
        "media.stellantis.com PEUGEOT 3008 Pricelist — Effective from 1st April 2023 — "
        "aggregate IT PHEV row (trim PHEV, not clearly HYBRID 225): EAER miles from "
        f"PLUG-IN HYBRID 180 column 29.8–39.1 → MIN floor({HYBRID_180_MIN_MI} mi×1.609344)="
        f"{HYBRID_180_MIN_KM} km (prudent min; never round up to 48). "
        f"Usable 10.4 is only on HYBRID 225/HYBRID4 (180=TBC) → battery nil. {PEUGEOT_UK_APR23}"
    )
    set_field_source(p23, "wltpRangeKm", range_cite, "2023-04-01")
    rewrite_source_name(
        p23,
        drop_substrings=[
            "EAER 48 km from HYBRID 180",
            "aggregate PHEV — EAER 48",
            "range 48 km",
        ],
        append=(
            "PEUGEOT 3008 UK Apr 2023 (Effective 1st April 2023): aggregate PHEV — "
            f"EAER {HYBRID_180_MIN_KM} km = floor(HYBRID 180 column {HYBRID_180_MIN_MI} mi); "
            "battery nil (Usable 10.4 only on HYBRID 225/HYBRID4; seed covers multiple variants) "
            f"— {PEUGEOT_UK_APR23}"
        ),
    )
    # Scrub residual "48 km" / "→ 48" from older segments if still present
    sn = p23.get("sourceName") or ""
    sn = re.sub(r"\bEAER 48 km\b", f"EAER {HYBRID_180_MIN_KM} km", sn)
    sn = re.sub(r"\brange 48 km\b", f"range {HYBRID_180_MIN_KM} km", sn)
    p23["sourceName"] = sn
    p23["sourceUpdatedAt"] = SOURCE_DAY
    finalize(p23)
    changed_fields.append(
        {
            "id": p23["id"],
            "field": "wltpRangeKm",
            "value": HYBRID_180_MIN_KM,
            "prev": 48,
            "url": PEUGEOT_UK_APR23,
            "sourceDate": "2023-04-01",
            "note": f"HYBRID 180 column min {HYBRID_180_MIN_MI} mi → floor = {HYBRID_180_MIN_KM} km",
        }
    )

    # --- Manifest rebuild ---------------------------------------------------------------
    completed = list(prev_man.get("completed") or [])
    partial = list(prev_man.get("partial") or [])
    homolog_reuse = list(prev_man.get("homolog_reuse") or [])
    left_nil = list(prev_man.get("left_nil") or [])
    extras = list(prev_man.get("extras") or [])

    def drop_id(bucket: list, rid: str) -> list:
        return [e for e in bucket if e.get("id") != rid]

    left_nil = drop_id(left_nil, "peugeot-3008-phev-2023")
    left_nil.append(
        nil_entry(
            p23,
            reason=(
                "CS+CD nil; battery nil: seed is aggregate IT PHEV (trim PHEV, EEA n=1604) — "
                "covers multiple UK Apr 2023 variants, not clearly HYBRID 225. Usable 10.4 is "
                "only on HYBRID 225 / HYBRID4 (HYBRID 180=TBC). EAER "
                f"{HYBRID_180_MIN_KM} km = floor({HYBRID_180_MIN_MI} mi×1.609344) from HYBRID 180 "
                "column (prudent min; never round up)."
            ),
            consulted=[
                {
                    "url": PEUGEOT_UK_APR23,
                    "sourceDate": "2023-04-01",
                    "reject_for": "battery — Usable 10.4 is HYBRID 225/300 only; seed covers multiple variants",
                    "accepted_for": (
                        f"wltpRangeKm {HYBRID_180_MIN_KM} = floor(HYBRID 180 EAER {HYBRID_180_MIN_MI} mi)"
                    ),
                }
            ],
            field_reasons={
                "batteryKWh": (
                    "aggregate / multi-variant seed row — Usable 10.4 printed only on "
                    "HYBRID 225 / HYBRID4; HYBRID 180 Usable=TBC"
                ),
                "fuelConsumptionLPerKm": "Combined L/100 weighted only",
                "energyConsumptionKWhPerKm": "electric Combined weighted only",
            },
        )
    )

    covered = (
        {e["id"] for e in completed}
        | {e["id"] for e in partial}
        | {e["id"] for e in homolog_reuse}
        | {e["id"] for e in left_nil}
    )
    missing = [i for i in batch1_ids if i not in covered]
    if missing:
        raise SystemExit(f"batch1 uncovered: {missing}")

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

    battery_convention = {
        "catalogConvention": "net/usable",
        "thisPass": [
            {
                "id": "bmw-x1-phev-xdrive25e-2022",
                "batteryKWh": 8.82,
                "note": "Capacità lorda/netta 10/8.82 printed → store netta 8.82",
            },
            {
                "id": "peugeot-3008-phev-2023",
                "batteryKWh": None,
                "note": (
                    "nil — seed IT aggregate covers multiple UK Apr 2023 variants "
                    "(trim PHEV); Usable 10.4 is HYBRID 225/HYBRID4 only"
                ),
            },
            {
                "id": "peugeot-3008-phev-2022",
                "batteryKWh": None,
                "note": "nil — no verified MY22 net label",
            },
        ],
    }

    new_ver = 83
    cdn["seedVersion"] = new_ver
    cdn["prevSeedVersion"] = 82
    cdn["rows"] = len(seed)
    payload = json.dumps(seed, separators=(",", ":"), ensure_ascii=False)
    cdn["bytes"] = len(payload.encode())
    cdn["updatedAt"] = datetime.now(timezone.utc).isoformat()
    cdn["note"] = (
        "seedVersion 83: PHEV wave2 batch1 corr4 — Peugeot 3008 2023 EAER floor(29.8 mi)=47; "
        "battery_convention nil for multi-variant aggregate; api/static sync deferred at seed 77"
    )
    SEED.write_text(payload)
    CDN.write_text(json.dumps(cdn, indent=2) + "\n")
    if SEED.stat().st_size != cdn["bytes"]:
        raise SystemExit(f"CDN bytes mismatch {cdn['bytes']} vs {SEED.stat().st_size}")

    lotto_partial = [p for p in partial if p["id"] in lotto]
    lotto_completed = [p for p in completed if p["id"] in lotto]
    lotto_homolog = [h for h in homolog_reuse if h["id"] in lotto]

    man = {
        "seedVersion": new_ver,
        "prevSeedVersion": 82,
        "ids_before": ids_before,
        "batch1_ids": batch1_ids,
        "completed": lotto_completed,
        "partial": lotto_partial,
        "extras": extras,
        "homolog_reuse": lotto_homolog,
        "left_nil": left_nil,
        "changed_fields": changed_fields,
        "counts": {
            "completed": len(lotto_completed),
            "partial": len(lotto_partial),
            "left_nil": len(left_nil),
            "homolog_reuse": len(lotto_homolog),
        },
        "non_phev_tech_sha": non_phev_sha,
        "m3_ids": sorted(m3_before),
        "sourceDay": SOURCE_DAY,
        "reviewNotes": [
            "CORR4: Peugeot 3008 2023 EAER 29.8 mi → floor 47 km (prudent min; was wrongly 48).",
            "CORR4: battery_convention peugeot-3008-phev-2023 → nil (multi-variant aggregate).",
            "Checker: miles→km floor probe; battery_convention thisPass must match seed nil/value.",
        ],
        "prKind": "research-correction",
        "battery_convention": battery_convention,
    }
    MANIFEST.write_text(json.dumps(man, indent=2, ensure_ascii=False) + "\n")
    print(
        json.dumps(
            {
                "seedVersion": new_ver,
                "bytes": cdn["bytes"],
                "counts": man["counts"],
                "changed_fields": changed_fields,
                "hybrid180_floor_km": HYBRID_180_MIN_KM,
                "non_phev_tech_sha": non_phev_sha,
            },
            indent=2,
            default=str,
        )
    )


if __name__ == "__main__":
    main()
