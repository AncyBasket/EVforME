#!/usr/bin/env python3
"""
Apply batteryKWh policy: keep ONLY official OEM URL refs (same source year + kW).

EEA ±15% alone is never enough. seedVersion stays 56 (no bump).
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

import check_catalog_battery as batt
import fill_catalog_fuels_from_eea as eea

NEW_SEED_VERSION = 56
BATTERY_REFS = eea.CACHE_DIR / "catalog_truth_battery_refs.json"
FIXTURE_BATTERY = eea.REPO / "EVforME?Tests" / "Fixtures" / "catalog_truth_battery_refs.json"
RANGE_REFS = eea.CACHE_DIR / "catalog_truth_range_refs.json"
FIXTURE_RANGE = eea.REPO / "EVforME?Tests" / "Fixtures" / "catalog_truth_range_refs.json"
CONSULTED = "2026-10-25"

# Official OEM only. source_year = year of the press/sheet (must equal row year).
# powerKw must match the catalog row (±5). No powerKw_any / cross-year reuse.
OFFICIAL: list[dict] = [
    {
        "ids": {"honda-e-2020"},
        "batteryKWh": 35.5,
        "capacity_kind": "gross",
        "url": "https://hondanews.eu/eu/en/cars/media/pressreleases/199768/2020-honda-e-33",
        "note": "Honda Europe 2020 press: 35.5 kWh Li-ion (nominal/gross).",
        "source_year": 2020,
        "powerKw": 96.5,  # catalog row powerKw
    },
    {
        "ids": {"mg-mg-zs-ev-2021"},
        "batteryKWh": 44.5,
        "capacity_kind": "gross",
        "url": "https://news.mgmotor.eu/it/press/prima-uscita-in-pubblico-per-mg-al-milano-monza-motor-show-con-zx-ev-100-elettrica-e-ehs-plug-in-hybrid/",
        "note": "MG Italy 2021: ZS EV 44.5 kWh nominal / 263 km / 105 kW.",
        "source_year": 2021,
        "powerKw": 105.0,
    },
    {
        "ids": {"byd-dolphin-2023"},
        "batteryKWh": 60.4,
        "capacity_kind": "gross",
        "url": "https://press.bydauto.be/byd-dolphin-plonge-dans-le-bain-europeen",
        "note": "BYD EU launch 2023: Blade 60.4 kWh Comfort/Design (nominal), 150 kW.",
        "source_year": 2023,
        "powerKw": 150.0,
    },
]

FIVE00 = {"fiat-500e-2021", "fiat-500e-2022"}

DUBIOUS_IDS = {
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
    "renault-scenic-2024",  # duplicate of renault-scenic-e-tech-2024
}


def is_dubious(rid: str) -> bool:
    return rid in DUBIOUS_IDS


def match_official(row: dict) -> dict | None:
    rid = row.get("id") or ""
    year = int(row.get("year") or 0)
    pkw = row.get("powerKw")
    if pkw in (None, "", 0):
        return None
    for spec in OFFICIAL:
        if rid not in spec["ids"]:
            continue
        if int(spec["source_year"]) != year:
            continue
        if abs(float(pkw) - float(spec["powerKw"])) > batt.KW_TOL:
            continue
        return spec
    return None


def main_baseline_counts() -> tuple[int, int]:
    """Battery counts on main (PR baseline), not previous branch tip."""
    try:
        raw = subprocess.check_output(
            ["git", "show", "main:EVforME?/Data/vehicles.seed.quality.json"],
            cwd=str(eea.REPO),
        )
    except subprocess.CalledProcessError:
        raw = subprocess.check_output(
            ["git", "show", "origin/main:EVforME?/Data/vehicles.seed.quality.json"],
            cwd=str(eea.REPO),
        )
    rows = json.loads(raw)
    ev = sum(1 for r in rows if r.get("powertrain") == "ev" and r.get("batteryKWh"))
    phev = sum(1 for r in rows if r.get("powertrain") == "phev" and r.get("batteryKWh"))
    return ev, phev


def refresh_cdn(rows: list[dict]) -> None:
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
    raw = eea.SEED_PATH.read_bytes()
    cdn = json.loads(eea.CDN_PATH.read_text(encoding="utf-8"))
    cdn["seedVersion"] = NEW_SEED_VERSION
    cdn["rows"] = len(rows)
    cdn["bytes"] = len(raw)
    cdn["updatedAt"] = datetime.now(timezone.utc).isoformat()
    cdn["note"] = (
        f"seedVersion {NEW_SEED_VERSION}: batteryKWh only with official OEM URL "
        "(same source_year + matching kW; net|gross); else nil."
    )
    eea.CDN_PATH.write_text(
        json.dumps(cdn, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def update_range_refs_drop(ids: set[str]) -> None:
    for path in (RANGE_REFS, FIXTURE_RANGE):
        if not path.is_file():
            continue
        refs = json.loads(path.read_text(encoding="utf-8"))
        fills = [f for f in (refs.get("fills") or []) if f.get("id") not in ids]
        removed = [f for f in (refs.get("fills") or []) if f.get("id") in ids]
        skips = list(refs.get("skips") or [])
        for f in removed:
            skips.append(
                {
                    "id": f["id"],
                    "result": "skip",
                    "reason": "cleared with battery: Fiat 500e 2021/22 ambiguous packs",
                    "previous_wltpRangeKm": f.get("wltpRangeKm"),
                    "clearedAt": datetime.now(timezone.utc).isoformat(),
                }
            )
        refs["fills"] = fills
        refs["skips"] = skips
        path.write_text(
            json.dumps(refs, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )


def main() -> int:
    rows: list[dict] = json.loads(eea.SEED_PATH.read_text(encoding="utf-8"))
    by_id = {r["id"]: r for r in rows}

    before_ev_main, before_phev_main = main_baseline_counts()
    before_ev_tip = sum(
        1 for r in rows if r.get("powertrain") == "ev" and r.get("batteryKWh")
    )
    before_phev_tip = sum(
        1 for r in rows if r.get("powertrain") == "phev" and r.get("batteryKWh")
    )

    nilled: list[dict] = []
    corrected: list[dict] = []

    # 1) Nil every battery that is not a matching OFFICIAL OEM row.
    keep_ids: set[str] = set()
    for r in rows:
        if (r.get("powertrain") or "").lower() not in {"ev", "phev"}:
            continue
        spec = match_official(r)
        if spec:
            keep_ids.add(r["id"])

    for r in rows:
        if (r.get("powertrain") or "").lower() not in {"ev", "phev"}:
            continue
        rid = r["id"]
        old_bat = r.get("batteryKWh")
        old_rng = r.get("wltpRangeKm")

        if rid in FIVE00:
            if old_bat is not None or old_rng is not None:
                r["batteryKWh"] = None
                r["wltpRangeKm"] = None
                nilled.append(
                    {
                        "id": rid,
                        "action": "nil_battery_and_range",
                        "old_batteryKWh": old_bat,
                        "old_wltpRangeKm": old_rng,
                        "reason": "ambiguous 23.8 kWh/190 km vs ~42 kWh pack",
                    }
                )
            continue

        if rid in keep_ids:
            continue
        if old_bat is None:
            continue
        r["batteryKWh"] = None
        nilled.append(
            {
                "id": rid,
                "action": "nil_battery",
                "old_batteryKWh": old_bat,
                "reason": "no_official_oem_url_same_year_kw",
            }
        )

    # 2) Apply / confirm OEM values for keep_ids
    for rid in sorted(keep_ids):
        r = by_id[rid]
        spec = match_official(r)
        assert spec is not None
        new_bat = float(spec["batteryKWh"])
        old = r.get("batteryKWh")
        old_from_nil = next(
            (n["old_batteryKWh"] for n in nilled if n["id"] == rid), old
        )
        r["batteryKWh"] = new_bat
        corrected.append(
            {
                "id": rid,
                "old_batteryKWh": old_from_nil if old_from_nil is not None else old,
                "batteryKWh": new_bat,
                "capacity_kind": spec["capacity_kind"],
                "url": spec["url"],
                "consulted": CONSULTED,
                "note": spec["note"],
                "powerKw": float(spec["powerKw"]),
                "source_year": int(spec["source_year"]),
            }
        )

    eea.SEED_PATH.write_text(
        json.dumps(rows, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    refresh_cdn(rows)
    update_range_refs_drop(FIVE00)

    after_ev = sum(
        1 for r in rows if r.get("powertrain") == "ev" and r.get("batteryKWh")
    )
    after_phev = sum(
        1 for r in rows if r.get("powertrain") == "phev" and r.get("batteryKWh")
    )

    oem_ids = {c["id"] for c in corrected}
    suspects_after, _ = batt.run_suspect_scan(rows, oem_ok=oem_ids)

    # Synthetic report on tip-before state for audit (optional)
    synth = batt.find_synthetic_pattern_ids(
        json.loads(
            # re-scan current after — should not flag kept OEM (no energy patterns among 3)
            eea.SEED_PATH.read_text(encoding="utf-8")
        )
    )

    dubious = sorted({r["id"] for r in rows if is_dubious(r["id"])})

    refs = {
        "seedVersion": NEW_SEED_VERSION,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "consulted_date": CONSULTED,
        "rules": [
            "Keep batteryKWh ONLY with official OEM URL in refs: source_year == row year, matching powerKw (±5), capacity_kind net|gross",
            "No kW on row → nil; EEA ±15% alone is not enough; no IT-listino without URL",
            "Synthetic: same implied km (±1) across ≥3 models/year, or constant implied-km step (incl. 0) across consecutive years → nil",
        ],
        "counts": {
            "battery_before_ev_vs_main": before_ev_main,
            "battery_before_phev_vs_main": before_phev_main,
            "battery_before_ev_tip": before_ev_tip,
            "battery_before_phev_tip": before_phev_tip,
            "battery_after_ev": after_ev,
            "battery_after_phev": after_phev,
            "ended_nil_net_vs_main": (before_ev_main + before_phev_main)
            - (after_ev + after_phev),
            "nil_operations_this_run": len(nilled),
            "corrected_oem": len(corrected),
            "suspects_after": len(suspects_after),
        },
        "nilled": nilled,
        "corrected": corrected,
        "synthetic_ids_after": sorted(synth),
        "suspects_after": suspects_after,
        "dubious_models_no_delete": dubious,
    }
    eea.CACHE_DIR.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(refs, ensure_ascii=False, indent=2) + "\n"
    BATTERY_REFS.write_text(payload, encoding="utf-8")
    if FIXTURE_BATTERY.parent.is_dir():
        FIXTURE_BATTERY.write_text(payload, encoding="utf-8")

    print(
        f"vs_main before ev/phev={before_ev_main}/{before_phev_main} "
        f"tip_before={before_ev_tip}/{before_phev_tip} "
        f"after={after_ev}/{after_phev} nilled={len(nilled)} "
        f"oem={len(corrected)} suspects_after={len(suspects_after)}"
    )
    for c in corrected:
        print(
            f"  OEM {c['id']}: {c['old_batteryKWh']} → {c['batteryKWh']} "
            f"{c['capacity_kind']} source_year={c['source_year']} kW={c['powerKw']}"
        )
    if suspects_after:
        print("SUSPECTS REMAINING:", [s["id"] for s in suspects_after[:20]])
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
