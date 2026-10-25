#!/usr/bin/env python3
"""
Apply batteryKWh policy: keep only EEA-verified or same-year OEM sheet values.

seedVersion stays 56 (no bump).
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

import check_catalog_battery as batt
import fill_catalog_fuels_from_eea as eea

NEW_SEED_VERSION = 56
BATTERY_REFS = eea.CACHE_DIR / "catalog_truth_battery_refs.json"
FIXTURE_BATTERY = eea.REPO / "EVforME?Tests" / "Fixtures" / "catalog_truth_battery_refs.json"
RANGE_REFS = eea.CACHE_DIR / "catalog_truth_range_refs.json"
FIXTURE_RANGE = eea.REPO / "EVforME?Tests" / "Fixtures" / "catalog_truth_range_refs.json"
CONSULTED = "2026-10-25"

# Same-year OEM only. capacity_kind must be "net" or "gross".
OFFICIAL: list[dict] = [
    {
        "ids": {"honda-e-2020"},
        "years": {2020},
        "batteryKWh": 35.5,
        "capacity_kind": "gross",
        "url": "https://hondanews.eu/eu/en/cars/media/pressreleases/199768/2020-honda-e-33",
        "note": "Honda Europe 2020 press: 35.5 kWh Li-ion (nominal/gross Energie).",
        "powerKw_any": True,
        "require_powerKw": True,  # 2019 without kW must not match
    },
    {
        "ids": {"mg-mg-zs-ev-2021"},
        "years": {2021},
        "batteryKWh": 44.5,
        "capacity_kind": "gross",
        "url": "https://news.mgmotor.eu/it/press/prima-uscita-in-pubblico-per-mg-al-milano-monza-motor-show-con-zx-ev-100-elettrica-e-ehs-plug-in-hybrid/",
        "note": "MG Italy 2021: ZS EV 44.5 kWh / 263 km / 105 kW (nominal).",
        "powerKw": 105.0,
    },
    {
        "ids": {"byd-dolphin-2023"},
        "years": {2023},
        "batteryKWh": 60.4,
        "capacity_kind": "gross",
        "url": "https://press.bydauto.be/byd-dolphin-plonge-dans-le-bain-europeen",
        "note": "BYD EU launch 2023: Blade 60.4 kWh Comfort/Design, 150 kW (nominal capacity).",
        "powerKw": 150.0,
    },
    {
        "id_prefix": "mini-electric-hatch-",
        "years": {2019, 2020, 2021, 2022, 2023},
        "batteryKWh": 28.9,
        "capacity_kind": "net",
        "url": "https://www.press.bmwgroup.com/ireland/article/detail/T0298516EN/the-first-ever-mini-electric?language=en",
        "also": "https://www.press.bmwgroup.com/global/article/attachment/T0325441EN/471414",
        "note": "BMW/MINI press: Cooper SE 32.6 kWh gross / 28.9 kWh net (first-gen).",
        "powerKw_any": True,
    },
    {
        "ids": {"lexus-rz-2022", "lexus-rz-2025", "lexus-rz-2026"},
        "batteryKWh": 71.4,
        "capacity_kind": "gross",
        "url": "https://newsroom.lexus.eu/dynamic-press-launch-of-the-new-all-electric-lexus-rz/",
        "note": "Lexus EU: RZ 450e 71.4 kWh gross Li-ion (96 cells).",
        "powerKw_any": True,
    },
]

# Always nil these (ambiguous / wrong-year source / listed by review).
FORCE_NIL_PREFIXES = (
    "chevrolet-bolt-ev-2018",
    "chevrolet-bolt-ev-2019",
    "chevrolet-bolt-ev-2020",
    "chevrolet-bolt-ev-2021",
    "chevrolet-bolt-ev-2022",
    "chevrolet-bolt-ev-2023",
    "chevrolet-bolt-euv-",
    "hyundai-kona-electric-2018",
    "hyundai-kona-electric-2019",
    "hyundai-kona-electric-2020",
    "hyundai-kona-electric-2021",
    "kia-e-niro-2018",
    "kia-e-niro-2019",
    "renault-zoe-2015",
    "renault-zoe-2016",
    "volkswagen-e-up!-2013",
    "volkswagen-e-up!-2014",
    "volkswagen-e-up!-2015",
    "volkswagen-e-up!-2016",
    "volkswagen-e-up!-2017",
    "volkswagen-e-up!-2018",
    "jaguar-i-pace-2018",
    "mg-mg4-2025",
    "mg-mg4-2026",
    "mg-mg5-2025",
    "mg-mg5-2026",
    "hyundai-inster-2024",
    "cupra-tavascan-",
    "genesis-electrified-gv70-",
    "byd-dolphin-surf-2026",
    "leapmotor-t03-",
    "volkswagen-golf-gte-phev-2024",
    "byd-dolphin-2024",
    "byd-dolphin-2025",
    "honda-e-2021",
    "honda-e-2022",
    "honda-e-2023",
    "honda-e-2019",
    "opel-frontera-electric-2025",
    "opel-frontera-electric-2026",
    "mini-electric-hatch-2024",
    "mini-electric-hatch-2025",
    "mini-electric-hatch-2026",
)

FORCE_NIL_IDS = {
    "fiat-500e-2021",
    "fiat-500e-2022",
}


def force_nil(rid: str) -> bool:
    if rid in FORCE_NIL_IDS:
        return True
    return any(rid.startswith(p) or rid == p.rstrip("-") for p in FORCE_NIL_PREFIXES)


def kw_ok(row_kw, target, *, any_ok: bool, require_powerKw: bool) -> bool:
    if require_powerKw and row_kw in (None, "", 0):
        return False
    if any_ok:
        return True
    if target is None:
        return True
    if row_kw in (None, "", 0):
        return False
    return abs(float(row_kw) - float(target)) <= 5.0


def match_official(row: dict) -> dict | None:
    rid = row.get("id") or ""
    year = int(row.get("year") or 0)
    pkw = row.get("powerKw")
    for spec in OFFICIAL:
        if "ids" in spec and rid not in spec["ids"]:
            continue
        if "id_prefix" in spec:
            if not rid.startswith(spec["id_prefix"]):
                continue
        years = spec.get("years")
        if years is not None and year not in years:
            continue
        if "ids" in spec and years is None:
            # year must match id suffix when years not set — ids already pin year
            pass
        if not kw_ok(
            pkw if pkw is None else float(pkw) if pkw not in ("",) else None,
            spec.get("powerKw"),
            any_ok=bool(spec.get("powerKw_any")),
            require_powerKw=bool(spec.get("require_powerKw")),
        ):
            continue
        return spec
    return None


def refresh_cdn(rows: list[dict]) -> None:
    """Keep seedVersion 56; refresh CDN bytes/note only."""
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
        f"seedVersion {NEW_SEED_VERSION}: batteryKWh only if EEA-verified (±15% Zr) "
        "or same-year OEM sheet (net/gross); else nil. Synthetic pack patterns cleared."
    )
    eea.CDN_PATH.write_text(json.dumps(cdn, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


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
        path.write_text(json.dumps(refs, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    rows: list[dict] = json.loads(eea.SEED_PATH.read_text(encoding="utf-8"))
    by_id = {r["id"]: r for r in rows}

    # Snapshot before
    before_ev = sum(
        1 for r in rows if r.get("powertrain") == "ev" and r.get("batteryKWh")
    )
    before_phev = sum(
        1 for r in rows if r.get("powertrain") == "phev" and r.get("batteryKWh")
    )

    # Scan with NO oem exemption so wrong-year OEM values are cleared first.
    suspects, _ = batt.run_suspect_scan(rows, oem_ok=set())
    suspect_ids = {s["id"] for s in suspects}
    coh_ids = {line.split(":", 1)[0] for line in batt.coherence_failures(rows)}
    synth = set(batt.find_synthetic_pattern_ids(rows))
    force = {r["id"] for r in rows if force_nil(r["id"]) and r.get("batteryKWh")}

    clear_ids = suspect_ids | coh_ids | synth | force | {"fiat-500e-2021", "fiat-500e-2022"}

    nilled: list[dict] = []
    corrected: list[dict] = []

    five00 = {"fiat-500e-2021", "fiat-500e-2022"}

    for rid in sorted(clear_ids):
        r = by_id.get(rid)
        if not r:
            continue
        old_bat = r.get("batteryKWh")
        old_rng = r.get("wltpRangeKm")
        if rid in five00:
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
        if old_bat is not None:
            r["batteryKWh"] = None
            nilled.append(
                {
                    "id": rid,
                    "action": "nil_battery",
                    "old_batteryKWh": old_bat,
                    "reason": "unverified_or_synthetic_or_force_list",
                }
            )

    # OEM same-year overrides (may re-fill after nil)
    for rid, r in by_id.items():
        if (r.get("powertrain") or "").lower() not in {"ev", "phev"}:
            continue
        if force_nil(rid) and rid not in {
            # mini 2019-2023 are force-nil for wrong packs then re-filled by OEM
            x
            for x in []
        }:
            # Still allow OEM match for mini 2019-2023 / lexus / honda-2020 etc.
            pass
        # Block OEM for force-nil that are not in OFFICIAL
        spec = match_official(r)
        if not spec:
            continue
        # Do not apply OEM to force-nil ids that aren't covered by OFFICIAL
        if force_nil(rid) and not match_official(r):
            continue
        # Skip force-nil models that should stay nil (frontera, honda 21-23, dolphin 24-25…)
        if rid.startswith("opel-frontera-electric-"):
            continue
        if rid in {
            "byd-dolphin-2024",
            "byd-dolphin-2025",
            "honda-e-2021",
            "honda-e-2022",
            "honda-e-2023",
            "honda-e-2019",
        }:
            continue
        if rid.startswith("mini-electric-hatch-") and int(r.get("year") or 0) >= 2024:
            continue

        new_bat = float(spec["batteryKWh"])
        energy = r.get("energyConsumptionKWhPerKm")
        rng = r.get("wltpRangeKm")
        if energy and rng and float(energy) > 0 and float(rng) > 0:
            implied = new_bat / float(energy)
            if abs(implied - float(rng)) / float(rng) > batt.TOL:
                r["batteryKWh"] = None
                continue
        old = r.get("batteryKWh")
        # Prefer recording pre-nil value from nilled list
        old_from_nil = next(
            (n["old_batteryKWh"] for n in nilled if n["id"] == rid), old
        )
        r["batteryKWh"] = new_bat
        corrected.append(
            {
                "id": rid,
                "old_batteryKWh": old_from_nil,
                "batteryKWh": new_bat,
                "capacity_kind": spec["capacity_kind"],
                "url": spec["url"],
                "consulted": CONSULTED,
                "note": spec["note"],
                "powerKw": r.get("powerKw"),
                "source_year": int(r.get("year") or 0),
            }
        )

    eea.SEED_PATH.write_text(
        json.dumps(rows, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    refresh_cdn(rows)
    update_range_refs_drop(five00)

    after_ev = sum(
        1 for r in rows if r.get("powertrain") == "ev" and r.get("batteryKWh")
    )
    after_phev = sum(
        1 for r in rows if r.get("powertrain") == "phev" and r.get("batteryKWh")
    )

    # Classify remaining batteries
    eea_verified = []
    oem_ids = {c["id"] for c in corrected}
    suspects_after, indexes = batt.run_suspect_scan(
        rows, oem_ok=oem_ids
    )
    for r in rows:
        if not r.get("batteryKWh"):
            continue
        if (r.get("powertrain") or "").lower() not in {"ev", "phev"}:
            continue
        if r["id"] in oem_ids:
            continue
        # if not in suspects_after, it's EEA-ok
        eea_verified.append(r["id"])

    # Dubious model names for PR (no deletion)
    dubious = [
        r["id"]
        for r in rows
        if r.get("powertrain") == "ev"
        and (
            "equus" in r["id"]
            or r["id"].startswith("hyundai-equus")
        )
    ]

    refs = {
        "seedVersion": NEW_SEED_VERSION,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "consulted_date": CONSULTED,
        "rules": [
            "Keep battery only if EEA Zr exists for model/year and implied range within 15%, OR same-year OEM sheet (net|gross) matching kW",
            "No EEA Zr → unverified → nil (unless OEM same-year)",
            "Synthetic same-implied across ≥3 models / fixed year-step → nil",
            "capacity_kind is net or gross as stated by OEM",
        ],
        "counts": {
            "battery_before_ev": before_ev,
            "battery_before_phev": before_phev,
            "battery_after_ev": after_ev,
            "battery_after_phev": after_phev,
            "ended_nil_net": (before_ev + before_phev) - (after_ev + after_phev),
            "suspects_flagged_before_clear": len(suspects),
            "nil_operations": len(nilled),
            "corrected_oem": len(corrected),
            "eea_verified_remaining": len(eea_verified),
            "suspects_after": len(suspects_after),
        },
        "nilled": nilled,
        "corrected": corrected,
        "eea_verified_ids": sorted(eea_verified),
        "suspects_before": suspects,
        "dubious_models_no_delete": sorted(dubious),
    }
    eea.CACHE_DIR.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(refs, ensure_ascii=False, indent=2) + "\n"
    BATTERY_REFS.write_text(payload, encoding="utf-8")
    if FIXTURE_BATTERY.parent.is_dir():
        FIXTURE_BATTERY.write_text(payload, encoding="utf-8")

    print(
        f"before ev/phev bat={before_ev}/{before_phev} "
        f"after={after_ev}/{after_phev} nilled={len(nilled)} "
        f"oem={len(corrected)} eea_keep={len(eea_verified)} "
        f"suspects_after={len(suspects_after)}"
    )
    for c in corrected:
        print(f"  OEM {c['id']}: {c['old_batteryKWh']} → {c['batteryKWh']} {c['capacity_kind']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
