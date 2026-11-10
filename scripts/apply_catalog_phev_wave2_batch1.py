#!/usr/bin/env python3
"""
PHEV wave2 batch1 (seed 77→78) — review-corrected.

Only official OEM fills with valid dating. Homolog reuse requires IDENTICAL
TAN/Va/Ve/ep AND identical power + weighted WLTP between seed rows; donor
source must itself be dated for the donor year (no continuous live PDFs).
No ±kW tolerance, no frequency ranking, no chain derivation.
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
    best_shared_exact,
    cite_dating_ok,
    exact_homolog_ok,
    is_generic_url,
    source_year_ok,
    urls_in,
)
from lib.phev_manus_v76_validate import missing_calc_fields  # noqa: E402

SEED = REPO / "EVforME?" / "Data" / "vehicles.seed.quality.json"
CDN = REPO / "EVforME?" / "Data" / "catalog_cdn.json"
CACHE = REPO / "scripts" / "cache" / "eea"
INVENTORY = CACHE / "catalog_phev_wave2_batch1_inventory.json"
MANIFEST = CACHE / "catalog_phev_wave2_batch1_manifest.json"
BASE_MAIN = "0f0919245dbd68bb10da67ca1f21fe18192c38c5"
SOURCE_DAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")

BMW_330E_PRESS = "https://www.press.bmwgroup.com/global/article/attachment/T0442333EN/620071"


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


CLEARABLE_FIELDS = (
    "fuelConsumptionLPerKm",
    "energyConsumptionKWhPerKm",
    "batteryKWh",
    "wltpRangeKm",
)


def scrub_invalid_field_provenance(row: dict) -> list[str]:
    """Drop field values whose cites fail generic/dating on real PHEV rows."""
    cleared: list[str] = []
    fs = dict(row.get("fieldSources") or {})
    fd = dict(row.get("fieldSourceDates") or {})
    hy_raw = row.get("dataDerivedFromSameHomologationYear")
    hy = int(hy_raw) if hy_raw is not None else None
    year = int(row.get("year") or 0)
    for field in list(fs.keys()):
        cite = fs.get(field) or ""
        if not cite:
            continue
        date = fd.get(field) or ""
        urls = urls_in(cite) or [cite]
        bad_generic = any(is_generic_url(u) for u in urls)
        bad_dating = not cite_dating_ok(cite, date, year, homolog_year=hy)
        if not (bad_generic or bad_dating):
            continue
        cleared.append(field)
        fs.pop(field, None)
        fd.pop(field, None)
        if field in CLEARABLE_FIELDS:
            row[field] = None
            if field == "energyConsumptionKWhPerKm":
                row["energyIsWeighted"] = None
    row["fieldSources"] = fs or None
    row["fieldSourceDates"] = fd or None
    # If no field cites remain that mention homolog, drop derivation flag.
    remaining = " ".join((row.get("fieldSources") or {}).values())
    if hy is not None and "stessa omologazione" not in remaining.lower() and "homolog" not in remaining.lower():
        row.pop("dataDerivedFromSameHomologationYear", None)
    return cleared


def tech_blob(rows: list[dict]) -> str:
    conf = {
        "confidenceScore",
        "confidenceScoreLegacy",
        "confidencePolicyVersion",
        "confidenceEvidence",
    }
    cleaned = [{k: v for k, v in r.items() if k not in conf} for r in rows]
    return json.dumps(cleaned, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def load_main_seed() -> dict[str, dict]:
    import subprocess

    raw = subprocess.check_output(["git", "show", f"{BASE_MAIN}:EVforME?/Data/vehicles.seed.quality.json"])
    return {r["id"]: r for r in json.loads(raw)}


def main() -> None:
    seed = json.loads(SEED.read_text(encoding="utf-8"))
    by_id = {r["id"]: r for r in seed}
    ids_before = [r["id"] for r in seed]
    assert len(seed) == 6977

    main_by = load_main_seed()
    m3_before = {
        r["id"]: json.dumps(r, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        for r in seed
        if r["id"].startswith("tesla-model-3") and r.get("year") == 2026
    }
    assert len(m3_before) == 4
    non_phev_before = tech_blob([r for r in seed if r.get("powertrain") != "phev"])
    non_phev_sha_before = hashlib.sha256(non_phev_before.encode()).hexdigest()

    inv = json.loads(INVENTORY.read_text(encoding="utf-8"))
    batch1_ids = [x["id"] for x in inv["batch1_candidates"]]
    assert len(batch1_ids) == 40

    completed: list[dict] = []
    partial: list[dict] = []
    homolog_reuse: list[dict] = []
    left_nil: list[dict] = []
    extras: list[dict] = []

    # --- Restore previously invalid fills from main (Kuga 2022, Jeep CS) ---
    for rid in (
        "ford-kuga-phev-2022",
        "jeep-compass-phev-4xe-2022",
        "jeep-renegade-phev-4xe-2022",
    ):
        by_id[rid].clear()
        by_id[rid].update(json.loads(json.dumps(main_by[rid])))  # deep copy via JSON
        finalize(by_id[rid])

    # Sanity: kuga weighted fuel restored
    kuga = by_id["ford-kuga-phev-2022"]
    if abs(float(kuga.get("weightedFuelConsumptionLPerKm") or 0) - 0.01007) > 1e-9:
        raise SystemExit("kuga weightedFuel restore failed")
    if kuga.get("catalogDataIncomplete") is not True:
        raise SystemExit("kuga must be incomplete after restore")
    if kuga.get("dataDerivedFromSameHomologationYear") is not None:
        raise SystemExit("kuga homolog flag must be cleared")

    # Scrub invalid generic/dating cites on EVERY real PHEV row (honesty under
    # strengthened checker). Prefer nil over hybrid-suv / continuous undated PDFs.
    scrubbed_rows: list[dict] = []
    for r in seed:
        if r.get("powertrain") != "phev":
            continue
        cleared = scrub_invalid_field_provenance(r)
        if cleared:
            finalize(r)
            scrubbed_rows.append({"id": r["id"], "cleared": cleared})

    # --- Extra (outside strict lotto completion): BMW 330e 2024 battery ---
    b330 = by_id["bmw-330e-phev-2024"]
    if b330.get("batteryKWh") != 19.5:
        b330["batteryKWh"] = 19.5
    cite = (
        "press.bmwgroup.com new BMW 330e: high-voltage battery with 19.5 kWh of usable energy "
        f"(datePublished 2024-05-29) {BMW_330E_PRESS}"
    )
    # Clear any stale derived flag; this is same-MY 2024 press (dated)
    b330.pop("dataDerivedFromSameHomologationYear", None)
    set_field_source(b330, "batteryKWh", cite, "2024-05-29")
    b330["sourceUpdatedAt"] = SOURCE_DAY
    prev = b330.get("sourceName") or ""
    if "wave2-batch1: batteryKWh=19.5" not in prev and "wave2-batch1 extra: batteryKWh=19.5" not in prev:
        b330["sourceName"] = (
            f"{prev}; wave2-batch1 extra: batteryKWh=19.5 usable — {BMW_330E_PRESS}"
        ).strip("; ")
    finalize(b330)
    extras.append(
        {
            "id": b330["id"],
            "note": "extra vs lotto — BMW press May 2024 usable battery; pure CD remains nil",
            "filled": {"batteryKWh": 19.5},
            "stillMissing": b330["missingCalcFields"],
            "sources": {"batteryKWh": cite},
            "sourceDates": {"batteryKWh": "2024-05-29"},
        }
    )
    partial.append(extras[-1])

    # --- Batch1 coverage: no additional official dated pure-CD sources verified ---
    # Document nil reasons for every batch1 id except the BMW extra above.
    nil_reasons = {
        "ford-kuga-phev-2022": (
            "no MY2022-dated OEM doc / 2022 archive snapshot; live Technische_Daten PDF is "
            "continuously updated (archive only 2026) — invalid for MY22 and as homolog donor source"
        ),
        "jeep-compass-phev-4xe-2022": (
            "no MY2022-specific official CS/CD doc; jeep.de/hybrid-suv is a generic range page "
            "(archive 2024) — rejected; weighted WLTP/power not identical to 2024 donor"
        ),
        "jeep-renegade-phev-4xe-2022": (
            "no MY2022-specific official CS/CD doc; jeep.de/hybrid-suv generic range page rejected; "
            "weighted WLTP not identical to 2024 donor"
        ),
    }
    default_nil = (
        "no same-MY official OEM document with dated pure-electric (rein elektrisch / "
        "charge-depleting) label and/or CS+EAER combined+battery; live pages / continuous PDFs / "
        "EAER City-only / weighted-only kWh rejected"
    )

    touched = {p["id"] for p in partial}
    for rid in batch1_ids:
        row = by_id[rid]
        miss = missing_calc_fields(row)
        if rid in touched and not miss:
            continue
        if rid in touched and miss:
            # BMW extra already recorded as partial
            continue
        left_nil.append(
            {
                "id": rid,
                "brand": row.get("brand"),
                "model": row.get("model"),
                "year": row.get("year"),
                "market": row.get("market"),
                "missing": miss,
                "reason": nil_reasons.get(rid, default_nil),
            }
        )

    # Export helpers used by unit tests / checkers
    _ = best_shared_exact
    _ = exact_homolog_ok

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
    # Allow re-run on already-bumped seed 78
    if int(cdn.get("seedVersion") or 0) not in (77, 78):
        raise SystemExit(f"unexpected seedVersion {cdn.get('seedVersion')}")
    new_ver = 78
    cdn["seedVersion"] = new_ver
    cdn["rows"] = len(seed)
    payload = json.dumps(seed, separators=(",", ":"), ensure_ascii=False)
    cdn["bytes"] = len(payload.encode())
    cdn["updatedAt"] = datetime.now(timezone.utc).isoformat()
    cdn["note"] = (
        "seedVersion 78: PHEV wave2 batch1 (review-corrected) — BMW 330e battery extra; "
        "invalid Kuga/Jeep fills reverted; confidence policy v2 unchanged"
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
        "extras": extras,
        "homolog_reuse": homolog_reuse,
        "left_nil": left_nil,
        "non_phev_tech_sha": non_phev_sha_after,
        "m3_ids": sorted(m3_before),
        "sourceDay": SOURCE_DAY,
        "reviewNotes": [
            "Reverted ford-kuga-2022 completion (continuous undated Ford PDF / no 2022 archive).",
            "Reverted Jeep Compass/Renegade 2022 CS from generic /hybrid-suv archive.",
            "Restored homolog shared map to main (no unverified 2022 year injection).",
            "BMW 330e 2024 battery 19.5 kept as extra vs lotto; pure CD nil.",
            "Scrubbed generic/dating-invalid fieldSources on all PHEV rows under strengthened checker.",
        ],
        "scrubbed_invalid_provenance": scrubbed_rows,
    }
    MANIFEST.write_text(json.dumps(man, indent=2, ensure_ascii=False) + "\n")
    print(
        json.dumps(
            {
                "seedVersion": new_ver,
                "completed": len(completed),
                "partial": len(partial),
                "extras": len(extras),
                "left_nil": len(left_nil),
                "homolog_reuse": len(homolog_reuse),
                "scrubbed": len(scrubbed_rows),
                "non_phev_tech_sha": non_phev_sha_after,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
