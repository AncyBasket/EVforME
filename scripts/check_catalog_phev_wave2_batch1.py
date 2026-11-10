#!/usr/bin/env python3
"""Must-fail probes + invariants for PHEV wave2 batch1 (seed 78)."""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
from lib.phev_manus_v76_validate import (  # noqa: E402
    has_pure_energy_label,
    missing_calc_fields,
)

SEED = REPO / "EVforME?" / "Data" / "vehicles.seed.quality.json"
CDN = REPO / "EVforME?" / "Data" / "catalog_cdn.json"
MANIFEST = REPO / "scripts" / "cache" / "eea" / "catalog_phev_wave2_batch1_manifest.json"
INVENTORY = REPO / "scripts" / "cache" / "eea" / "catalog_phev_wave2_batch1_inventory.json"
CURRENT_MY = 2026

WEIGHTED_ONLY_HINT = re.compile(
    r"gewichtet|ponderat|weighted|ECAC\s*gewichtet|EC,\s*AC\s*gewichtet",
    re.I,
)


def source_year_ok(url: str, source_date: str, vehicle_year: int, *, homolog: bool) -> bool:
    if homolog:
        return True  # dating enforced via dataDerivedFromSameHomologationYear + dual cite
    if vehicle_year == CURRENT_MY:
        return True
    m = re.search(r"web\.archive\.org/web/(\d{8})", url or "")
    if m:
        return int(m.group(1)[:4]) == int(vehicle_year)
    if source_date and len(source_date) >= 4 and source_date[:4].isdigit():
        if int(source_date[:4]) == int(vehicle_year):
            return True
    return False


def is_generic_url(url: str) -> bool:
    u = (url or "").lower()
    path = urlparse(u).path.rstrip("/")
    if path in ("", "/", "/de", "/de/neuwagen", "/neuwagen"):
        return True
    return any(h in u for h in ("/neuwagen.html", "/brand/de/neuwagen", "/models.html"))


def must_fail_probes() -> None:
    caught = 0
    # 1) pure kWh without pure-electric label
    bad_cite = "Stromverbrauch kombiniert 16,8 kWh/100 (WLTP) next to CO2 gewichtet"
    if not has_pure_energy_label(bad_cite):
        caught += 1
    else:
        raise SystemExit("probe: unlabeled kWh unexpectedly accepted as pure")
    # 2) complete flag with missing field
    fake = {
        "fuelConsumptionLPerKm": 0.06,
        "energyConsumptionKWhPerKm": None,
        "energyIsWeighted": True,
        "wltpRangeKm": 50,
        "batteryKWh": 12,
        "catalogDataIncomplete": False,
    }
    if missing_calc_fields(fake) and fake["catalogDataIncomplete"] is False:
        caught += 1
    else:
        raise SystemExit("probe: incomplete-as-complete not caught")
    # 3) missing sourceDate / dating for past year live page
    if not source_year_ok("https://www.jeep.de/hybrid-suv", "", 2024, homolog=False):
        caught += 1
    else:
        raise SystemExit("probe: undated live page accepted for past MY")
    # 4) generic URL
    if is_generic_url("https://www.audi.de/de/brand/de/neuwagen.html"):
        caught += 1
    else:
        raise SystemExit("probe: generic URL not rejected")
    # 5) weighted-only cite must not satisfy pure label
    if WEIGHTED_ONLY_HINT.search("ECAC gewichtet, kombiniert 16,0 kWh") and not has_pure_energy_label(
        "ECAC gewichtet, kombiniert 16,0 kWh"
    ):
        caught += 1
    else:
        raise SystemExit("probe: weighted cite treated as pure")
    if caught < 5:
        raise SystemExit(f"probes incomplete caught={caught}")


def main() -> None:
    must_fail_probes()

    seed = json.loads(SEED.read_text(encoding="utf-8"))
    cdn = json.loads(CDN.read_text(encoding="utf-8"))
    man = json.loads(MANIFEST.read_text(encoding="utf-8"))
    inv = json.loads(INVENTORY.read_text(encoding="utf-8"))

    if int(cdn.get("seedVersion") or 0) != 78:
        raise SystemExit(f"seedVersion want 78 got {cdn.get('seedVersion')}")
    if len(seed) != 6977:
        raise SystemExit(f"rows {len(seed)}")
    by_id = {r["id"]: r for r in seed}
    if [r["id"] for r in seed] != man["ids_before"]:
        raise SystemExit("id order/set drift vs manifest")

    m3 = [r for r in seed if r["id"].startswith("tesla-model-3") and r.get("year") == 2026]
    if len(m3) != 4:
        raise SystemExit(f"m3 {len(m3)}")
    if sorted(r["id"] for r in m3) != sorted(man["m3_ids"]):
        raise SystemExit("m3 id set drift")

    # non-PHEV byte-identical (tech fields)
    conf = {
        "confidenceScore",
        "confidenceScoreLegacy",
        "confidencePolicyVersion",
        "confidenceEvidence",
    }
    non = [{k: v for k, v in r.items() if k not in conf} for r in seed if r.get("powertrain") != "phev"]
    sha = hashlib.sha256(
        json.dumps(non, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()
    if sha != man["non_phev_tech_sha"]:
        raise SystemExit(f"non-PHEV sha drift {sha} vs {man['non_phev_tech_sha']}")

    # completed Kuga 2022
    kuga = by_id["ford-kuga-phev-2022"]
    if kuga.get("catalogDataIncomplete"):
        raise SystemExit("kuga 2022 still incomplete")
    if missing_calc_fields(kuga):
        raise SystemExit(f"kuga missing {missing_calc_fields(kuga)}")
    cite = (kuga.get("fieldSources") or {}).get("energyConsumptionKWhPerKm") or ""
    if not has_pure_energy_label(cite):
        raise SystemExit("kuga CD cite missing pure-electric label")
    if kuga.get("dataDerivedFromSameHomologationYear") != 2024:
        raise SystemExit("kuga missing homolog year")
    for field in ("fuelConsumptionLPerKm", "energyConsumptionKWhPerKm", "wltpRangeKm", "batteryKWh"):
        if not (kuga.get("fieldSourceDates") or {}).get(field):
            raise SystemExit(f"kuga missing sourceDate {field}")

    # no complete row with missing calc fields
    for r in seed:
        if r.get("powertrain") != "phev":
            continue
        miss = missing_calc_fields(r)
        flagged = bool(r.get("catalogDataIncomplete"))
        if miss and not flagged:
            raise SystemExit(f"complete-with-missing {r['id']}: {miss}")
        if not miss and flagged:
            raise SystemExit(f"incomplete-flag-with-full-fields {r['id']}")
        e = r.get("energyConsumptionKWhPerKm")
        if e is not None and r.get("energyIsWeighted") is not True:
            cite = (r.get("fieldSources") or {}).get("energyConsumptionKWhPerKm") or ""
            if cite and not has_pure_energy_label(cite):
                raise SystemExit(f"pure kWh without label {r['id']}: {cite[:120]}")

    # inventory batch size
    if len(inv.get("batch1_candidates") or []) != 40:
        raise SystemExit("batch1 candidates != 40")

    print("OK")
    print(
        json.dumps(
            {
                "seedVersion": 78,
                "rows": len(seed),
                "completed": len(man["completed"]),
                "partial": len(man["partial"]),
                "left_nil": len(man["left_nil"]),
                "non_phev_tech_sha": sha,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
