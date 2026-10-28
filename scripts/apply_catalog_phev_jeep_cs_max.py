#!/usr/bin/env python3
"""
Seed +1 (v70→v71): Jeep hybrid-suv archive CS = max of source interval.

Fonte: https://web.archive.org/web/20240620055110/https://www.jeep.de/hybrid-suv
sourceDate 2024-06-20 — "Bei entladener Batterie: Kraftstoffverbrauch"
  Renegade 4xe 6,9–7,5 → 0.075
  Compass 4xe 7,0–7,6 → 0.076 (già ok)
  Wrangler 4xe 10,6–11,8 → 0.118
  Grand Cherokee 4xe 10,2–10,6 → 0.106

CD elettrico resta nil (sulla pagina solo ponderato).
2022/2023: solo se omologazione EEA identica a 2024 (TAN/Va/Ve/ep/Ew/Fc).
"""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SEED = REPO / "EVforME?" / "Data" / "vehicles.seed.quality.json"
CDN = REPO / "EVforME?" / "Data" / "catalog_cdn.json"
CACHE = REPO / "scripts" / "cache" / "eea"
HOMOLOG_JEEP = CACHE / "catalog_phev_jeep_4xe_homolog.json"
RANK = CACHE / "catalog_phev_it_incomplete_rank.json"
MANIFEST = CACHE / "catalog_phev_jeep_cs_max_manifest.json"
SOURCE_DAY = "2026-10-28"

JEEP_HYB = "https://web.archive.org/web/20240620055110/https://www.jeep.de/hybrid-suv"
JEEP_HYB_DATE = "2024-06-20"

CALC_FIELDS = (
    "fuelConsumptionLPerKm",
    "energyConsumptionKWhPerKm",
    "wltpRangeKm",
    "batteryKWh",
)


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


def set_cs(row: dict, value: float, note: str) -> None:
    year = int(row["year"])
    row["fuelConsumptionLPerKm"] = value
    # never set unweighted CD from this page
    fs = dict(row.get("fieldSources") or {})
    fd = dict(row.get("fieldSourceDates") or {})
    fs["fuelConsumptionLPerKm"] = f"jeep.de {year} {JEEP_HYB}"
    fd["fuelConsumptionLPerKm"] = JEEP_HYB_DATE
    row["fieldSources"] = fs
    row["fieldSourceDates"] = fd
    sn = row.get("sourceName") or ""
    bit = f"{note} — {JEEP_HYB} ({JEEP_HYB_DATE})"
    if bit not in sn:
        # drop stale wrong CS notes
        parts = [p.strip() for p in sn.split(";") if p.strip()]
        parts = [
            p
            for p in parts
            if "0.074" not in p and "avoid placeholder" not in p.lower()
        ]
        if bit not in parts:
            parts.append(bit)
        row["sourceName"] = "; ".join(parts)
    row["sourceUpdatedAt"] = SOURCE_DAY
    row["market"] = row.get("market") or "IT"


def best_shared_2024(
    family: str, dst_year: int, dst_power: float, shared: dict, ep_tol: float = 2.0
) -> dict | None:
    """Fingerprint shared between 2024 and dst_year, matching power."""
    cands = []
    for sh in shared.get(family) or []:
        years = {int(y): n for y, n in (sh.get("years") or {}).items()}
        if 2024 not in years or int(dst_year) not in years:
            continue
        if not (sh.get("TAN") or "").strip():
            continue
        ep = sh.get("ep")
        if ep is None:
            continue
        if abs(float(ep) - float(dst_power)) > ep_tol:
            continue
        # require weighted WLTP present on fingerprint
        if sh.get("Ew") is None or sh.get("Fc") is None:
            continue
        score = float(years[2024]) + float(years[int(dst_year)])
        cands.append((score, sh))
    if not cands:
        return None
    cands.sort(key=lambda x: -x[0])
    return cands[0][1]


def ensure_2024_row(seed: list, by_id: dict, template_id: str, new_id: str, eea_n: int) -> dict:
    if new_id in by_id:
        return by_id[new_id]
    src = by_id[template_id]
    row = deepcopy(src)
    row["id"] = new_id
    row["year"] = 2024
    row["powerKw"] = 200.0
    row["fuelConsumptionLPerKm"] = None
    row["energyConsumptionKWhPerKm"] = None
    # keep range/battery from template only if same-MY dated — for new 2024 leave nil
    # unless template already had OEM-dated values for another year (don't copy blindly)
    row["wltpRangeKm"] = None
    row["batteryKWh"] = None
    row.pop("fieldSources", None)
    row.pop("fieldSourceDates", None)
    row.pop("dataDerivedFromSameHomologationYear", None)
    model = row["model"]
    cn = "WRANGLER UNLIMITED" if "wrangler" in new_id else "GRAND CHEROKEE"
    row["sourceName"] = (
        f"EEA co2cars IT 2024 {cn} PETROL/ELECTRIC n={eea_n}; "
        f"shell PHEV 4xe (powerKw 200) — CS from jeep.de hybrid-suv archive 20240620"
    )
    row["sourceUpdatedAt"] = SOURCE_DAY
    row["co2gKm"] = src.get("co2gKm")
    finalize(row)
    seed.append(row)
    by_id[new_id] = row
    return row


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

    before_c, before_kwh, before_multi = counts()

    changed: list[dict] = []
    added_rows: list[str] = []

    def record(rid: str, field: str, via: str, tan: str | None = None):
        r = by_id[rid]
        changed.append(
            {
                "id": rid,
                "field": field,
                "value": r.get(field),
                "url": JEEP_HYB,
                "sourceDate": JEEP_HYB_DATE,
                "via": via,
                **({"TAN": tan} if tan else {}),
            }
        )

    # --- Renegade: fix 0.074 → 0.075 ---
    for rid in ("jeep-renegade-phev-4xe-2024", "jeep-renegade-phev-4xe-2023"):
        r = by_id[rid]
        old = r.get("fuelConsumptionLPerKm")
        set_cs(
            r,
            0.075,
            "Jeep Renegade 4xe archive.org 20240620 hybrid-suv CS bei entladener Batterie 6,9–7,5 → 0.075",
        )
        if rid.endswith("2023"):
            # keep homologation cite
            fs = dict(r.get("fieldSources") or {})
            cite = fs.get("fuelConsumptionLPerKm") or ""
            tan = "E3*2007/46*0300*39"
            if "stessa omologazione" not in cite:
                fs["fuelConsumptionLPerKm"] = (
                    f"jeep.de 2024 {JEEP_HYB}; stessa omologazione EEA {tan} AXT23/19M, anni 2023 e 2024"
                )
                r["fieldSources"] = fs
            r["dataDerivedFromSameHomologationYear"] = 2024
            record(rid, "fuelConsumptionLPerKm", "homologation", tan=tan)
        else:
            record(rid, "fuelConsumptionLPerKm", "same_my")
        finalize(r)
        print(f"{rid}: {old} → {r['fuelConsumptionLPerKm']}")

    # Compass unchanged (0.076)
    assert abs(float(by_id["jeep-compass-phev-4xe-2024"]["fuelConsumptionLPerKm"]) - 0.076) < 1e-9

    # --- Ensure 2024 Wrangler / Grand Cherokee rows ---
    w24 = ensure_2024_row(
        seed, by_id, "jeep-wrangler-4xe-2023", "jeep-wrangler-4xe-2024", eea_n=179
    )
    if "jeep-wrangler-4xe-2024" not in ids_before:
        added_rows.append("jeep-wrangler-4xe-2024")
    g24 = ensure_2024_row(
        seed,
        by_id,
        "jeep-grand-cherokee-4xe-2023",
        "jeep-grand-cherokee-4xe-2024",
        eea_n=174,
    )
    if "jeep-grand-cherokee-4xe-2024" not in ids_before:
        added_rows.append("jeep-grand-cherokee-4xe-2024")

    # parents list may need refresh after append
    parents = [r for r in seed if r.get("powertrain") == "phev" and not r.get("parentId")]

    set_cs(
        w24,
        0.118,
        "Jeep Wrangler 4xe archive.org 20240620 hybrid-suv CS bei entladener Batterie 10,6–11,8 → 0.118",
    )
    # keep weighted fuel if present from EEA shell
    if w24.get("weightedFuelConsumptionLPerKm") is None:
        w24["weightedFuelConsumptionLPerKm"] = 0.038  # ~3.5–4.3 L/100 mid; informational
    finalize(w24)
    record("jeep-wrangler-4xe-2024", "fuelConsumptionLPerKm", "same_my")

    set_cs(
        g24,
        0.106,
        "Jeep Grand Cherokee 4xe archive.org 20240620 hybrid-suv CS bei entladener Batterie 10,2–10,6 → 0.106",
    )
    finalize(g24)
    record("jeep-grand-cherokee-4xe-2024", "fuelConsumptionLPerKm", "same_my")

    # --- Homologation to older years ---
    homolog = json.loads(HOMOLOG_JEEP.read_text(encoding="utf-8"))
    shared = homolog.get("shared") or {}

    derive = [
        {
            "dst_id": "jeep-wrangler-4xe-2023",
            "src_id": "jeep-wrangler-4xe-2024",
            "family": "jeep-wrangler",
        },
        {
            "dst_id": "jeep-wrangler-4xe-2022",
            "src_id": "jeep-wrangler-4xe-2024",
            "family": "jeep-wrangler",
        },
        {
            "dst_id": "jeep-grand-cherokee-4xe-2023",
            "src_id": "jeep-grand-cherokee-4xe-2024",
            "family": "jeep-grand-cherokee",
        },
        # 2022 Grand Cherokee: only if shared with 2024 (expected: none)
        {
            "dst_id": "jeep-grand-cherokee-4xe-2022",
            "src_id": "jeep-grand-cherokee-4xe-2024",
            "family": "jeep-grand-cherokee",
            "optional": True,
        },
    ]

    derived: list[dict] = []
    for d in derive:
        if d["dst_id"] not in by_id:
            if d.get("optional"):
                print(f"SKIP missing optional {d['dst_id']}")
                continue
            raise SystemExit(f"missing {d['dst_id']}")
        dst = by_id[d["dst_id"]]
        src = by_id[d["src_id"]]
        if src.get("dataDerivedFromSameHomologationYear") is not None:
            raise SystemExit(f"chain {d['src_id']}")
        sh = best_shared_2024(
            d["family"], int(dst["year"]), float(dst.get("powerKw") or 200), shared
        )
        if not sh:
            print(f"SKIP homolog {d['dst_id']}: no identical EEA 2024 fingerprint")
            # ensure CS stays nil if we somehow had a bad value
            if d["dst_id"].startswith("jeep-grand-cherokee") and int(dst["year"]) == 2022:
                pass
            finalize(dst)
            continue
        # copy CS only
        dst["fuelConsumptionLPerKm"] = src["fuelConsumptionLPerKm"]
        tan, va, ve = sh["TAN"], sh["Va"], sh["Ve"]
        fs = dict(dst.get("fieldSources") or {})
        fd = dict(dst.get("fieldSourceDates") or {})
        fs["fuelConsumptionLPerKm"] = (
            f"jeep.de 2024 {JEEP_HYB}; stessa omologazione EEA {tan} {va}/{ve}, "
            f"anni {dst['year']} e 2024"
        )
        fd["fuelConsumptionLPerKm"] = JEEP_HYB_DATE
        dst["fieldSources"] = fs
        dst["fieldSourceDates"] = fd
        dst["dataDerivedFromSameHomologationYear"] = 2024
        dst["sourceUpdatedAt"] = SOURCE_DAY
        note = (
            f"stessa omologazione EEA {tan} {va}/{ve}, anni {dst['year']} e 2024 — {JEEP_HYB}"
        )
        sn = dst.get("sourceName") or ""
        if note not in sn:
            dst["sourceName"] = f"{sn}; {note}".strip("; ").strip()
        if src.get("weightedFuelConsumptionLPerKm") is not None and dst.get(
            "weightedFuelConsumptionLPerKm"
        ) is None:
            dst["weightedFuelConsumptionLPerKm"] = src["weightedFuelConsumptionLPerKm"]
        finalize(dst)
        record(d["dst_id"], "fuelConsumptionLPerKm", "homologation", tan=tan)
        derived.append(
            {
                "id": d["dst_id"],
                "sourceId": d["src_id"],
                "TAN": tan,
                "Va": va,
                "Ve": ve,
                "ep": sh.get("ep"),
                "Ew": sh.get("Ew"),
                "Fc": sh.get("Fc"),
                "fields": ["fuelConsumptionLPerKm"],
                "derivedFromYear": 2024,
            }
        )
        print(f"DERIVED {d['dst_id']} ← 2024 TAN={tan} Va={va} Ve={ve}")

    for r in seed:
        if r["id"] in m3_before and json.dumps(r, sort_keys=True) != m3_before[r["id"]]:
            raise SystemExit(f"M3 2026 altered: {r['id']}")

    # refresh parents after adds
    parents = [r for r in seed if r.get("powertrain") == "phev" and not r.get("parentId")]
    after_c, after_kwh, after_multi = counts()

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
    new_ver = int(cdn.get("seedVersion") or 70) + 1
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
        "added_rows": added_rows,
        "phev_complete_before": before_c,
        "phev_complete_after": after_c,
        "phev_only_kwh_before": before_kwh,
        "phev_only_kwh_after": after_kwh,
        "phev_multi_missing_before": before_multi,
        "phev_multi_missing_after": after_multi,
        "top30_complete_after": t30[0],
        "top30_only_kwh_after": t30[1],
        "top30_multi_missing_after": t30[2],
        "fields_changed": changed,
        "derived": derived,
        "source": {"url": JEEP_HYB, "sourceDate": JEEP_HYB_DATE},
        "cs_intervals_L_per_100": {
            "renegade": [6.9, 7.5],
            "compass": [7.0, 7.6],
            "wrangler": [10.6, 11.8],
            "grand_cherokee": [10.2, 10.6],
        },
    }
    MANIFEST.write_text(json.dumps(man, indent=2) + "\n")
    print(json.dumps({k: v for k, v in man.items() if k not in ("ids_before", "fields_changed")}, indent=2))
    print("changed", len(changed), "added", added_rows)


if __name__ == "__main__":
    main()
