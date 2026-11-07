#!/usr/bin/env python3
"""
Selective recovery of Manus PHEV supplement (PR #33) → seed v75→v76.

Only fields re-verified against reopened OEM documents are imported.
Rejected proposals keep main values. No confidence / Core / API changes.
No row removals. M3 2026 untouched.

BMW 225e 2022 range: NOT imported — cached “PDF” was HTML listino 2026;
live press pages are not admissible for past years without a 2022 archive snapshot.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
from lib.phev_manus_v76_validate import (  # noqa: E402
    missing_calc_fields,
    validate_field_import,
)

SEED = REPO / "EVforME?" / "Data" / "vehicles.seed.quality.json"
CDN = REPO / "EVforME?" / "Data" / "catalog_cdn.json"
CACHE = REPO / "scripts" / "cache" / "eea"
OEM = REPO / "scripts" / "cache" / "oem" / "manus_verify"
MANIFEST = CACHE / "catalog_phev_manus_verified_v76_manifest.json"
AUDIT = REPO / "docs" / "audit" / "PHEV_MANUS_VERIFIED_V76.json"

SOURCE_DAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")

ACCEPTED = {
    "toyota-rav4-phev-2023": [
        {
            "field": "batteryKWh",
            "value": 18.1,
            "url": "https://newsroom.toyota.it/download/1316286/20230101rav4plug-inhybridmy23schedatecnica.pdf",
            "date": "2023-01-03",
            "label": "BATTERIE HV / Litio - Capacità (kWh) = 18.1",
            "page": "scheda tecnica p.1; PDF CreationDate 2023-01-03",
            "note": "net/gross base not stated; value used as capacity as printed",
            "download": OEM / "toyota_rav4_my23.pdf",
            "row_year": 2023,
        },
    ],
    "cupra-formentor-phev-e-hybrid-2024": [
        {
            "field": "batteryKWh",
            "value": 12.8,
            "url": "https://www.cupra.com/content/dam/countries/ie/cupra-website/product-guide/formentor/cars-models-info-KM7-product-guide-Jan-2024.pdf",
            "date": "2024-01-01",
            "label": "Battery Capacity [kWh] 12.8 for e-Hybrid 204hp DSG (KM7BUY) and VZ 245hp",
            "page": "JANUARY 2024 Product Guide; tech table; Information valid as of 01.01.2024",
            "note": (
                "Matches prior-gen 204 hp / system 150 kW / ICE thermal 110 kW; "
                "seed powerKw 110.6 is thermal; CO2 27 g/km matches 204 hp row; "
                "NOT facelift 25.8 kWh"
            ),
            "download": OEM / "cupra_ie_jan2024.pdf",
            "row_year": 2024,
        },
    ],
}

REJECTED = [
    {
        "id": "bmw-serie-2-active-tourer-225e-xdrive-2022",
        "field": "wltpRangeKm",
        "proposed": 83,
        "reason": (
            "claimed press cache was HTML of 2026 listino (not a PDF); "
            "IT press URL redirects to newsroom home; DE live page dated 18.05.2022 "
            "shows 83–92 km but live pages are not admissible for past years and "
            "archive.org has no 2022 snapshot — restore main nil"
        ),
        "tried": [
            "scripts/cache/oem/manus_verify/bmw_2at_press_652064.html (was .pdf; HTML listino 2026)",
            "https://www.press.bmwgroup.com/italy/article/detail/T0396153IT/… → redirect newsroom home",
            "https://www.press.bmwgroup.com/deutschland/article/detail/T0390613DE/… live 2026, date badge 18.05.2022, no Wayback 2022",
        ],
    },
    {
        "id": "bmw-serie-2-active-tourer-225e-xdrive-2022",
        "field": "batteryKWh",
        "proposed": 14.2,
        "reason": (
            "listino PDF unreachable; summer-2022 press treats 14.2–15.8 as kWh/100 "
            "consumption not capacity; live 2026 listino cannot date a 2022 row"
        ),
        "tried": [
            "https://www.bmw.it/content/dam/bmw/marketIT/bmw_it/Topics/Business/2022/Listini/Listino-BMWSerie2-ActiveTourer-U06.pdf.asset.1656074029722.pdf",
        ],
    },
    {
        "id": "bmw-serie-2-active-tourer-225e-xdrive-2023",
        "field": "batteryKWh+wltpRangeKm",
        "proposed": {"batteryKWh": 14.2, "wltpRangeKm": 83},
        "reason": "original 2023 listino PDF not reopened (download fail; no archive snapshot)",
        "tried": [
            "https://www.bmw.it/content/dam/bmw/marketIT/bmw_it/Topics/Business/2023/Listini2023/Listino_BMW-Serie2-Active-Tourer_U06_produzione-dal-01.03.2023.pdf.asset.1675070620611.pdf"
        ],
    },
    {
        "id": "bmw-serie-2-active-tourer-225e-xdrive-2024",
        "field": "batteryKWh+wltpRangeKm",
        "proposed": {"batteryKWh": 14.2, "wltpRangeKm": 78},
        "reason": "original 2024 listino PDF not reopened (download fail; no archive snapshot)",
        "tried": [
            "https://www.bmw.it/content/dam/bmw/marketIT/bmw_it/Topics/Business/2024/aprile/Listino%20BMW%20Serie%202%20Active%20Tourer%20(U06)%20da%20prod.%2001.07.2024.pdf.asset.1713250994104.pdf"
        ],
    },
    {
        "id": "bmw-x3-phev-xdrive30e-2022",
        "field": "batteryKWh+wltpRangeKm",
        "proposed": {"batteryKWh": 11.15, "wltpRangeKm": 45},
        "reason": "original X3 2022 listino PDF not reopened",
        "tried": [
            "https://www.bmw.it/content/dam/bmw/marketIT/bmw_it/Topics/Business/2022/Listini/Listino-Nuova-BMW-X3-G01.pdf.asset.1656075290702.pdf"
        ],
    },
    {
        "id": "bmw-x3-phev-xdrive30e-2023",
        "field": "batteryKWh+wltpRangeKm",
        "proposed": {"batteryKWh": 11.15, "wltpRangeKm": 45},
        "reason": "original X3 2023 listino PDF not reopened",
        "tried": [
            "https://www.bmw.it/content/dam/bmw/marketIT/bmw_it/Topics/Business/2023/listini-0423/Listino-BMW-X3-G01-valido-da-prod.01.04.2023.pdf.asset.1676901178092.pdf"
        ],
    },
    {
        "id": "bmw-x3-phev-xdrive30e-2024",
        "field": "batteryKWh+wltpRangeKm",
        "proposed": {"batteryKWh": 11.15, "wltpRangeKm": 45},
        "reason": "original X3 2024 listino PDF not reopened",
        "tried": [
            "https://www.bmw.it/content/dam/bmw/marketIT/bmw_it/Topics/Business/2024/gennaio/Listino%20BMW%20X3%20(G01)%20valido%20da%20prod.%2001.04.2024.pdf.asset.1706715697138.pdf"
        ],
    },
    {
        "id": "hyundai-tucson-phev-2023",
        "field": "batteryKWh+wltpRangeKm+weightedFuel",
        "proposed": {"batteryKWh": 13.8, "wltpRangeKm": 62, "weightedFuelConsumptionLPerKm": 0.014},
        "reason": (
            "sole cited PDF is August 2022 (download 403); even if MY23-labelled, "
            "lacks 2023-dated document/snapshot; no EEA homolog shared map entry for derivation"
        ),
        "tried": [
            "https://hyundai-cyprus.com/wp-content/uploads/admin/2022/07/New-Hyundai-Tucson-FULL-HYBRID-PLUG-IN-HYBRID-AUGUST-22.pdf"
        ],
    },
    {
        "id": "toyota-rav4-phev-2023",
        "field": "weightedFuelConsumptionLPerKm",
        "proposed": 0.01,
        "reason": (
            "PDF MY23 shows 1,00 l/100 km; main already has valid EEA weightedFuel 0.00948 — "
            "keep main; no overwrite of existing valid data"
        ),
        "tried": [
            "https://newsroom.toyota.it/download/1316286/20230101rav4plug-inhybridmy23schedatecnica.pdf"
        ],
    },
    {
        "id": "toyota-rav4-phev-2024",
        "field": "batteryKWh+weightedFuel",
        "proposed": {"batteryKWh": 18.1, "weightedFuelConsumptionLPerKm": 0.01},
        "reason": (
            "live unversioned URL PDF CreationDate/ModDate 2023-06-26 — does not prove 2024 dating; "
            "no 2024 archive snapshot; no homolog shared 2023∩2024 in map"
        ),
        "tried": [
            "https://www.toyota.it/content/dam/toyota/nmsc/italy/gamma/pdf/scheda-tecnica/RAV4_Plug-in_Hybrid_Scheda_tecnica.pdf"
        ],
    },
    {
        "id": "volkswagen-tiguan-phev-ehybrid-2024",
        "field": "batteryKWh",
        "proposed": 19.7,
        "reason": (
            "VW Newsroom 19.7 kWh NET is for new-gen 1.5 TSI PHEV system 150/200 kW; "
            "seed powerKw=112.2 — cannot demonstrate the IT EEA row is that generation/market match"
        ),
        "tried": [
            "https://www.volkswagen-newsroom.com/en/press-releases/now-available-to-order-long-range-plug-in-hybrid-drives-for-the-tiguan-from-48655-euro-18182"
        ],
    },
]


def finalize(row: dict) -> None:
    miss = missing_calc_fields(row)
    row["missingCalcFields"] = miss
    row["catalogDataIncomplete"] = bool(miss)


def counts(rows):
    c = k = m = 0
    for r in rows:
        miss = missing_calc_fields(r)
        if not miss:
            c += 1
        elif miss == ["energyConsumptionKWhPerKm"]:
            k += 1
        else:
            m += 1
    return c, k, m


def strip_bmw_range_provenance(row: dict, *, main_source_updated_at: str | None = None) -> None:
    """Restore main nil for undemonstrated BMW 2022 range and drop added provenance only."""
    row["wltpRangeKm"] = None
    fs = dict(row.get("fieldSources") or {})
    fd = dict(row.get("fieldSourceDates") or {})
    fs.pop("wltpRangeKm", None)
    fd.pop("wltpRangeKm", None)
    if fs:
        row["fieldSources"] = fs
    else:
        row.pop("fieldSources", None)
    if fd:
        row["fieldSourceDates"] = fd
    else:
        row.pop("fieldSourceDates", None)
    sn = row.get("sourceName") or ""
    # remove only manus-verified range note
    parts = [p.strip() for p in sn.split(";") if p.strip()]
    parts = [p for p in parts if "manus-verified v76: wltpRangeKm" not in p]
    row["sourceName"] = "; ".join(parts) if parts else sn
    if main_source_updated_at is not None and "manus-verified v76:" not in (row.get("sourceName") or ""):
        # no remaining manus fields on this row → restore main consultation stamp
        row["sourceUpdatedAt"] = main_source_updated_at
    finalize(row)


def main() -> None:
    seed = json.loads(SEED.read_text(encoding="utf-8"))
    cdn = json.loads(CDN.read_text(encoding="utf-8"))
    by_id = {r["id"]: r for r in seed}
    ids_before = [r["id"] for r in seed]
    m3_before = {
        r["id"]: json.dumps(r, sort_keys=True)
        for r in seed
        if r["id"].startswith("tesla-model-3") and r.get("year") == 2026
    }

    parents = [r for r in seed if r.get("powertrain") == "phev" and not r.get("parentId")]
    before = counts(parents)

    # Always strip undemonstrated BMW range if present (idempotent fix for v76 review).
    if "bmw-serie-2-active-tourer-225e-xdrive-2022" in by_id:
        strip_bmw_range_provenance(
            by_id["bmw-serie-2-active-tourer-225e-xdrive-2022"],
            main_source_updated_at="2026-10-27",
        )

    changed: list[dict] = []
    for rid, fields in ACCEPTED.items():
        row = by_id[rid]
        for spec in fields:
            v = validate_field_import(
                row_year=int(spec["row_year"]),
                field=spec["field"],
                value=spec["value"],
                url=spec["url"],
                source_date=spec["date"],
                label=f"{spec['label']}; {spec['page']}",
                download_path=spec.get("download"),
            )
            if not v.ok:
                raise SystemExit(f"accepted import failed validation {rid}.{spec['field']}: {v.reason}")
            field = spec["field"]
            before_val = row.get(field)
            row[field] = spec["value"]
            fs = dict(row.get("fieldSources") or {})
            fd = dict(row.get("fieldSourceDates") or {})
            fs[field] = f"{spec['label']}; {spec['page']}; {spec['note']}; {spec['url']}"
            fd[field] = spec["date"]
            row["fieldSources"] = fs
            row["fieldSourceDates"] = fd
            sn = row.get("sourceName") or ""
            note = f"manus-verified v76: {field}={spec['value']} ({spec['date']}) — {spec['url']}"
            if note not in sn:
                row["sourceName"] = f"{sn}; {note}".strip("; ").strip()
            row["sourceUpdatedAt"] = SOURCE_DAY
            changed.append(
                {
                    "id": rid,
                    "field": field,
                    "before": before_val,
                    "after": spec["value"],
                    "decision": "accepted",
                    "url": spec["url"],
                    "sourceDate": spec["date"],
                    "label": spec["label"],
                    "page": spec["page"],
                    "note": spec["note"],
                    "evidence": "document_reopened",
                    "validation": v.reason,
                }
            )
        finalize(row)

    for rej in REJECTED:
        changed.append(
            {
                "id": rej["id"],
                "field": rej["field"],
                "before": None,
                "after": None,
                "proposed": rej["proposed"],
                "decision": "rejected",
                "reason": rej["reason"],
                "tried": rej["tried"],
                "evidence": "verification_failed_or_insufficient",
            }
        )

    for r in seed:
        if r["id"] in m3_before and json.dumps(r, sort_keys=True) != m3_before[r["id"]]:
            raise SystemExit(f"M3 2026 altered: {r['id']}")
    if set(ids_before) != {r["id"] for r in seed}:
        raise SystemExit("row set changed")

    parents = [r for r in seed if r.get("powertrain") == "phev" and not r.get("parentId")]
    after = counts(parents)
    bad = [
        r["id"]
        for r in parents
        if not r.get("catalogDataIncomplete") and missing_calc_fields(r)
    ]
    if bad:
        raise SystemExit(f"complete_with_nil_calc: {bad}")

    ver = int(cdn.get("seedVersion") or 0)
    if ver not in (75, 76):
        raise SystemExit(f"expected base seedVersion 75 or in-review 76, got {ver}")
    # Keep v76 for same-wave review (do not bump again).
    cdn["seedVersion"] = 76
    cdn["rows"] = len(seed)
    payload = json.dumps(
        [{k: v for k, v in r.items() if v is not None} for r in seed],
        separators=(",", ":"),
        ensure_ascii=False,
    )
    cdn["bytes"] = len(payload.encode())
    cdn["updatedAt"] = datetime.now(timezone.utc).isoformat()
    cdn["note"] = (
        "seedVersion 76: selective Manus PHEV recovery (Toyota/Cupra verified); "
        "BMW 225e 2022 range reverted — no admissible 2022 proof"
    )
    SEED.write_text(json.dumps(seed, ensure_ascii=False, separators=(",", ":")) + "\n")
    CDN.write_text(json.dumps(cdn, indent=2) + "\n")

    man = {
        "seedVersion": 76,
        "prevSeedVersion": 75,
        "ids_before": ids_before,
        "phev_complete_before": before[0],
        "phev_only_kwh_before": before[1],
        "phev_multi_missing_before": before[2],
        "phev_complete_after": after[0],
        "phev_only_kwh_after": after[1],
        "phev_multi_missing_after": after[2],
        "fields_changed": [c for c in changed if c["decision"] == "accepted"],
        "rejected": [c for c in changed if c["decision"] == "rejected"],
        "bmw_225e_2022_range": "reverted_to_main_nil",
        "new_rows": [],
    }
    CACHE.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(man, indent=2) + "\n")
    AUDIT.parent.mkdir(parents=True, exist_ok=True)
    AUDIT.write_text(json.dumps({"decisions": changed, "manifest": man}, indent=2) + "\n")
    print(
        json.dumps(
            {
                "seedVersion": 76,
                "before": before,
                "after": after,
                "accepted": len(man["fields_changed"]),
                "rejected": len(man["rejected"]),
                "bmw_range": "nil",
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
