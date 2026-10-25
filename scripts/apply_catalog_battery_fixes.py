#!/usr/bin/env python3
"""
Apply batteryKWh corrections after check_catalog_battery.py inventory.

- Nil every suspect (and every battery↔range coherence failure) unless an
  official manufacturer override matches the row's model/year/kW.
- Fiat 500e 2021/2022: nil battery AND wltpRangeKm; drop from range refs.
- seedVersion → 56 + CDN bytes.

No invented numbers: overrides are hard-coded from manufacturer URLs only.
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

# Official manufacturer capacities (prefer published usable/net when stated;
# otherwise the single kWh figure the OEM publishes on the tech sheet).
# Match powerKw ±5 when multiple packs exist for the model.
OFFICIAL: list[dict] = [
    {
        "id_prefix": "honda-e-",
        "years": {2019, 2020, 2021, 2022, 2023},
        "batteryKWh": 35.5,
        "capacity_kind": "as_published_by_oem",  # Honda sheet “Energie 35,5 kWh”; no separate usable
        "url": "https://hondanews.eu/eu/en/cars/media/pressreleases/199768/2020-honda-e-33",
        "also": "https://de.honda.de/inhalt/automobile/preislisten/documents/Honda-e/Honda_e_Preise_Daten_Ausstattung_2022-01",
        "note": "Honda Europe: 35.5 kWh Li-ion for Honda e / e Advance (100 or 113 kW).",
        "powerKw_any": True,
    },
    {
        "ids": {"mg-mg-zs-ev-2021"},
        "batteryKWh": 44.5,
        "capacity_kind": "as_published_by_oem",
        "url": "https://news.mgmotor.eu/it/press/prima-uscita-in-pubblico-per-mg-al-milano-monza-motor-show-con-zx-ev-100-elettrica-e-ehs-plug-in-hybrid/",
        "note": "MG Italy press: ZS EV 44.5 kWh / 263 km WLTP / 105 kW — matches catalog range+kW (pre-facelift pack).",
        "powerKw": 105.0,
    },
    {
        "ids": {"byd-dolphin-2024", "byd-dolphin-2025"},
        "batteryKWh": 60.4,
        "capacity_kind": "as_published_by_oem",  # BYD EU “Battery capacity 60.4 kWh” Comfort/Design
        "url": "https://press.bydauto.be/byd-dolphin-plonge-dans-le-bain-europeen",
        "also": "https://katalog.bydauto.dk/NicChristiansenGruppen/byd/specifikationer/byd-dolphin/?Page=5",
        "note": "BYD EU: Blade 60.4 kWh, 150 kW, 427 km WLTP (Comfort/Design). Not 44.9 kWh Active/Boost.",
        "powerKw": 150.0,
    },
    {
        "ids": {"byd-dolphin-2023"},
        "batteryKWh": 60.4,
        "capacity_kind": "as_published_by_oem",
        "url": "https://press.bydauto.be/byd-dolphin-plonge-dans-le-bain-europeen",
        "note": "Same Comfort/Design 60.4 kWh / 150 kW pack as EU launch.",
        "powerKw": 150.0,
    },
]


def kw_ok(row_kw: float | None, target: float | None, *, any_ok: bool) -> bool:
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
            if year not in spec.get("years", set()):
                continue
        if not kw_ok(pkw if pkw is None else float(pkw), spec.get("powerKw"), any_ok=bool(spec.get("powerKw_any"))):
            continue
        return spec
    return None


def bump_seed_version(rows: list[dict]) -> None:
    text = eea.CATALOG_SERVICE.read_text(encoding="utf-8")
    text2, n = re.subn(
        r"static let bundledSeedVersion = \d+",
        f"static let bundledSeedVersion = {NEW_SEED_VERSION}",
        text,
        count=1,
    )
    if n != 1:
        raise RuntimeError("Could not bump bundledSeedVersion")
    eea.CATALOG_SERVICE.write_text(text2, encoding="utf-8")
    raw = eea.SEED_PATH.read_bytes()
    cdn = json.loads(eea.CDN_PATH.read_text(encoding="utf-8"))
    cdn["seedVersion"] = NEW_SEED_VERSION
    cdn["rows"] = len(rows)
    cdn["bytes"] = len(raw)
    cdn["updatedAt"] = datetime.now(timezone.utc).isoformat()
    cdn["note"] = (
        f"seedVersion {NEW_SEED_VERSION}: batteryKWh — nil EEA-inconsistent packs; "
        "OEM sheet overrides only (Honda e 35.5, MG ZS EV 2021 44.5, BYD Dolphin 60.4); "
        "Fiat 500e 2021–22 range+battery nil (ambiguous 24 vs 42 kWh)."
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
                    "reason": (
                        "cleared with batteryKWh: Fiat 500e 2021/2022 ambiguous "
                        "24 kWh (~190 km) vs ~42 kWh pack — both range and battery set nil"
                    ),
                    "previous_wltpRangeKm": f.get("wltpRangeKm"),
                    "clearedAt": datetime.now(timezone.utc).isoformat(),
                }
            )
        refs["fills"] = fills
        refs["skips"] = skips
        refs["seedVersion"] = NEW_SEED_VERSION
        refs["battery_coherence_note"] = (
            "500e 2021/2022 fills removed — see catalog_truth_battery_refs.json"
        )
        path.write_text(json.dumps(refs, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    rows: list[dict] = json.loads(eea.SEED_PATH.read_text(encoding="utf-8"))
    suspects, _ = batt.run_suspect_scan(rows)
    suspect_ids = {s["id"] for s in suspects}
    coh_ids = set()
    for line in batt.coherence_failures(rows):
        coh_ids.add(line.split(":", 1)[0])

    clear_ids = suspect_ids | coh_ids
    # Always include 500e 2021/22
    five00 = {"fiat-500e-2021", "fiat-500e-2022"}
    clear_ids |= five00

    nilled: list[dict] = []
    corrected: list[dict] = []
    skipped_official: list[str] = []

    by_id = {r["id"]: r for r in rows}

    # First nil everyone in clear_ids
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
                    "reason": "suspect_or_coherence",
                }
            )

    # Then apply official overrides (may re-set battery on cleared rows)
    for rid, r in by_id.items():
        if (r.get("powertrain") or "").lower() not in {"ev", "phev"}:
            continue
        spec = match_official(r)
        if not spec:
            continue
        # Only apply if we cleared it or it was already wrong/missing among targets
        if rid not in clear_ids and r.get("batteryKWh") not in (None,):
            # still allow override if current value differs from official
            if abs(float(r["batteryKWh"]) - float(spec["batteryKWh"])) < 0.05:
                continue
        new_bat = float(spec["batteryKWh"])
        # Coherence gate: if range present, implied must be within 15%
        energy = r.get("energyConsumptionKWhPerKm")
        rng = r.get("wltpRangeKm")
        if energy and rng and float(energy) > 0 and float(rng) > 0:
            implied = new_bat / float(energy)
            if abs(implied - float(rng)) / float(rng) > batt.TOL:
                skipped_official.append(
                    f"{rid}: official {new_bat} kWh implies {implied:.0f} km vs range {rng}"
                )
                r["batteryKWh"] = None
                continue
        old = r.get("batteryKWh")
        r["batteryKWh"] = new_bat
        corrected.append(
            {
                "id": rid,
                "old_batteryKWh": old,
                "batteryKWh": new_bat,
                "capacity_kind": spec["capacity_kind"],
                "url": spec["url"],
                "consulted": CONSULTED,
                "note": spec["note"],
                "powerKw": r.get("powerKw"),
            }
        )

    eea.SEED_PATH.write_text(
        json.dumps(rows, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    bump_seed_version(rows)
    update_range_refs_drop(five00)

    refs = {
        "seedVersion": NEW_SEED_VERSION,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "consulted_date": CONSULTED,
        "rules": [
            "Nil battery when implied range >15% from all EEA Zr or exceeds max implied pack",
            "Nil battery when battery↔wltpRangeKm drift >15%",
            "OEM sheet overrides only when kW uniquely matches; prefer published usable/net when stated",
            "Fiat 500e 2021/2022: nil battery and wltpRangeKm (ambiguous packs)",
        ],
        "suspect_count_before": len(suspects),
        "coherence_count_before": len(coh_ids),
        "nilled": nilled,
        "corrected": corrected,
        "skipped_official_incoherent_with_range": skipped_official,
        "suspects_before": suspects,
    }
    eea.CACHE_DIR.mkdir(parents=True, exist_ok=True)
    BATTERY_REFS.write_text(json.dumps(refs, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if FIXTURE_BATTERY.parent.is_dir():
        FIXTURE_BATTERY.write_text(
            json.dumps(refs, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    print(
        f"nilled={len(nilled)} corrected={len(corrected)} "
        f"skipped_official={len(skipped_official)} seedVersion={NEW_SEED_VERSION}"
    )
    for c in corrected:
        print(f"  FIX {c['id']}: {c['old_batteryKWh']} → {c['batteryKWh']} ({c['url']})")
    for s in skipped_official:
        print(f"  SKIP {s}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
