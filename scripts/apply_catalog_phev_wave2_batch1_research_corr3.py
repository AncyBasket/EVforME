#!/usr/bin/env python3
"""
PHEV wave2 batch1 RESEARCH correction pass 3 (seed 81→82).

- peugeot-3008-phev-2023: aggregate PHEV — battery nil; keep EAER 48 (HYBRID 180 min);
  never mix Usable 10.4 (225/300) with range from 180 column; fix sourceName
- bmw-x1-phev-xdrive25e-2022: sourceName must state Capacità lorda/netta 10/8.82, netto 8.82
"""

from __future__ import annotations

import hashlib
import json
import re
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
INVENTORY = CACHE / "catalog_phev_wave2_batch1_inventory.json"
MANIFEST = CACHE / "catalog_phev_wave2_batch1_manifest.json"
SOURCE_DAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")

PEUGEOT_UK_APR23 = (
    "https://www.media.stellantis.com/uploads/uk/model-pricelist/"
    "peugeot3008pricespecapr23-6455a65377d74.pdf"
)
BMW_X1_IT = "https://www.press.bmwgroup.com/italy/article/attachment/T0321361IT/520251"

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


def clear_field(row: dict, field: str) -> None:
    row[field] = None
    fs = dict(row.get("fieldSources") or {})
    fd = dict(row.get("fieldSourceDates") or {})
    fs.pop(field, None)
    fd.pop(field, None)
    if fs:
        row["fieldSources"] = fs
    else:
        row.pop("fieldSources", None)
    if fd:
        row["fieldSourceDates"] = fd
    else:
        row.pop("fieldSourceDates", None)


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
    seed = json.loads(SEED.read_text(encoding="utf-8"))
    by_id = {r["id"]: r for r in seed}
    ids_before = [r["id"] for r in seed]
    assert len(seed) == 6977

    cdn = json.loads(CDN.read_text(encoding="utf-8"))
    if int(cdn.get("seedVersion") or 0) != 81:
        raise SystemExit(f"expected seed 81 baseline, got {cdn.get('seedVersion')}")

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

    # --- Peugeot 3008 2023: aggregate → battery nil, range 48 from HYBRID 180 column ------
    p23 = by_id["peugeot-3008-phev-2023"]
    # Not clearly HYBRID 225: trim="PHEV", EEA aggregate n=1604, no 225 in model/trim.
    if abs(float(p23.get("batteryKWh") or 0) - 10.4) > 1e-9:
        raise SystemExit(f"Peugeot 2023 battery unexpected baseline: {p23.get('batteryKWh')}")
    if int(p23.get("wltpRangeKm") or 0) != 48:
        raise SystemExit(f"Peugeot 2023 range unexpected baseline: {p23.get('wltpRangeKm')}")

    clear_field(p23, "batteryKWh")
    # Keep range 48 but retarget cite to HYBRID 180 EAER column (29.8 mi → 48 km)
    range_cite = (
        "media.stellantis.com PEUGEOT 3008 Pricelist — Effective from 1st April 2023 — "
        "aggregate IT PHEV row (trim PHEV, not clearly HYBRID 225): EAER miles from "
        "PLUG-IN HYBRID 180 column 29.8–39.1 → MIN 48 km (prudent min across variants; "
        "HYBRID 225 column is 35.4–42.9 and must not be mixed with 180). "
        f"Usable 10.4 is only on HYBRID 225/HYBRID4 (180=TBC) → battery nil. {PEUGEOT_UK_APR23}"
    )
    set_field_source(p23, "wltpRangeKm", range_cite, "2023-04-01")
    rewrite_source_name(
        p23,
        drop_substrings=[
            "bat 14.2",
            "battery 14.2",
            "wave2-corr2 battery usable",
            "range 48 km, bat 14.2",
        ],
        append=(
            "PEUGEOT 3008 UK Apr 2023 (Effective 1st April 2023): aggregate PHEV — "
            "EAER 48 km from HYBRID 180 column (29.8 mi min); battery nil "
            "(Usable 10.4 only on HYBRID 225/HYBRID4 columns, not claimed for this aggregate) "
            f"— {PEUGEOT_UK_APR23}"
        ),
    )
    p23["sourceUpdatedAt"] = SOURCE_DAY
    finalize(p23)
    changed_fields.append(
        {
            "id": p23["id"],
            "field": "batteryKWh",
            "value": None,
            "prev": 10.4,
            "url": PEUGEOT_UK_APR23,
            "sourceDate": "2023-04-01",
            "action": "scrub-aggregate-not-225",
        }
    )
    changed_fields.append(
        {
            "id": p23["id"],
            "field": "wltpRangeKm",
            "value": 48,
            "url": PEUGEOT_UK_APR23,
            "sourceDate": "2023-04-01",
            "note": "HYBRID 180 column min 29.8 mi → 48 km; not 225 column",
        }
    )

    # --- BMW X1 2022 sourceName hygiene -------------------------------------------------
    bmw = by_id["bmw-x1-phev-xdrive25e-2022"]
    sn = bmw.get("sourceName") or ""
    # Replace "batteria 10 kWh" phrasing
    sn2 = re.sub(
        r"batteria\s*10\s*kWh",
        "Capacità lorda/netta 10/8.82, memorizzato netto 8.82",
        sn,
        flags=re.I,
    )
    if "8.82" not in sn2:
        sn2 = (
            f"{sn2}; Capacità lorda/netta 10/8.82, memorizzato netto 8.82 "
            f"(listino IT valido dal 26.01.2022) — {BMW_X1_IT}"
        ).strip("; ")
    elif "memorizzato netto" not in sn2.lower() and "lorda/netta" not in sn2.lower():
        sn2 = (
            f"{sn2}; Capacità lorda/netta 10/8.82, memorizzato netto 8.82 "
            f"(listino IT valido dal 26.01.2022) — {BMW_X1_IT}"
        ).strip("; ")
    # Drop stale corr2 append if redundant
    parts = [p.strip() for p in sn2.split(";") if p.strip()]
    parts = [p for p in parts if "wave2-corr2 battery netta" not in p.lower()]
    bmw["sourceName"] = "; ".join(parts)
    bmw["sourceUpdatedAt"] = SOURCE_DAY
    finalize(bmw)
    changed_fields.append(
        {
            "id": bmw["id"],
            "field": "sourceName",
            "value": "Capacità lorda/netta 10/8.82, memorizzato netto 8.82",
            "url": BMW_X1_IT,
            "sourceDate": "2022-01-26",
        }
    )

    # --- Manifest rebuild patches -------------------------------------------------------
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
                "not clearly HYBRID 225. UK Apr 2023 Usable 10.4 is only on HYBRID 225 / "
                "HYBRID4 columns (HYBRID 180=TBC). EAER kept at 48 km = HYBRID 180 column "
                "min 29.8 mi (prudent across variants); never pair 10.4 with 48."
            ),
            consulted=[
                {
                    "url": PEUGEOT_UK_APR23,
                    "sourceDate": "2023-04-01",
                    "reject_for": "battery — Usable 10.4 is HYBRID 225/300 only; row not clearly 225",
                    "accepted_for": "wltpRangeKm 48 from HYBRID 180 EAER column min 29.8 mi",
                }
            ],
            field_reasons={
                "batteryKWh": (
                    "aggregate PHEV — Usable 10.4 printed only on HYBRID 225 / HYBRID4; "
                    "HYBRID 180 Usable=TBC; do not assign 225 battery to aggregate"
                ),
                "fuelConsumptionLPerKm": "Combined L/100 weighted only",
                "energyConsumptionKWhPerKm": "electric Combined weighted only",
            },
        )
    )

    left_nil = drop_id(left_nil, "bmw-x1-phev-xdrive25e-2022")
    left_nil.append(
        nil_entry(
            bmw,
            reason=(
                "CS+CD nil: IT listino 2022-01-26 has EAER + Capacità lorda/netta 10/8.82 "
                "(memorizzato netto 8.82); no discharged CS / pure CD"
            ),
            consulted=[
                {
                    "url": BMW_X1_IT,
                    "sourceDate": "2022-01-26",
                    "reject_for": "CS/CD",
                    "accepted_for": "batteryKWh netta 8.82; wltpRangeKm alreadyPresent",
                }
            ],
            field_reasons={
                "fuelConsumptionLPerKm": "no discharged-battery CS",
                "energyConsumptionKWhPerKm": "no rein-elektrisch / pure-CD label",
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

    new_ver = 82
    cdn["seedVersion"] = new_ver
    cdn["prevSeedVersion"] = 81
    cdn["rows"] = len(seed)
    payload = json.dumps(seed, separators=(",", ":"), ensure_ascii=False)
    cdn["bytes"] = len(payload.encode())
    cdn["updatedAt"] = datetime.now(timezone.utc).isoformat()
    cdn["note"] = (
        "seedVersion 82: PHEV wave2 batch1 corr3 — Peugeot 3008 2023 aggregate battery nil "
        "(no mix 10.4@225 with EAER@180); BMW X1 2022 sourceName netta 8.82; "
        "best_shared_exact TAN+Va+Ve+ep gate; api/static sync deferred at seed 77"
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
        "prevSeedVersion": 81,
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
            "CORR3: Peugeot 3008 2023 is aggregate IT PHEV — battery nil; EAER 48 from HYBRID 180 "
            "column (29.8 mi); Usable 10.4 stays on 225/300 columns only (never mix with 48).",
            "CORR3: BMW X1 2022 sourceName → Capacità lorda/netta 10/8.82, memorizzato netto 8.82.",
            "Checker: Q3 SB 2023←2024 must pass exact_homolog_ok AND best_shared_exact(TAN+Va+Ve+ep); "
            "must-fail probe when distinct TANs share the same power.",
        ],
        "prKind": "research-correction",
        "battery_convention": prev_man.get("battery_convention"),
    }
    MANIFEST.write_text(json.dumps(man, indent=2, ensure_ascii=False) + "\n")
    print(
        json.dumps(
            {
                "seedVersion": new_ver,
                "bytes": cdn["bytes"],
                "counts": man["counts"],
                "changed_fields": changed_fields,
                "non_phev_tech_sha": non_phev_sha,
            },
            indent=2,
            default=str,
        )
    )


if __name__ == "__main__":
    main()
