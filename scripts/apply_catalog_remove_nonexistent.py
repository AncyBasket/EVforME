#!/usr/bin/env python3
"""
Remove catalog rows for models/years not sold in Europe (EEA all-MS / OEM),
or parallel/ambiguous ids. Restore rows wrongly dropped earlier.

seedVersion → 57 (no app marketing bump).
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import fill_catalog_fuels_from_eea as eea

NEW_SEED_VERSION = 57
CONSULTED = "2026-10-26"
REPORT_PATH = eea.CACHE_DIR / "catalog_existence_removal_report.json"

# KEEP with source (EEA EU-wide or OEM).
KEEP: dict[str, dict] = {
    "jaguar-i-pace-2025": {
        "reason": "EEA EU Zr IPACE 2025 (provisional registrations)",
        "source": "EEA CO2 monitoring Electric Zr (all MS) — Cn IPACE year 2025",
        "kind": "eea_eu",
    },
    "kia-soul-ev-2024": {
        "reason": "EEA EU: KIA SOUL electric 150 kW in 2024 (Final; DE/NL/NO/…)",
        "source": "EEA CO2 monitoring Electric Zr (all MS) — Cn SOUL year 2024 Status F",
        "kind": "eea_eu",
    },
    "kia-soul-ev-2025": {
        "reason": "EEA EU: KIA SOUL electric 150 kW in 2025 (Provisional; DE/FR/…)",
        "source": "EEA CO2 monitoring Electric Zr (all MS) — Cn SOUL year 2025 Status P",
        "kind": "eea_eu",
    },
    "nio-el8-2022": {
        "reason": "EEA EU: NIO Cn ES8.EL8 year 2022, 240 kW, DE registrations (same kW as catalog row)",
        "source": "EEA CO2 monitoring — Mk NIO Cn ES8.EL8 year 2022 MS=DE ep_KW=240",
        "kind": "eea_eu",
    },
    "volvo-c40-recharge-2025": {
        "reason": "EEA EU still has C40 EV registrations in 2025 (alongside EC40 rename)",
        "source": "EEA CO2 monitoring Electric Zr (all MS) — Cn C40 year 2025",
        "kind": "eea_eu",
    },
    "volvo-xc40-recharge-2025": {
        "reason": "EEA EU still has XC40 EV registrations in 2025 (alongside EX40 rename)",
        "source": "EEA CO2 monitoring Electric Zr (all MS) — Cn XC40 year 2025",
        "kind": "eea_eu",
    },
}

# Always remove these (candidates that fail EU EEA / OEM delivery-year proof).
REMOVE: dict[str, str] = {
    **{
        f"hyundai-equus-{y}": "no EEA EU Equus EV; Hyundai never sold Equus as EV in Europe"
        for y in range(2022, 2027)
    },
    **{
        f"nissan-altra-ev-{y}": "no EEA EU Altra-EV; not a Europe-sold EV in these years"
        for y in range(2022, 2027)
    },
    "lucid-gravity-2022": "EEA EU Lucid Gravity only from 2025; no 2022",
    "lucid-gravity-2023": "EEA EU Lucid Gravity only from 2025; no 2023",
    "nio-el8-2021": "EEA EU NIO ES8/EL8: no EL8/ES8.EL8 match for 2021 at catalog kW; ES8 2021 exists but EL8 nameplate EU later",
    "nio-et5-2021": "EEA EU Cn ET5 year 2021 is Mk SKYWELL (not NIO); NIO ET5 EEA from 2023",
    "nio-et5-touring-2021": "no EEA EU NIO ET5 Touring in 2021 (NIO Touring from 2023)",
    "nio-et5-touring-2022": "no EEA EU NIO ET5 Touring in 2022 (NIO Touring from 2023)",
    "nio-el6-2021": "EEA EU NIO EL6 from 2023; no 2021",
    "nio-el6-2022": "EEA EU NIO EL6 from 2023; no 2022",
    "xpeng-g6-2021": "EEA EU XPeng G6 from 2024; no 2021",
    "xpeng-g6-2022": "EEA EU XPeng G6 from 2024; no 2022",
    "xpeng-g9-2021": "EEA EU XPeng G9 from 2023; no 2021",
    "chevrolet-bolt-euv-2021": "no EEA EU Chevrolet BEV registrations for Bolt EUV",
    "jaguar-i-pace-2026": "EEA EU IPACE through 2025 only; no 2026",
    "lexus-rz-2022": "Lexus EU Apr 2022 = reservations only; first deliveries end-2022/2023; EEA RZ from 2023 (same bar as Mini 2019)",
    "honda-e-2019": "Honda EU: first deliveries summer 2020 (not 2019 sales year)",
    "mini-electric-hatch-2019": "BMW/MINI press: orders 2019, first deliveries March 2020 — no 2019 delivery year",
    "kia-soul-ev-2026": "EEA EU SOUL EV through 2025 only; no 2026",
    "volvo-c40-recharge-2026": "no EEA EU C40 2026; rename to EC40 (volvo-ec40-2026 present)",
    "volvo-xc40-recharge-2026": "no EEA EU XC40 EV 2026; rename to EX40 (volvo-ex40-2026 present)",
    "renault-scenic-2024": (
        "parallel id vs renault-scenic-e-tech-2024 with conflicting specs "
        "(powerKw 148.9 vs 153.3, dims, consumption, confidence 0.55 vs 0.95); "
        "keep scenic-e-tech as canonical"
    ),
}


def main_seed_rows() -> list[dict]:
    raw = subprocess.check_output(
        ["git", "show", "main:EVforME?/Data/vehicles.seed.quality.json"],
        cwd=str(eea.REPO),
    )
    return json.loads(raw)


def bump_seed(rows: list[dict]) -> None:
    raw = eea.SEED_PATH.read_bytes()
    cdn = json.loads(eea.CDN_PATH.read_text(encoding="utf-8"))
    cdn["seedVersion"] = NEW_SEED_VERSION
    cdn["rows"] = len(rows)
    cdn["bytes"] = len(raw)
    cdn["updatedAt"] = datetime.now(timezone.utc).isoformat()
    cdn["note"] = (
        f"seedVersion {NEW_SEED_VERSION}: remove nonexistent EU EVs (EEA all-MS); "
        "restore Soul 2024/25, NIO EL8 2022, Volvo C40/XC40 Recharge 2025; drop Lexus RZ 2022"
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


def strip_refs(removed: set[str]) -> None:
    for path in (
        eea.CACHE_DIR / "catalog_truth_battery_refs.json",
        eea.REPO / "EVforME?Tests" / "Fixtures" / "catalog_truth_battery_refs.json",
    ):
        if not path.is_file():
            continue
        refs = json.loads(path.read_text(encoding="utf-8"))
        refs["nilled"] = [n for n in (refs.get("nilled") or []) if n.get("id") not in removed]
        refs["corrected"] = [
            c for c in (refs.get("corrected") or []) if c.get("id") not in removed
        ]
        if "dubious_models_no_delete" in refs:
            refs["dubious_models_no_delete"] = [
                i for i in refs["dubious_models_no_delete"] if i not in removed
            ]
        refs["seedVersion"] = NEW_SEED_VERSION
        path.write_text(json.dumps(refs, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    for path in (
        eea.CACHE_DIR / "catalog_truth_range_refs.json",
        eea.REPO / "EVforME?Tests" / "Fixtures" / "catalog_truth_range_refs.json",
    ):
        if not path.is_file():
            continue
        refs = json.loads(path.read_text(encoding="utf-8"))
        refs["fills"] = [f for f in (refs.get("fills") or []) if f.get("id") not in removed]
        refs["skips"] = [s for s in (refs.get("skips") or []) if s.get("id") not in removed]
        refs["seedVersion"] = NEW_SEED_VERSION
        path.write_text(json.dumps(refs, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    for path in (
        eea.CACHE_DIR / "catalog_truth_eea_refs.json",
        eea.REPO / "EVforME?Tests" / "Fixtures" / "catalog_truth_eea_refs.json",
    ):
        if not path.is_file():
            continue
        refs = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(refs, list):
            refs = [r for r in refs if (r.get("id") if isinstance(r, dict) else r) not in removed]
            path.write_text(json.dumps(refs, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    # Start from main tip catalog, then apply remove/keep policy.
    main_rows = main_seed_rows()
    before = len(main_rows)
    by_main = {r["id"]: r for r in main_rows}

    removed: list[dict] = []
    kept: list[dict] = []
    remove_ids = set(REMOVE)

    for rid, reason in sorted(REMOVE.items()):
        if rid not in by_main:
            continue
        r = by_main[rid]
        removed.append(
            {
                "id": rid,
                "reason": reason,
                "snapshot": {
                    "brand": r.get("brand"),
                    "model": r.get("model"),
                    "year": r.get("year"),
                    "powertrain": r.get("powertrain"),
                    "powerKw": r.get("powerKw"),
                },
            }
        )

    for rid, meta in sorted(KEEP.items()):
        if rid not in by_main:
            raise SystemExit(f"KEEP id missing on main: {rid}")
        if rid in remove_ids:
            raise SystemExit(f"KEEP id also in REMOVE: {rid}")
        kept.append({"id": rid, **meta})

    new_rows = [r for r in main_rows if r["id"] not in remove_ids]
    after = len(new_rows)

    eea.SEED_PATH.write_text(
        json.dumps(new_rows, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    bump_seed(new_rows)
    strip_refs(remove_ids)

    report = {
        "seedVersion": NEW_SEED_VERSION,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "consulted_date": CONSULTED,
        "eea_scope": "all MS (EU-wide Electric Zr), not IT-only",
        "counts": {
            "rows_before": before,
            "rows_after": after,
            "removed": len(removed),
            "kept_from_candidates": len(kept),
        },
        "kept": kept,
        "removed": removed,
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
