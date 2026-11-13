#!/usr/bin/env python3
"""
PHEV wave2 batch1 RESEARCH correction pass 2 (seed 80→81).

- peugeot-3008-phev-2022: scrub FR-2021 fill; MY2022 official net+EAER not verified
- bmw-x1-phev-xdrive25e-2022: battery 10 gross → 8.82 netta (IT listino 2022-01-26)
- peugeot-3008-phev-2023: battery 14.2 Capacity → 10.4 Usable (UK Apr 2023 listino)
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
INVENTORY = CACHE / "catalog_phev_wave2_batch1_inventory.json"
MANIFEST = CACHE / "catalog_phev_wave2_batch1_manifest.json"
SOURCE_DAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")

BMW_X1_IT = "https://www.press.bmwgroup.com/italy/article/attachment/T0321361IT/520251"
PEUGEOT_UK_APR23 = (
    "https://www.media.stellantis.com/uploads/uk/model-pricelist/"
    "peugeot3008pricespecapr23-6455a65377d74.pdf"
)
PEUGEOT_FR_20211102 = (
    "https://www.peugeot.fr/content/dam/peugeot/france/b2c/documentation/tarifs/"
    "novembre-2021/ct-3008-applicable-au-02-novembre-2021.pdf"
)
PEUGEOT_UK_ARCH_20220628 = (
    "https://web.archive.org/web/20220628030021/"
    "https://business.peugeot.co.uk/content/dam/peugeot/uk/b2b/buy/price---spec/"
    "pdfs/3008-suv-price-spec-guide.pdf"
)
PEUGEOT_UK_LIVE = (
    "https://business.peugeot.co.uk/content/dam/peugeot/uk/b2b/buy/price---spec/"
    "pdfs/3008-suv-price-spec-guide.pdf"
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


def main() -> None:
    seed = json.loads(SEED.read_text(encoding="utf-8"))
    by_id = {r["id"]: r for r in seed}
    ids_before = [r["id"] for r in seed]
    assert len(seed) == 6977

    cdn = json.loads(CDN.read_text(encoding="utf-8"))
    if int(cdn.get("seedVersion") or 0) != 80:
        raise SystemExit(f"expected seed 80 baseline, got {cdn.get('seedVersion')}")

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

    # --- 1) Peugeot 3008 2022: scrub invalid FR-2021 fill --------------------------------
    p22 = by_id["peugeot-3008-phev-2022"]
    for fld in ("batteryKWh", "wltpRangeKm"):
        if p22.get(fld) is not None:
            changed_fields.append(
                {
                    "id": p22["id"],
                    "field": fld,
                    "value": None,
                    "prev": p22.get(fld),
                    "url": PEUGEOT_FR_20211102,
                    "sourceDate": None,
                    "action": "scrub",
                }
            )
        clear_field(p22, fld)
    sn = p22.get("sourceName") or ""
    if "Peugeot FR Nov 2021" in sn or "wave2-batch1-corr Peugeot" in sn:
        # drop the invalid fill note but keep other provenance
        parts = [p.strip() for p in sn.split(";") if p.strip()]
        parts = [
            p
            for p in parts
            if "Peugeot FR Nov 2021" not in p and "wave2-batch1-corr Peugeot" not in p
        ]
        if parts:
            p22["sourceName"] = "; ".join(parts)
        else:
            p22.pop("sourceName", None)
    p22["sourceUpdatedAt"] = SOURCE_DAY
    finalize(p22)

    p22_nil = nil_entry(
        p22,
        reason=(
            "battery+EAER nil: FR tarif CT-3008 applicable 02/11/2021 is calendar-2021 — "
            "fails MY2022 dating (need MY-year document date or archive.org snapshot from 2022). "
            "Official UK business.peugeot.co.uk price/spec guide has a 2022-06-28 archive.org "
            "capture, but PDF retrieval truncates at 1 MiB without %%EOF so Usable Battery / "
            "Electric Range (Combined) values from that snapshot cannot be verified this pass "
            "(never use the archive only to re-date FR-2021 figures). Live UK guide rejected "
            "(CDX digest differs from 2022 capture; continuous). Dealer mirrors rejected."
        ),
        consulted=[
            {
                "url": PEUGEOT_FR_20211102,
                "sourceDate": "2021-11-02",
                "reject": "document date 2021 — not valid for MY2022 dating rule",
            },
            {
                "url": PEUGEOT_UK_ARCH_20220628,
                "sourceDate": "2022-06-28",
                "reject": (
                    "official Peugeot UK guide archived in 2022, but downloaded body truncated "
                    "at 1048576 bytes (no %%EOF) — cannot honestly read Usable/EAER from snapshot"
                ),
            },
            {
                "url": PEUGEOT_UK_LIVE,
                "reject": "live continuous PDF — CDX digest ≠ 20220628 capture; not used for MY22",
            },
            {
                "url": "https://www.guyperry.co.uk/wp-content/uploads/2022/04/3008-suv-price-spec-guide-2.pdf",
                "reject": "dealer/partner upload — not peugeot.com / media.stellantis OEM",
            },
        ],
        field_reasons={
            "batteryKWh": (
                "no verified MY2022 official sheet with labeled net/usable kWh "
                "(13.2 on FR tarif is unlabeled / likely gross; not stored)"
            ),
            "wltpRangeKm": "no verified MY2022 official combined EAER from a readable 2022 snapshot",
            "fuelConsumptionLPerKm": "FR mixte ponderato only; no discharged CS on consulted sheets",
            "energyConsumptionKWhPerKm": "no pure-CD label on consulted sheets",
        },
    )

    # --- 2) BMW X1 xDrive25e 2022: gross 10 → netta 8.82 ---------------------------------
    bmw = by_id["bmw-x1-phev-xdrive25e-2022"]
    if abs(float(bmw.get("batteryKWh") or 0) - 10.0) > 1e-9:
        raise SystemExit(f"BMW X1 2022 battery unexpected: {bmw.get('batteryKWh')}")
    bmw_cite = (
        "press.bmwgroup.com BMW X1 LISTINO PREZZI (F48) Valido a partire dal 26.01.2022 — "
        "Capacità lorda/netta batteria AV (kWh) 10/8.82 → store netta/net 8.82 "
        f"(not lorda 10) {BMW_X1_IT}"
    )
    bmw["batteryKWh"] = 8.82
    set_field_source(bmw, "batteryKWh", bmw_cite, "2022-01-26")
    # keep range cite; ensure sourceName mentions net
    sn = bmw.get("sourceName") or ""
    if "netta 8.82" not in sn:
        bmw["sourceName"] = f"{sn}; wave2-corr2 battery netta 8.82 — {BMW_X1_IT}".strip("; ")
    bmw["sourceUpdatedAt"] = SOURCE_DAY
    finalize(bmw)
    changed_fields.append(
        {
            "id": bmw["id"],
            "field": "batteryKWh",
            "value": 8.82,
            "prev": 10.0,
            "url": BMW_X1_IT,
            "sourceDate": "2022-01-26",
            "label": "netta",
        }
    )

    # --- 3) Peugeot 3008 2023: Capacity 14.2 → Usable 10.4 --------------------------------
    p23 = by_id["peugeot-3008-phev-2023"]
    if abs(float(p23.get("batteryKWh") or 0) - 14.2) > 1e-9:
        raise SystemExit(f"Peugeot 2023 battery unexpected: {p23.get('batteryKWh')}")
    p23_cite = (
        "media.stellantis.com PEUGEOT 3008 Pricelist — Effective from 1st April 2023 — "
        "Usable Battery Capacity (kWh) 10.4 for HYBRID 225 / HYBRID4 "
        f"(not Battery Capacity MAX 14.2) {PEUGEOT_UK_APR23}"
    )
    p23["batteryKWh"] = 10.4
    set_field_source(p23, "batteryKWh", p23_cite, "2023-04-01")
    sn = p23.get("sourceName") or ""
    if "Usable 10.4" not in sn and "usable 10.4" not in sn.lower():
        p23["sourceName"] = (
            f"{sn}; wave2-corr2 battery usable/net 10.4 — {PEUGEOT_UK_APR23}"
        ).strip("; ")
    p23["sourceUpdatedAt"] = SOURCE_DAY
    finalize(p23)
    changed_fields.append(
        {
            "id": p23["id"],
            "field": "batteryKWh",
            "value": 10.4,
            "prev": 14.2,
            "url": PEUGEOT_UK_APR23,
            "sourceDate": "2023-04-01",
            "label": "usable",
        }
    )

    # --- Rebuild manifest from prev, patching the three rows -----------------------------
    # Start from previous outcome lists; replace peugeot-2022 / bmw-2022 / peugeot-2023 entries.
    completed = list(prev_man.get("completed") or [])
    partial = list(prev_man.get("partial") or [])
    homolog_reuse = list(prev_man.get("homolog_reuse") or [])
    left_nil = list(prev_man.get("left_nil") or [])
    extras = list(prev_man.get("extras") or [])

    def drop_id(bucket: list, rid: str) -> list:
        return [e for e in bucket if e.get("id") != rid]

    partial = drop_id(partial, "peugeot-3008-phev-2022")
    left_nil = drop_id(left_nil, "peugeot-3008-phev-2022")
    left_nil.append(p22_nil)

    # BMW X1 2022 was left_nil with alreadyPresent battery 10 — update alreadyPresent
    left_nil = drop_id(left_nil, "bmw-x1-phev-xdrive25e-2022")
    left_nil.append(
        nil_entry(
            bmw,
            reason=(
                "CS+CD nil: IT listino 2022-01-26 has EAER + battery netta; "
                "no discharged CS / pure CD. Battery corrected to netta 8.82."
            ),
            consulted=[
                {
                    "url": BMW_X1_IT,
                    "sourceDate": "2022-01-26",
                    "reject_for": "CS/CD — no discharged / rein-elektrisch labels",
                    "accepted_for": "batteryKWh netta 8.82; wltpRangeKm alreadyPresent",
                }
            ],
            field_reasons={
                "fuelConsumptionLPerKm": "no discharged-battery CS on IT listino",
                "energyConsumptionKWhPerKm": "no rein-elektrisch / pure-CD label",
            },
        )
    )

    # Peugeot 2023 was left_nil with alreadyPresent battery 14.2 — update
    left_nil = drop_id(left_nil, "peugeot-3008-phev-2023")
    left_nil.append(
        nil_entry(
            p23,
            reason=(
                "CS+CD nil: UK Apr 2023 price/spec backs Usable Battery 10.4 and EAER; "
                "Fuel Consumption Combined / electric Combined are weighted only"
            ),
            consulted=[
                {
                    "url": PEUGEOT_UK_APR23,
                    "sourceDate": "2023-04-01",
                    "reject_for": "CS/CD — Combined fuel/electric weighted",
                    "accepted_for": "batteryKWh Usable 10.4; wltpRangeKm alreadyPresent",
                }
            ],
            field_reasons={
                "fuelConsumptionLPerKm": "UK Apr 2023 Combined L/100 is weighted",
                "energyConsumptionKWhPerKm": "UK Apr 2023 electric Combined kWh weighted",
            },
        )
    )

    # Ensure every batch1 id covered
    covered = (
        {e["id"] for e in completed}
        | {e["id"] for e in partial}
        | {e["id"] for e in homolog_reuse}
        | {e["id"] for e in left_nil}
    )
    missing = [i for i in batch1_ids if i not in covered]
    if missing:
        raise SystemExit(f"batch1 uncovered: {missing}")

    # Invariants
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

    new_ver = 81
    cdn["seedVersion"] = new_ver
    cdn["prevSeedVersion"] = 80
    cdn["rows"] = len(seed)
    payload = json.dumps(seed, separators=(",", ":"), ensure_ascii=False)
    cdn["bytes"] = len(payload.encode())
    cdn["updatedAt"] = datetime.now(timezone.utc).isoformat()
    cdn["note"] = (
        "seedVersion 81: PHEV wave2 batch1 corr2 — Peugeot 3008 2022 scrub (FR-2021 invalid for MY22); "
        "BMW X1 2022 battery netta 8.82; Peugeot 3008 2023 battery usable 10.4; "
        "api/static sync deferred at seed 77"
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
        "prevSeedVersion": 80,
        "ids_before": ids_before,
        "batch1_ids": batch1_ids,
        "completed": lotto_completed,
        "partial": lotto_partial,
        "extras": extras,
        "homolog_reuse": lotto_homolog,
        "left_nil": left_nil,
        "changed_fields": changed_fields,
        "battery_convention": {
            "catalogConvention": "net/usable",
            "thisPass": [
                "bmw-x1-phev-xdrive25e-2022 → 8.82 netta (printed)",
                "peugeot-3008-phev-2023 → 10.4 Usable Battery Capacity (printed)",
                "peugeot-3008-phev-2022 → battery nil (no verified MY22 net label)",
            ],
        },
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
            "CORR2: Peugeot 3008 2022 FR-2021 fill scrubbed — dating rule requires MY-year date or 2022 archive; "
            "UK 2022 archive PDF truncated unreadable; never re-date FR values via UK snapshot.",
            "CORR2: BMW X1 2022 battery → netta 8.82 from Capacità lorda/netta 10/8.82 on IT listino 2022-01-26.",
            "CORR2: Peugeot 3008 2023 battery → Usable 10.4 from UK Apr 2023 listino (was Capacity MAX 14.2).",
            "Nil research: no homepage-only reasons (Peugeot 2023, Volvo XC40, Captur, GLA/GLE consulted URLs retained/updated).",
            "Checker: require_year_token fail-closed + must-fail probe; best_shared_exact requires TAN+ep/power "
            "(missing ep rejected); seed-row homolog uses exact_homolog_ok for power+weighted WLTP.",
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
                "changed_fields": changed_fields,
                "non_phev_tech_sha": non_phev_sha,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
