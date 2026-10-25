#!/usr/bin/env python3
"""
Remove catalog rows for models/years that never existed as Europe-sold cars,
or exact rename/duplicate rows already covered by another id.

seedVersion → 57.
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import fill_catalog_fuels_from_eea as eea

NEW_SEED_VERSION = 57
CONSULTED = "2026-10-25"
REPORT_PATH = eea.CACHE_DIR / "catalog_existence_removal_report.json"

# Verified KEEP (see report / PR). All other candidates are removed.
KEEP: dict[str, dict] = {
    "jaguar-i-pace-2025": {
        "reason": "EEA IT Zr model year IPACE 2025 (provisional)",
        "source": "EEA IT CO2 monitoring Zr cache IT_JAGUAR_bev_Zr.json",
        "kind": "eea",
    },
    "lexus-rz-2022": {
        "reason": "Lexus EU: first deliveries from end of 2022",
        "source": "https://newsroom.lexus.eu/world-premiere-of-the-all-new-lexus-rz/",
        "kind": "oem",
        "consulted": CONSULTED,
    },
}

# Candidate ids from PR #20 dubious list + scenic duplicate.
CANDIDATES = [
    *[f"hyundai-equus-{y}" for y in range(2022, 2027)],
    *[f"nissan-altra-ev-{y}" for y in range(2022, 2027)],
    "lucid-gravity-2022",
    "lucid-gravity-2023",
    "nio-el8-2021",
    "nio-el8-2022",
    "nio-et5-2021",
    "nio-et5-touring-2021",
    "nio-et5-touring-2022",
    "nio-el6-2021",
    "nio-el6-2022",
    "xpeng-g6-2021",
    "xpeng-g6-2022",
    "xpeng-g9-2021",
    "chevrolet-bolt-euv-2021",
    "jaguar-i-pace-2025",
    "jaguar-i-pace-2026",
    "lexus-rz-2022",
    "honda-e-2019",
    "mini-electric-hatch-2019",
    "kia-soul-ev-2024",
    "kia-soul-ev-2025",
    "kia-soul-ev-2026",
    "volvo-c40-recharge-2025",
    "volvo-c40-recharge-2026",
    "volvo-xc40-recharge-2025",
    "volvo-xc40-recharge-2026",
    "renault-scenic-2024",
]

REMOVAL_REASONS: dict[str, str] = {
    **{
        f"hyundai-equus-{y}": "no EEA EV Equus; Hyundai never sold Equus EV in Europe"
        for y in range(2022, 2027)
    },
    **{
        f"nissan-altra-ev-{y}": "no EEA; Altra EV was 1990s Japan/US concept era, not EU catalog year"
        for y in range(2022, 2027)
    },
    "lucid-gravity-2022": "no EEA Lucid; Gravity EU sales not in 2022",
    "lucid-gravity-2023": "no EEA Lucid; Gravity not sold EU 2023 in EEA IT",
    "nio-el8-2021": "no EEA NIO brand cache; EL8 not in EEA IT for 2021",
    "nio-el8-2022": "no EEA NIO brand cache; EL8 not in EEA IT for 2022",
    "nio-et5-2021": "no EEA NIO; ET5 not in EEA IT for 2021",
    "nio-et5-touring-2021": "no EEA NIO; ET5 Touring not in EEA IT for 2021",
    "nio-et5-touring-2022": "no EEA NIO; ET5 Touring not in EEA IT for 2022",
    "nio-el6-2021": "no EEA NIO; EL6 not in EEA IT for 2021",
    "nio-el6-2022": "no EEA NIO; EL6 not in EEA IT for 2022",
    "xpeng-g6-2021": "EEA XPeng G6 only from 2025; no 2021 model year",
    "xpeng-g6-2022": "EEA XPeng G6 only from 2025; no 2022 model year",
    "xpeng-g9-2021": "EEA XPeng G9 only from 2025; no 2021 model year",
    "chevrolet-bolt-euv-2021": "no EEA Chevrolet BEV cache; Bolt EUV not EU type-approved in EEA IT",
    "jaguar-i-pace-2026": "EEA IPACE years through 2025 only; no 2026 Zr",
    "honda-e-2019": "Honda EU: first deliveries summer 2020 (not 2019 sales year)",
    "mini-electric-hatch-2019": "BMW/MINI press: orders 2019, first deliveries March 2020 — no 2019 delivery year",
    "kia-soul-ev-2024": "EEA SOUL EV years 2020–2022 only",
    "kia-soul-ev-2025": "EEA SOUL EV years 2020–2022 only",
    "kia-soul-ev-2026": "EEA SOUL EV years 2020–2022 only",
    "volvo-c40-recharge-2025": "rename duplicate: catalog already has volvo-ec40-2025 (EEA EC40 2025)",
    "volvo-c40-recharge-2026": "no EEA C40 2026; renamed to EC40 (volvo-ec40-2026 present)",
    "volvo-xc40-recharge-2025": "rename duplicate: catalog already has volvo-ex40-2025 (EEA EX40 2025)",
    "volvo-xc40-recharge-2026": "no EEA XC40 EV 2026; renamed to EX40 (volvo-ex40-2026 present)",
    "renault-scenic-2024": "exact duplicate of renault-scenic-e-tech-2024 (same brand/model/year)",
}


def bump_seed(rows: list[dict]) -> None:
    raw = eea.SEED_PATH.read_bytes()
    cdn = json.loads(eea.CDN_PATH.read_text(encoding="utf-8"))
    cdn["seedVersion"] = NEW_SEED_VERSION
    cdn["rows"] = len(rows)
    cdn["bytes"] = len(raw)
    cdn["updatedAt"] = datetime.now(timezone.utc).isoformat()
    cdn["note"] = (
        f"seedVersion {NEW_SEED_VERSION}: removed nonexistent / duplicate EV rows "
        "(existence audit); kept jaguar-i-pace-2025 (EEA), lexus-rz-2022 (OEM)."
    )
    eea.CDN_PATH.write_text(
        json.dumps(cdn, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    text = eea.CATALOG_SERVICE.read_text(encoding="utf-8")
    text2, n = re.subn(
        r"static let bundledSeedVersion = \d+",
        f"static let bundledSeedVersion = {NEW_SEED_VERSION}",
        text,
        count=1,
    )
    if n != 1:
        raise RuntimeError("Could not set bundledSeedVersion")
    eea.CATALOG_SERVICE.write_text(text2, encoding="utf-8")


def strip_refs(removed: set[str]) -> dict[str, int]:
    counts: dict[str, int] = {}

    # battery refs
    for path in (
        eea.CACHE_DIR / "catalog_truth_battery_refs.json",
        eea.REPO / "EVforME?Tests" / "Fixtures" / "catalog_truth_battery_refs.json",
    ):
        if not path.is_file():
            continue
        refs = json.loads(path.read_text(encoding="utf-8"))
        before = len(refs.get("nilled") or [])
        refs["nilled"] = [n for n in (refs.get("nilled") or []) if n.get("id") not in removed]
        refs["corrected"] = [
            c for c in (refs.get("corrected") or []) if c.get("id") not in removed
        ]
        if "dubious_models_no_delete" in refs:
            refs["dubious_models_no_delete"] = [
                i for i in refs["dubious_models_no_delete"] if i not in removed
            ]
        if "eea_verified_ids" in refs:
            refs["eea_verified_ids"] = [
                i for i in refs["eea_verified_ids"] if i not in removed
            ]
        refs["seedVersion"] = NEW_SEED_VERSION
        path.write_text(json.dumps(refs, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        counts["battery_nilled_dropped"] = before - len(refs.get("nilled") or [])

    # range refs
    for path in (
        eea.CACHE_DIR / "catalog_truth_range_refs.json",
        eea.REPO / "EVforME?Tests" / "Fixtures" / "catalog_truth_range_refs.json",
    ):
        if not path.is_file():
            continue
        refs = json.loads(path.read_text(encoding="utf-8"))
        fills_b = len(refs.get("fills") or [])
        refs["fills"] = [f for f in (refs.get("fills") or []) if f.get("id") not in removed]
        refs["skips"] = [s for s in (refs.get("skips") or []) if s.get("id") not in removed]
        refs["seedVersion"] = NEW_SEED_VERSION
        path.write_text(json.dumps(refs, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        counts["range_fills_dropped"] = fills_b - len(refs.get("fills") or [])

    # eea refs (list)
    for path in (
        eea.CACHE_DIR / "catalog_truth_eea_refs.json",
        eea.REPO / "EVforME?Tests" / "Fixtures" / "catalog_truth_eea_refs.json",
    ):
        if not path.is_file():
            continue
        refs = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(refs, list):
            before = len(refs)
            refs = [r for r in refs if (r.get("id") if isinstance(r, dict) else r) not in removed]
            counts["eea_refs_dropped"] = before - len(refs)
            path.write_text(json.dumps(refs, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        elif isinstance(refs, dict):
            for key in ("fills", "rows", "entries", "items"):
                if key in refs and isinstance(refs[key], list):
                    before = len(refs[key])
                    refs[key] = [
                        r
                        for r in refs[key]
                        if (r.get("id") if isinstance(r, dict) else r) not in removed
                    ]
                    counts[f"eea_{key}_dropped"] = before - len(refs[key])
            refs["seedVersion"] = NEW_SEED_VERSION
            path.write_text(json.dumps(refs, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    return counts


def main() -> int:
    rows: list[dict] = json.loads(eea.SEED_PATH.read_text(encoding="utf-8"))
    before = len(rows)
    by_id = {r["id"]: r for r in rows}

    removed: list[dict] = []
    kept: list[dict] = []
    missing_candidates: list[str] = []

    for rid in CANDIDATES:
        if rid not in by_id:
            missing_candidates.append(rid)
            continue
        if rid in KEEP:
            kept.append({"id": rid, **KEEP[rid]})
            continue
        reason = REMOVAL_REASONS.get(rid, "not verified in EEA / OEM for Europe that year")
        removed.append({"id": rid, "reason": reason, "snapshot": {
            "brand": by_id[rid].get("brand"),
            "model": by_id[rid].get("model"),
            "year": by_id[rid].get("year"),
            "powertrain": by_id[rid].get("powertrain"),
        }})

    remove_ids = {r["id"] for r in removed}
    new_rows = [r for r in rows if r["id"] not in remove_ids]
    after = len(new_rows)

    eea.SEED_PATH.write_text(
        json.dumps(new_rows, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    bump_seed(new_rows)
    ref_counts = strip_refs(remove_ids)

    report = {
        "seedVersion": NEW_SEED_VERSION,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "consulted_date": CONSULTED,
        "counts": {
            "rows_before": before,
            "rows_after": after,
            "removed": len(removed),
            "kept_from_candidates": len(kept),
        },
        "kept": kept,
        "removed": removed,
        "missing_candidates": missing_candidates,
        "ref_strip": ref_counts,
    }
    eea.CACHE_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"rows {before} → {after} removed={len(removed)} kept={len(kept)} "
        f"seed={NEW_SEED_VERSION}"
    )
    for k in kept:
        print(f"  KEEP {k['id']}: {k['reason']}")
    for r in removed:
        print(f"  DROP {r['id']}: {r['reason']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
