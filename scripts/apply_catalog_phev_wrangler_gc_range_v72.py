#!/usr/bin/env python3
"""
Seed +1 (v71→v72):
1) Wrangler 4xe 2022: drop EAER City range (PDF has only City, no combined EAER) → nil;
   keep battery 17.3 with fieldSources/fieldSourceDates 2022-01-25.
2) Grand Cherokee 4xe 2024: copy range 44 + battery 17.3 from 2023 MJ23 listino via
   identical EEA homologation (TAN E9*2018/858*11257*01 JCACG/5HP1S),
   dataDerivedFromSameHomologationYear=2023. No chain. CD stays nil.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SEED = REPO / "EVforME?" / "Data" / "vehicles.seed.quality.json"
CDN = REPO / "EVforME?" / "Data" / "catalog_cdn.json"
CACHE = REPO / "scripts" / "cache" / "eea"
RANK = CACHE / "catalog_phev_it_incomplete_rank.json"
MANIFEST = CACHE / "catalog_phev_wrangler_gc_range_v72_manifest.json"
SOURCE_DAY = "2026-10-28"

WRANGLER_PDF = (
    "https://www.media.stellantis.com/uploads/de/model-document/"
    "220101_j_wrangler_jl_td_01012022-61dd98f991688.pdf"
)
WRANGLER_PDF_DATE = "2022-01-25"  # Stand cited as 25.01.2022 / sheet header 01.01.2022

GC_PDF = (
    "https://www.media.stellantis.com/uploads/de/model-pricelist/"
    "preisliste_grand_cherokee_4xe_januar_20234-6486c171a11d8.pdf"
)
GC_PDF_DATE = "2023-01-01"  # MJ23 gültig ab 01/2023
GC_TAN = "E9*2018/858*11257*01"
GC_VA = "JCACG"
GC_VE = "5HP1S"


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

    def counts():
        complete = sum(1 for r in parents if not r.get("catalogDataIncomplete"))
        only_kwh = multi = 0
        for r in parents:
            if not r.get("catalogDataIncomplete"):
                continue
            miss = missing_calc_fields(r)
            if miss == ["energyConsumptionKWhPerKm"]:
                only_kwh += 1
            else:
                multi += 1
        return complete, only_kwh, multi

    before = counts()
    changed: list[dict] = []

    # --- 1) Wrangler 2022: nil City EAER; keep battery with dated fieldSources ---
    w22 = by_id["jeep-wrangler-4xe-2022"]
    old_range = w22.get("wltpRangeKm")
    w22["wltpRangeKm"] = None
    # Ensure battery provenance
    w22["batteryKWh"] = 17.3
    fs = dict(w22.get("fieldSources") or {})
    fd = dict(w22.get("fieldSourceDates") or {})
    fs.pop("wltpRangeKm", None)
    fd.pop("wltpRangeKm", None)
    fs["batteryKWh"] = f"media.stellantis.com 2022 {WRANGLER_PDF}"
    fd["batteryKWh"] = WRANGLER_PDF_DATE
    w22["fieldSources"] = fs
    w22["fieldSourceDates"] = fd
    sn = w22.get("sourceName") or ""
    note = (
        "EAER City 45/53 km (Sahara/Rubicon) rejected — not combined EAER → wltpRangeKm nil; "
        f"battery 17,3 kWh kept — {WRANGLER_PDF} ({WRANGLER_PDF_DATE})"
    )
    # scrub stale "EAER City … 45 km" claim as usable range
    parts = [p.strip() for p in sn.split(";") if p.strip()]
    scrubbed = []
    for p in parts:
        low = p.lower()
        if "eaer city" in low and "45" in p and "rejected" not in low:
            continue
        scrubbed.append(p)
    if note not in "; ".join(scrubbed):
        scrubbed.append(note)
    w22["sourceName"] = "; ".join(scrubbed)
    w22["sourceUpdatedAt"] = SOURCE_DAY
    finalize(w22)
    changed.append(
        {
            "id": "jeep-wrangler-4xe-2022",
            "field": "wltpRangeKm",
            "value": None,
            "old": old_range,
            "url": WRANGLER_PDF,
            "sourceDate": WRANGLER_PDF_DATE,
            "via": "reject_eaer_city",
            "reason": "PDF only lists Elektrische Reichweite EAER City (45/53); no combined EAER",
        }
    )
    changed.append(
        {
            "id": "jeep-wrangler-4xe-2022",
            "field": "batteryKWh",
            "value": 17.3,
            "url": WRANGLER_PDF,
            "sourceDate": WRANGLER_PDF_DATE,
            "via": "same_my_doc",
        }
    )

    # --- 2) Grand Cherokee 2024 ← 2023 range/battery (OEM fields, not CS-derived) ---
    g23 = by_id["jeep-grand-cherokee-4xe-2023"]
    g24 = by_id["jeep-grand-cherokee-4xe-2024"]
    # Source range/battery must be OEM on 2023 (not homologation-copied)
    assert g23.get("wltpRangeKm") == 44
    assert abs(float(g23.get("batteryKWh")) - 17.3) < 1e-9
    g23_fs = g23.get("fieldSources") or {}
    for k in ("wltpRangeKm", "batteryKWh"):
        cite = g23_fs.get(k) or ""
        if "stessa omologazione" in cite:
            raise SystemExit(f"chain risk: 2023 {k} already homolog-derived")
    # Ensure 2023 has fieldSources for these OEM fields (listino MJ23)
    g23_fs = dict(g23_fs)
    g23_fd = dict(g23.get("fieldSourceDates") or {})
    g23_fs["wltpRangeKm"] = f"media.stellantis.com 2023 {GC_PDF}"
    g23_fs["batteryKWh"] = f"media.stellantis.com 2023 {GC_PDF}"
    g23_fd["wltpRangeKm"] = GC_PDF_DATE
    g23_fd["batteryKWh"] = GC_PDF_DATE
    g23["fieldSources"] = g23_fs
    g23["fieldSourceDates"] = g23_fd
    finalize(g23)

    # 2024 must not already be a homologation destination for a further hop (no chain out)
    # CS on 2024 is same_my archive — OK. Set derivedFrom=2023 for range/battery copy.
    if g24.get("dataDerivedFromSameHomologationYear") not in (None, 2023):
        # currently None — OK
        pass

    g24["wltpRangeKm"] = 44
    g24["batteryKWh"] = 17.3
    g24_fs = dict(g24.get("fieldSources") or {})
    g24_fd = dict(g24.get("fieldSourceDates") or {})
    homolog_bit = (
        f"stessa omologazione EEA {GC_TAN} {GC_VA}/{GC_VE}, anni 2024 e 2023"
    )
    for k in ("wltpRangeKm", "batteryKWh"):
        g24_fs[k] = f"media.stellantis.com 2023 {GC_PDF}; {homolog_bit}"
        g24_fd[k] = GC_PDF_DATE
    g24["fieldSources"] = g24_fs
    g24["fieldSourceDates"] = g24_fd
    g24["dataDerivedFromSameHomologationYear"] = 2023
    g24["sourceUpdatedAt"] = SOURCE_DAY
    note24 = (
        f"EAER 44 km (min 44–48) + battery 17,3 kWh from MJ23 listino via {homolog_bit} — "
        f"{GC_PDF} ({GC_PDF_DATE})"
    )
    sn24 = g24.get("sourceName") or ""
    if note24 not in sn24:
        g24["sourceName"] = f"{sn24}; {note24}".strip("; ").strip()
    # energy stays nil
    assert g24.get("energyConsumptionKWhPerKm") is None
    finalize(g24)
    for field, val in (("wltpRangeKm", 44), ("batteryKWh", 17.3)):
        changed.append(
            {
                "id": "jeep-grand-cherokee-4xe-2024",
                "field": field,
                "value": val,
                "url": GC_PDF,
                "sourceDate": GC_PDF_DATE,
                "via": "homologation",
                "TAN": GC_TAN,
                "Va": GC_VA,
                "Ve": GC_VE,
                "derivedFromYear": 2023,
            }
        )

    for r in seed:
        if r["id"] in m3_before and json.dumps(r, sort_keys=True) != m3_before[r["id"]]:
            raise SystemExit(f"M3 2026 altered: {r['id']}")

    after = counts()
    regs = {}
    if RANK.exists():
        rank = json.loads(RANK.read_text(encoding="utf-8"))
        for e in (rank.get("all_incomplete") or []) + (rank.get("top") or []):
            regs[e["id"]] = e.get("regs") or e.get("n") or 0
    top30 = sorted(parents, key=lambda r: -float(regs.get(r["id"]) or 0))[:30]

    def top_bucket(rows):
        c = sum(1 for r in rows if not r.get("catalogDataIncomplete"))
        kwh = sum(
            1
            for r in rows
            if r.get("catalogDataIncomplete")
            and missing_calc_fields(r) == ["energyConsumptionKWhPerKm"]
        )
        return c, kwh, len(rows) - c - kwh

    t30 = top_bucket(top30)

    cdn = json.loads(CDN.read_text(encoding="utf-8"))
    new_ver = int(cdn.get("seedVersion") or 71) + 1
    if new_ver != 72:
        raise SystemExit(f"expected seed 72, got path to {new_ver}")
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
        "phev_complete_before": before[0],
        "phev_complete_after": after[0],
        "phev_only_kwh_before": before[1],
        "phev_only_kwh_after": after[1],
        "phev_multi_missing_before": before[2],
        "phev_multi_missing_after": after[2],
        "top30_complete_after": t30[0],
        "top30_only_kwh_after": t30[1],
        "top30_multi_missing_after": t30[2],
        "fields_changed": changed,
        "wrangler_pdf_eaer": {
            "url": WRANGLER_PDF,
            "sourceDate": WRANGLER_PDF_DATE,
            "combined_eaer_found": False,
            "city_only": [45, 53],
            "action": "wltpRangeKm_nil",
        },
        "gc_homolog": {
            "TAN": GC_TAN,
            "Va": GC_VA,
            "Ve": GC_VE,
            "derivedFromYear": 2023,
            "url": GC_PDF,
            "sourceDate": GC_PDF_DATE,
        },
    }
    MANIFEST.write_text(json.dumps(man, indent=2) + "\n")
    print(
        json.dumps(
            {k: v for k, v in man.items() if k not in ("ids_before", "fields_changed")},
            indent=2,
        )
    )
    print("changed", len(changed))
    print(
        "w22 miss",
        w22.get("missingCalcFields"),
        "range",
        w22.get("wltpRangeKm"),
        "bat",
        w22.get("batteryKWh"),
    )
    print(
        "g24 miss",
        g24.get("missingCalcFields"),
        "range",
        g24.get("wltpRangeKm"),
        "bat",
        g24.get("batteryKWh"),
        "derived",
        g24.get("dataDerivedFromSameHomologationYear"),
    )


if __name__ == "__main__":
    main()
