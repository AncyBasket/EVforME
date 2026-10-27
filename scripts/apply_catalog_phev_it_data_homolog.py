#!/usr/bin/env python3
"""
PHEV IT data wave-2 (seed +1 from current):

1) Same-MY OEM completions (CS≥3, CD unweighted, range, battery).
2) Homologation copy: incomplete year may copy CS/CD/range/battery from a
   COMPLETE same-model year ONLY if EEA IT fingerprints match exactly on
   TAN, Va, Ve, ep, ec, m, Mt, Ewltp, Fc. No chain (source must not be derived).

Tesla Model 3 2026 untouched; no removals.
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
MANIFEST = CACHE / "catalog_phev_it_data_homolog_manifest.json"
SOURCE_DAY = "2026-10-27"

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
        r.get("TAN") or "",
        r.get("Va") or "",
        r.get("Ve") or "",
        r.get("ep"),
        r.get("ec"),
        r.get("m"),
        r.get("Mt"),
        r.get("Ew"),
        r.get("Fc"),
    )


def best_shared(
    family_key: str,
    src_year: int,
    dst_year: int,
    dst_power_kw: float,
    shared: dict,
) -> dict | None:
    """Pick highest-n shared fingerprint with ep ≈ catalog powerKw."""
    cands = []
    for sh in shared.get(family_key) or []:
        years = {int(y): n for y, n in (sh.get("years") or {}).items()}
        if src_year not in years or dst_year not in years:
            continue
        ep = sh.get("ep")
        if ep is None:
            continue
        if abs(float(ep) - float(dst_power_kw)) > 2.0:
            continue
        # reject empty TAN (rule requires type-approval number)
        if not (sh.get("TAN") or "").strip():
            continue
        score = float(years[src_year]) + float(years[dst_year])
        cands.append((score, sh))
    if not cands:
        return None
    cands.sort(key=lambda x: -x[0])
    return cands[0][1]


def assert_complete(r: dict, rid: str) -> None:
    cs = r.get("fuelConsumptionLPerKm")
    if cs is None or float(cs) * 100 < 3.0:
        raise SystemExit(f"incomplete CS {rid}")
    if r.get("energyConsumptionKWhPerKm") is None:
        raise SystemExit(f"incomplete CD {rid}")
    if r.get("energyIsWeighted") is True:
        raise SystemExit(f"weighted CD {rid}")
    if r.get("wltpRangeKm") is None or r.get("batteryKWh") is None:
        raise SystemExit(f"incomplete range/bat {rid}")
    if r.get("catalogDataIncomplete"):
        raise SystemExit(f"still flagged incomplete {rid}")


def main() -> None:
    seed = json.loads(SEED.read_text(encoding="utf-8"))
    by_id = {r["id"]: r for r in seed}
    ids_before = [r["id"] for r in seed]
    m3_before = {
        r["id"]: json.dumps(r, sort_keys=True)
        for r in seed
        if r["id"].startswith("tesla-model-3") and r.get("year") == 2026
    }

    before_complete = sum(
        1
        for r in seed
        if r.get("powertrain") == "phev"
        and not r.get("parentId")
        and not r.get("catalogDataIncomplete")
    )
    before_same_my = sum(
        1
        for r in seed
        if r.get("powertrain") == "phev"
        and not r.get("parentId")
        and not r.get("catalogDataIncomplete")
        and r.get("dataDerivedFromSameHomologationYear") is None
    )
    before_derived = sum(
        1
        for r in seed
        if r.get("powertrain") == "phev"
        and not r.get("parentId")
        and not r.get("catalogDataIncomplete")
        and r.get("dataDerivedFromSameHomologationYear") is not None
    )

    homolog = json.loads(HOMOLOG.read_text(encoding="utf-8"))
    shared = homolog.get("shared") or {}

    same_my_completed: list[dict] = []
    # (none new this wave — Kuga 2024 already complete on branch)
    derived_completed: list[dict] = []

    # --- Homologation derivations (source must be complete + not derived) ---
    DERIVATIONS = [
        {
            "dst_id": "ford-kuga-phev-2023",
            "src_id": "ford-kuga-phev-2024",
            "family": "ford-kuga",
            "oem_host": "ford.de",
            "oem_url": "https://www.ford.de/content/dam/guxeu/de/documents/price-list/cars/new-kuga/Technische_Daten_des_Ford_Kuga.pdf",
            "oem_year": 2024,
        },
    ]

    for d in DERIVATIONS:
        dst = by_id[d["dst_id"]]
        src = by_id[d["src_id"]]
        if src.get("catalogDataIncomplete"):
            raise SystemExit(f"source incomplete {d['src_id']}")
        if src.get("dataDerivedFromSameHomologationYear") is not None:
            raise SystemExit(f"chain forbidden: source {d['src_id']} is derived")
        assert_complete(src, d["src_id"])
        if dst.get("dataDerivedFromSameHomologationYear") is not None:
            raise SystemExit(f"dst already derived {d['dst_id']}")

        sh = best_shared(
            d["family"],
            int(src["year"]),
            int(dst["year"]),
            float(dst.get("powerKw") or 0),
            shared,
        )
        if not sh:
            raise SystemExit(
                f"no identical homologation {d['src_id']} → {d['dst_id']}"
            )

        for f in COPY_FIELDS:
            dst[f] = src[f]
        dst["energyIsWeighted"] = False
        dst["catalogDataIncomplete"] = False
        dst["confidenceScore"] = 0.85
        dst["market"] = "IT"
        dst["dataDerivedFromSameHomologationYear"] = int(src["year"])
        dst["sourceUpdatedAt"] = SOURCE_DAY
        tan = sh["TAN"]
        va, ve = sh["Va"], sh["Ve"]
        dst["sourceName"] = (
            f"{src.get('sourceName')}; "
            f"stessa omologazione EEA {tan} {va}/{ve}, "
            f"anni {dst['year']} e {src['year']} "
            f"(CS/CD/range/bat da MY{src['year']} OEM {d['oem_host']}: {d['oem_url']})"
        )
        derived_completed.append(
            {
                "id": d["dst_id"],
                "host": d["oem_host"],
                "year": int(dst["year"]),
                "url": d["oem_url"],
                "TAN": tan,
                "Va": va,
                "Ve": ve,
                "ep": sh["ep"],
                "derivedFromYear": int(src["year"]),
                "sourceId": d["src_id"],
            }
        )

    for r in seed:
        if r["id"] in m3_before and json.dumps(r, sort_keys=True) != m3_before[r["id"]]:
            raise SystemExit(f"M3 2026 altered: {r['id']}")

    cdn = json.loads(CDN.read_text(encoding="utf-8"))
    new_ver = int(cdn.get("seedVersion") or 67) + 1
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

    parents = [
        r for r in seed if not r.get("parentId") and r.get("powertrain") == "phev"
    ]
    after_complete = sum(1 for r in parents if not r.get("catalogDataIncomplete"))
    after_same_my = sum(
        1
        for r in parents
        if not r.get("catalogDataIncomplete")
        and r.get("dataDerivedFromSameHomologationYear") is None
    )
    after_derived = sum(
        1
        for r in parents
        if not r.get("catalogDataIncomplete")
        and r.get("dataDerivedFromSameHomologationYear") is not None
    )

    man = {
        "seedVersion": new_ver,
        "ids_before": ids_before,
        "phev_complete_before": before_complete,
        "phev_complete_after": after_complete,
        "phev_complete_same_my_before": before_same_my,
        "phev_complete_same_my_after": after_same_my,
        "phev_complete_derived_before": before_derived,
        "phev_complete_derived_after": after_derived,
        "same_my_completed": same_my_completed,
        "derived_completed": derived_completed,
        "completed_count": len(same_my_completed) + len(derived_completed),
    }
    MANIFEST.write_text(json.dumps(man, indent=2) + "\n")
    print(json.dumps({k: v for k, v in man.items() if k != "ids_before"}, indent=2))


if __name__ == "__main__":
    main()
