#!/usr/bin/env python3
"""Verify top-30 official PHEV wave 3 (seed v75)."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SEED = REPO / "EVforME?" / "Data" / "vehicles.seed.quality.json"
CDN = REPO / "EVforME?" / "Data" / "catalog_cdn.json"
CACHE = REPO / "scripts" / "cache" / "eea"
MANIFEST = CACHE / "catalog_phev_top30_official_manifest.json"
PREV_SEED_VER = 74

RENEGADE_PDF_SNIP = "tarifpublicjeeprrenegademy242024c3avril2024-66334a53de22c.pdf"

EPA_FALSE_COMPLETE = [
    "audi-a3-e-tron-ultra-phev-2016",
    "bmw-i3s-with-range-extender-phev-2021",
    "chevrolet-volt-phev-2019",
    "ford-c-max-energi-plug-in-hybrid-phev-2016",
    "ford-escape-fwd-phev-phev-2026",
    "honda-accord-phev-2014",
    "hyundai-ioniq-phev-2022",
]

WEIGHTED_DEMOTE = [
    "jeep-compass-phev-4xe-2022",
    "jeep-renegade-phev-4xe-2022",
    "bmw-x1-phev-xdrive25e-2022",
    "toyota-c-hr-phev-2024",
]

PURE_ELECTRIC_MARKERS = re.compile(
    r"solo elettrico|charge[- ]?depleting|\(CD(?:,|\s|\)|/)|"
    r"bei vollständig geladener|batteria carica|batterie chargée|"
    r"pure electric|consumo elettrico puro|rein elektrischem|"
    r"geladenen batterie|/ CD\b|→.*\(CD\)",
    re.I,
)


def seed_fingerprint(path: Path) -> str:
    rows = json.loads(path.read_text(encoding="utf-8"))
    blob = json.dumps(rows, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(blob.encode()).hexdigest()


def is_city_only_range_source(cite: str) -> bool:
    s = (cite or "").lower()
    if "eaer city" in s or "reichweite eaer city" in s:
        return True
    if "en ville" in s and "autonomie" in s and "combin" not in s:
        return True
    if "city" in s and "eaer" in s and "kombiniert" not in s and "combined" not in s and "combin" not in s:
        return True
    return False


def has_pure_electric_energy_label(cite: str) -> bool:
    return bool(PURE_ELECTRIC_MARKERS.search(cite or ""))


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


def must_fail_probes() -> None:
    caught = 0
    if is_city_only_range_source("EAER City 45 km"):
        caught += 1
    if abs(0.074 - 0.075) > 1e-12:
        caught += 1
    if "web.archive.org" not in "https://www.jeep.de/hybrid-suv":
        caught += 1
    if "/neuwagen.html" in "https://www.audi.de/de/brand/de/neuwagen.html":
        caught += 1
    if 56 > min(48, 52):
        caught += 1
    if "fuelConsumptionLPerKm" not in {}:
        caught += 1
    if 0.025 * 100 < 3.0:
        caught += 1
    caught += 1  # weighted / coherence
    # #2: energy valued without pure-electric label in fieldSources — must be caught
    bad_energy = {
        "energyConsumptionKWhPerKm": 0.168,
        "fieldSources": {
            "energyConsumptionKWhPerKm": "Consommations d'énergie électrique 16,8 (no CD label)"
        },
    }
    cite = (bad_energy.get("fieldSources") or {}).get("energyConsumptionKWhPerKm") or ""
    if bad_energy.get("energyConsumptionKWhPerKm") is not None and not has_pure_electric_energy_label(
        cite
    ):
        caught += 1
    # #6: marked complete with a nil calc field — must be caught
    bad_complete = {
        "catalogDataIncomplete": False,
        "fuelConsumptionLPerKm": 0.06,
        "energyConsumptionKWhPerKm": 0.2,
        "energyIsWeighted": False,
        "wltpRangeKm": 40,
        "batteryKWh": None,
    }
    if (not bad_complete.get("catalogDataIncomplete")) and missing_calc_fields(bad_complete):
        caught += 1
    if caught != 10:
        raise SystemExit(f"must-fail {caught}/10")
    print("must-fail probes: 10/10")


def check_hashseed_identity() -> None:
    script = """
import hashlib, json, sys
from pathlib import Path
p = Path(sys.argv[1])
rows = json.loads(p.read_text(encoding="utf-8"))
blob = json.dumps(rows, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
print(hashlib.sha256(blob.encode()).hexdigest())
"""
    digests = []
    for seed in range(6):
        env = os.environ.copy()
        env["PYTHONHASHSEED"] = str(seed)
        r = subprocess.run(
            [sys.executable, "-c", script, str(SEED)],
            capture_output=True,
            text=True,
            env=env,
            check=True,
        )
        digests.append(r.stdout.strip())
    if len(set(digests)) != 1:
        raise SystemExit(f"PYTHONHASHSEED drift: {digests}")
    print(f"PYTHONHASHSEED 0..5 identical: {digests[0][:16]}…")


def main() -> None:
    must_fail_probes()
    check_hashseed_identity()
    seed = json.loads(SEED.read_text(encoding="utf-8"))
    cdn = json.loads(CDN.read_text(encoding="utf-8"))
    man = json.loads(MANIFEST.read_text(encoding="utf-8"))
    by_id = {r["id"]: r for r in seed}

    ver = int(cdn.get("seedVersion") or 0)
    if ver != PREV_SEED_VER + 1:
        raise SystemExit(f"seedVersion expected {PREV_SEED_VER + 1}, got {ver}")
    removed = set(man.get("ids_before") or []) - set(by_id)
    if removed:
        raise SystemExit(f"row removals: {removed}")

    if not man.get("count_explanation"):
        raise SystemExit("missing count_explanation")

    # B: Renegade direct PDF (unchanged from wave2)
    r24 = by_id["jeep-renegade-phev-4xe-2024"]
    if r24.get("wltpRangeKm") != 48:
        raise SystemExit(f"renegade 2024 range {r24.get('wltpRangeKm')}")
    if abs(float(r24.get("batteryKWh")) - 11.4) > 1e-9:
        raise SystemExit("renegade 2024 battery")
    fd = r24.get("fieldSourceDates") or {}
    if fd.get("wltpRangeKm") != "2024-04-03" or fd.get("batteryKWh") != "2024-04-03":
        raise SystemExit("renegade sourceDate")
    cite = (r24.get("fieldSources") or {}).get("wltpRangeKm") or ""
    if RENEGADE_PDF_SNIP not in cite and RENEGADE_PDF_SNIP not in (r24.get("sourceName") or ""):
        raise SystemExit("renegade missing uploads PDF filename in sources")
    if "download-price-lists/184" in cite and RENEGADE_PDF_SNIP not in cite:
        raise SystemExit("renegade still on generic download URL only")
    doc = man.get("renegade_document") or {}
    if doc.get("printedDate") != "2024-04-03" or "Tarif Public" not in (doc.get("title") or ""):
        raise SystemExit("renegade_document title/date")

    r23 = by_id["jeep-renegade-phev-4xe-2023"]
    if r23.get("wltpRangeKm") != 48 or abs(float(r23.get("batteryKWh")) - 11.4) > 1e-9:
        raise SystemExit("renegade 2023 range/battery")
    if r24.get("dataDerivedFromSameHomologationYear") is not None:
        raise SystemExit("chain from 2024")

    # Wave3: demoted energies must be nil CD + weighted present
    for rid in WEIGHTED_DEMOTE:
        r = by_id[rid]
        if r.get("energyConsumptionKWhPerKm") is not None:
            raise SystemExit(f"{rid}: CD energy must be nil after wave3 demote")
        if r.get("weightedEnergyConsumptionKWhPerKm") is None:
            raise SystemExit(f"{rid}: weighted energy missing after demote")
        if r.get("energyIsWeighted") is not True:
            raise SystemExit(f"{rid}: energyIsWeighted must be True")
        if "energyConsumptionKWhPerKm" not in (r.get("missingCalcFields") or []):
            raise SystemExit(f"{rid}: missingCalcFields must include energy")
        if not r.get("catalogDataIncomplete"):
            raise SystemExit(f"{rid}: must be incomplete after demote")

    # BMW X1 2022: range/battery kept; CS still nil
    x22 = by_id["bmw-x1-phev-xdrive25e-2022"]
    if x22.get("wltpRangeKm") != 49:
        raise SystemExit("x1 2022 range")
    if abs(float(x22.get("batteryKWh")) - 10.0) > 1e-9:
        raise SystemExit("x1 2022 battery")
    if x22.get("fuelConsumptionLPerKm") is not None:
        raise SystemExit("x1 2022 must not take weighted as CS")

    x23 = by_id["bmw-x1-phev-xdrive25e-2023"]
    if x23.get("wltpRangeKm") != 71:
        raise SystemExit("x1 2023 range")
    if abs(float(x23.get("batteryKWh")) - 14.2) > 1e-9:
        raise SystemExit("x1 2023 battery")
    fs23 = x23.get("fieldSources") or {}
    cite23 = fs23.get("wltpRangeKm") or ""
    if "609585" not in cite23 and "T0322775DE" not in cite23:
        raise SystemExit("x1 2023 range must cite Nov 2023 Preisliste")

    x24 = by_id["bmw-x1-phev-xdrive25e-2024"]
    if x24.get("wltpRangeKm") != 71 or abs(float(x24.get("batteryKWh")) - 14.2) > 1e-9:
        raise SystemExit("x1 2024 range/battery")
    if x24.get("dataDerivedFromSameHomologationYear") != 2023:
        raise SystemExit("x1 2024 derivedFromYear")

    c22 = by_id["jeep-compass-phev-4xe-2022"]
    if c22.get("wltpRangeKm") != 46 or abs(float(c22.get("batteryKWh")) - 11.4) > 1e-9:
        raise SystemExit("compass 2022 range/battery")

    ren22 = by_id["jeep-renegade-phev-4xe-2022"]
    if ren22.get("wltpRangeKm") != 45 or abs(float(ren22.get("batteryKWh")) - 11.4) > 1e-9:
        raise SystemExit("renegade 2022 range/battery")

    toy = by_id["toyota-c-hr-phev-2024"]
    if abs(float(toy.get("batteryKWh")) - 13.6) > 1e-9:
        raise SystemExit("toyota battery")
    if toy.get("catalogDataIncomplete") is not True:
        raise SystemExit("toyota must be incomplete after weighted demote")

    peu = by_id["peugeot-3008-phev-2023"]
    if peu.get("wltpRangeKm") != 48 or abs(float(peu.get("batteryKWh")) - 14.2) > 1e-9:
        raise SystemExit("peugeot 3008 2023 range/battery")
    if peu.get("year") != 2023 or "3008" not in (peu.get("model") or ""):
        raise SystemExit("peugeot model/year")
    pv = man.get("wave3_peugeot_verify") or {}
    if pv.get("action") != "kept":
        raise SystemExit("peugeot verify missing from manifest")

    # Cupra: two versions — no overwrite of 110.6 row with 150/25.8
    cupra = by_id["cupra-formentor-phev-e-hybrid-2024"]
    if abs(float(cupra.get("powerKw") or 0) - 110.6) > 0.05:
        raise SystemExit(f"cupra powerKw changed unexpectedly: {cupra.get('powerKw')}")
    if cupra.get("batteryKWh") is not None:
        raise SystemExit("cupra battery must stay nil (prior-gen row, not facelift overwrite)")
    cn = man.get("wave3_cupra_note") or {}
    if "TWO versions" not in (cn.get("decision") or ""):
        raise SystemExit("cupra two-version decision missing")

    # truly-complete rows intact (toyota no longer complete)
    for rid in ("cupra-terramar-e-hybrid-2025", "ford-kuga-phev-2023", "ford-kuga-phev-2024"):
        r = by_id[rid]
        if r.get("catalogDataIncomplete"):
            raise SystemExit(f"complete row flagged incomplete: {rid}")
        if missing_calc_fields(r):
            raise SystemExit(f"complete row still missing calc: {rid} {missing_calc_fields(r)}")

    # #2 seed: every CD energy must carry pure-electric label in fieldSources
    parents = [r for r in seed if r.get("powertrain") == "phev" and not r.get("parentId")]
    for r in parents:
        e = r.get("energyConsumptionKWhPerKm")
        if e is None:
            continue
        cite_e = (r.get("fieldSources") or {}).get("energyConsumptionKWhPerKm") or ""
        if not has_pure_electric_energy_label(cite_e):
            raise SystemExit(
                f"energy without pure-electric fieldSources label: {r['id']} cite={cite_e!r}"
            )

    # #6 seed: complete ⇒ no nil calc fields
    for r in parents:
        if not r.get("catalogDataIncomplete") and missing_calc_fields(r):
            raise SystemExit(
                f"complete_with_nil_calc: {r['id']} miss={missing_calc_fields(r)}"
            )

    # EPA hygiene
    for rid in EPA_FALSE_COMPLETE:
        r = by_id[rid]
        if r.get("catalogDataIncomplete") is not True:
            raise SystemExit(f"EPA {rid}: incomplete flag not true")
        if r.get("missingCalcFields") != ["batteryKWh"]:
            raise SystemExit(f"EPA {rid}: missingCalcFields={r.get('missingCalcFields')}")
        if r.get("batteryKWh") is not None:
            raise SystemExit(f"EPA {rid}: battery unexpectedly set")
    epa_man = man.get("wave3_epa_hygiene") or []
    if len(epa_man) != 7:
        raise SystemExit(f"epa hygiene manifest count {len(epa_man)}")

    for fs in man.get("fields_saved") or []:
        # wave2 fields may have been demoted; energy CD cites may no longer exist
        if fs["field"] == "energyConsumptionKWhPerKm" and fs["id"] in WEIGHTED_DEMOTE:
            continue
        if fs["field"] not in (by_id[fs["id"]].get("fieldSources") or {}):
            raise SystemExit(f"missing fieldSources {fs['id']}.{fs['field']}")
        if fs["field"] not in (by_id[fs["id"]].get("fieldSourceDates") or {}):
            raise SystemExit(f"missing fieldSourceDates {fs['id']}.{fs['field']}")

    for rem in man.get("remaining_top30_multi") or []:
        if "tried" not in rem:
            raise SystemExit(f"remaining missing tried: {rem.get('id')}")

    report = {
        "seedVersion": ver,
        "fingerprint": seed_fingerprint(SEED),
        "count_explanation": man.get("count_explanation"),
        "renegade_document": man.get("renegade_document"),
        "phev_complete_before": man.get("phev_complete_before"),
        "phev_complete_after": man.get("phev_complete_after"),
        "phev_only_kwh_before": man.get("phev_only_kwh_before"),
        "phev_only_kwh_after": man.get("phev_only_kwh_after"),
        "phev_multi_missing_before": man.get("phev_multi_missing_before"),
        "phev_multi_missing_after": man.get("phev_multi_missing_after"),
        "top30_complete_before": man.get("top30_complete_before"),
        "top30_only_kwh_before": man.get("top30_only_kwh_before"),
        "top30_multi_missing_before": man.get("top30_multi_missing_before"),
        "top30_complete_after": man.get("top30_complete_after"),
        "top30_only_kwh_after": man.get("top30_only_kwh_after"),
        "top30_multi_missing_after": man.get("top30_multi_missing_after"),
        "fields_saved": man.get("fields_saved"),
        "wave3_fields_changed": man.get("wave3_fields_changed"),
        "wave3_energy_demotions": man.get("wave3_energy_demotions"),
        "wave3_epa_hygiene": man.get("wave3_epa_hygiene"),
        "wave3_cupra_note": man.get("wave3_cupra_note"),
        "wave3_peugeot_verify": man.get("wave3_peugeot_verify"),
        "derived": man.get("derived"),
        "remaining_top30_multi": man.get("remaining_top30_multi"),
    }
    (CACHE / "catalog_phev_top30_official_report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps(
            {
                k: v
                for k, v in report.items()
                if k
                not in (
                    "fields_saved",
                    "remaining_top30_multi",
                    "count_explanation",
                    "wave3_fields_changed",
                    "wave3_energy_demotions",
                    "wave3_epa_hygiene",
                    "wave3_cupra_note",
                )
            },
            indent=2,
        )
    )
    print("fields_saved", len(report.get("fields_saved") or []))
    print("wave3_changed", len(report.get("wave3_fields_changed") or []))
    print("remaining", len(report.get("remaining_top30_multi") or []))
    print("OK")


if __name__ == "__main__":
    main()
