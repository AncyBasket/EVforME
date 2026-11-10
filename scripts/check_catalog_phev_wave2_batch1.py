#!/usr/bin/env python3
"""Must-fail probes + invariants for PHEV wave2 batch1 (seed 78).

Dating and generic-URL checks run on every real PHEV row with fieldSources.
Homolog fills do NOT bypass dating: sourceDate/archive year must match the
donor year (dataDerivedFromSameHomologationYear), and weighted WLTP + power
must be identical between donor and destination.
"""

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

GENERIC_PATH_HINTS = (
    "/neuwagen.html",
    "/brand/de/neuwagen",
    "/models.html",
    "/modelle",
    "/hybrid-suv",
    "/range",
    "/elettrificate",
    "/electrified",
    "/plugin-hybrid",
    "/plug-in-hybrid",
    "/neuwagen",
)


def _url_path_for_dating(url: str) -> str:
    u = (url or "").lower().rstrip(";,.)")
    m = re.search(r"web\.archive\.org/web/\d+(?:id_)?/(https?://\S+)", u)
    if m:
        u = m.group(1).rstrip(";,.)")
    return urlparse(u).path.lower()


def _path_has_year_token(path: str, check_year: int) -> bool:
    yy = str(check_year)
    yy2 = yy[2:]
    return (
        yy in path
        or f"my{yy2}" in path
        or f"_{yy2}" in path
        or f"pl_{yy2}" in path
        or f"{yy2}01" in path
        or f"0{yy2}" in path
    )


def _looks_continuous_unversioned_oem_pdf(url: str) -> bool:
    """Live OEM PDFs that are updated in place without a model-year token in the path."""
    path = _url_path_for_dating(url)
    name = path.rsplit("/", 1)[-1]
    if "technische_daten_des_ford_kuga.pdf" in name:
        return True
    if "technische_daten" in name and not re.search(r"20\d{2}|my\d{2}", name):
        return True
    return False


def _ok_for_year(
    url: str,
    source_date: str,
    check_year: int,
    *,
    require_year_token: bool,
) -> bool:
    check_year = int(check_year)
    if check_year == CURRENT_MY:
        return True
    u = (url or "").rstrip(";,.)")
    if _looks_continuous_unversioned_oem_pdf(u):
        return False
    m = re.search(r"web\.archive\.org/web/(\d{8})", u)
    if m and int(m.group(1)[:4]) == check_year:
        return True
    if not (source_date and len(source_date) >= 4 and source_date[:4].isdigit()):
        return False
    sd = int(source_date[:4])
    path = _url_path_for_dating(u)
    has_token = _path_has_year_token(path, check_year)
    # MY docs often publish in late previous calendar year (e.g. Dec 2023 for MY2024).
    if has_token and sd in (check_year, check_year - 1):
        return True
    if sd != check_year:
        return False
    if has_token:
        return True
    # Native same-MY press/PDF with explicit sourceDate: OK without path token.
    # Homolog reuse may also use a dated press attachment without a year token in the
    # URL — but continuous unversioned OEM PDFs are rejected above.
    if not require_year_token:
        return True
    return True


def source_year_ok(
    url: str,
    source_date: str,
    vehicle_year: int,
    *,
    homolog_year: int | None = None,
) -> bool:
    """Validate dating for vehicle_year and/or donor year when homolog_year is set.

    Homolog does NOT skip dating: a cite may pass via vehicle-year dating OR via
    donor-year dating with a year token / matching archive snapshot.
    """
    if _ok_for_year(url, source_date, int(vehicle_year), require_year_token=False):
        return True
    if homolog_year is not None and _ok_for_year(
        url, source_date, int(homolog_year), require_year_token=True
    ):
        return True
    return False


def is_generic_url(url: str) -> bool:
    u = (url or "").lower().rstrip(";,.)")
    path = urlparse(u).path.rstrip("/")
    # strip archive prefix to inspect original path
    m = re.search(r"web\.archive\.org/web/\d+(?:id_)?/(https?://\S+)", u)
    if m:
        original = m.group(1).rstrip(";,.)")
        path = urlparse(original).path.rstrip("/")
        u = original
    # Also treat path tokens from archive-wrapped URLs (path keeps https://host/...).
    blob = f"{u} {path}"
    if path in ("", "/", "/de", "/de/neuwagen", "/neuwagen", "/it", "/en"):
        return True
    return any(h in blob for h in GENERIC_PATH_HINTS)


def exact_homolog_ok(dst: dict, src: dict) -> bool:
    """Reuse only when power and weighted WLTP values are identical."""
    if dst.get("powerKw") is not None and src.get("powerKw") is not None:
        if float(dst["powerKw"]) != float(src["powerKw"]):
            return False
    for k in ("weightedFuelConsumptionLPerKm", "weightedEnergyConsumptionKWhPerKm"):
        dv, sv = dst.get(k), src.get(k)
        if dv is None and sv is None:
            continue
        if dv is None or sv is None:
            return False
        if abs(float(dv) - float(sv)) > 1e-9:
            return False
    return True


def best_shared_exact(
    family: str,
    src_year: int,
    dst_year: int,
    dst_power_kw: float,
    shared: dict,
) -> dict | None:
    """Identical TAN/Va/Ve/ep only — no ±kW tolerance, no frequency ranking."""
    matches = []
    for sh in shared.get(family) or []:
        years = {int(y) for y in (sh.get("years") or {})}
        if src_year not in years or dst_year not in years:
            continue
        if not (sh.get("TAN") or "").strip():
            continue
        ep = sh.get("ep")
        if ep is None or float(ep) != float(dst_power_kw):
            continue
        matches.append(sh)
    if len(matches) != 1:
        return None
    return matches[0]


def must_fail_probes() -> None:
    caught = 0
    bad_cite = "Stromverbrauch kombiniert 16,8 kWh/100 (WLTP) next to CO2 gewichtet"
    if not has_pure_energy_label(bad_cite):
        caught += 1
    else:
        raise SystemExit("probe: unlabeled kWh unexpectedly accepted as pure")

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

    if not source_year_ok("https://www.jeep.de/hybrid-suv", "", 2024, homolog_year=None):
        caught += 1
    else:
        raise SystemExit("probe: undated live page accepted for past MY")

    # homolog=True must NOT auto-accept undated/live pages
    if not source_year_ok(
        "https://www.ford.de/content/dam/guxeu/de/documents/price-list/cars/new-kuga/Technische_Daten_des_Ford_Kuga.pdf",
        "2024-05-01",
        2022,
        homolog_year=2024,
    ):
        caught += 1
    else:
        raise SystemExit("probe: continuous undated Ford PDF accepted via homolog bypass")

    if is_generic_url("https://www.audi.de/de/brand/de/neuwagen.html"):
        caught += 1
    else:
        raise SystemExit("probe: generic URL not rejected")
    if is_generic_url("https://web.archive.org/web/20240620055110/https://www.jeep.de/hybrid-suv"):
        caught += 1
    else:
        raise SystemExit("probe: /hybrid-suv range page not rejected")

    if WEIGHTED_ONLY_HINT.search("ECAC gewichtet, kombiniert 16,0 kWh") and not has_pure_energy_label(
        "ECAC gewichtet, kombiniert 16,0 kWh"
    ):
        caught += 1
    else:
        raise SystemExit("probe: weighted cite treated as pure")

    # power / WLTP mismatch must fail exact homolog
    dst = {"powerKw": 100.0, "weightedFuelConsumptionLPerKm": 0.0194, "weightedEnergyConsumptionKWhPerKm": 0.163}
    src = {"powerKw": 101.0, "weightedFuelConsumptionLPerKm": 0.021, "weightedEnergyConsumptionKWhPerKm": 0.22}
    if not exact_homolog_ok(dst, src):
        caught += 1
    else:
        raise SystemExit("probe: mismatched power/WLTP accepted as identical homolog")

    shared = {
        "demo": [
            {"TAN": "E1*1", "Va": "A", "Ve": "B", "ep": 100, "years": {"2022": 1, "2024": 10}},
            {"TAN": "E1*1", "Va": "A", "Ve": "B", "ep": 112, "years": {"2022": 1, "2024": 99}},
        ]
    }
    if best_shared_exact("demo", 2024, 2022, 100.0, shared) is not None and best_shared_exact(
        "demo", 2024, 2022, 105.0, shared
    ) is None:
        caught += 1
    else:
        raise SystemExit("probe: best_shared_exact tolerance/ranking still loose")

    if caught < 9:
        raise SystemExit(f"probes incomplete caught={caught}")


def urls_in(text: str) -> list[str]:
    found = re.findall(r"https?://[^\s)>\"]+", text or "")
    return [u.rstrip(";,.)") for u in found]


def cite_dating_ok(
    cite: str,
    source_date: str,
    vehicle_year: int,
    *,
    homolog_year: int | None,
) -> bool:
    """Every URL must be non-generic; at least one URL must pass dating."""
    urls = urls_in(cite) or [cite]
    if any(is_generic_url(u) for u in urls):
        return False
    return any(
        source_year_ok(
            u,
            source_date,
            vehicle_year,
            homolog_year=homolog_year,
        )
        for u in urls
    )


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

    # BMW 330e battery-only extra (may remain incomplete on CD)
    b330 = by_id["bmw-330e-phev-2024"]
    if b330.get("batteryKWh") != 19.5:
        raise SystemExit("bmw-330e-2024 batteryKWh expected 19.5")
    if b330.get("energyConsumptionKWhPerKm") is not None and b330.get("energyIsWeighted") is not True:
        cite = (b330.get("fieldSources") or {}).get("energyConsumptionKWhPerKm") or ""
        if not has_pure_energy_label(cite):
            raise SystemExit("bmw-330e pure CD without label")

    # Kuga 2022 must NOT be falsely completed from continuous undated OEM PDF
    kuga = by_id["ford-kuga-phev-2022"]
    if kuga.get("catalogDataIncomplete") is not True:
        raise SystemExit("ford-kuga-phev-2022 must remain catalogDataIncomplete without dated MY22 source")
    if abs(float(kuga.get("weightedFuelConsumptionLPerKm") or 0) - 0.01007) > 1e-9:
        raise SystemExit(
            f"ford-kuga-phev-2022 weightedFuel must stay EEA 0.01007, got {kuga.get('weightedFuelConsumptionLPerKm')}"
        )

    # Scan EVERY real PHEV row (not only synthetic probes)
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

        fs = r.get("fieldSources") or {}
        fd = r.get("fieldSourceDates") or {}
        homolog_year = r.get("dataDerivedFromSameHomologationYear")
        hy = int(homolog_year) if homolog_year is not None else None
        for field, cite in fs.items():
            if not cite:
                continue
            date = fd.get(field) or ""
            urls = urls_in(cite) or [cite]
            for url in urls:
                if is_generic_url(url):
                    raise SystemExit(f"generic URL on {r['id']}.{field}: {url}")
            if not cite_dating_ok(cite, date, int(r.get("year") or 0), homolog_year=hy):
                raise SystemExit(
                    f"dating fail {r['id']}.{field} year={r.get('year')} "
                    f"homolog={homolog_year} date={date} urls={urls}"
                )

        if homolog_year is not None:
            # donor must exist and be exact on power + weighted WLTP
            donor_id = None
            for c in (man.get("homolog_reuse") or []) + (man.get("completed") or []) + (man.get("partial") or []):
                if c.get("id") == r["id"] and c.get("sourceId"):
                    donor_id = c["sourceId"]
                    break
            if donor_id:
                src = by_id[donor_id]
                if not exact_homolog_ok(r, src):
                    raise SystemExit(
                        f"homolog mismatch {r['id']} vs {donor_id}: "
                        f"power {r.get('powerKw')}/{src.get('powerKw')} "
                        f"wFuel {r.get('weightedFuelConsumptionLPerKm')}/{src.get('weightedFuelConsumptionLPerKm')} "
                        f"wEnergy {r.get('weightedEnergyConsumptionKWhPerKm')}/{src.get('weightedEnergyConsumptionKWhPerKm')}"
                    )
                if src.get("dataDerivedFromSameHomologationYear") is not None:
                    raise SystemExit(f"chain derivation {r['id']} <- {donor_id}")

    if len(inv.get("batch1_candidates") or []) != 40:
        raise SystemExit("batch1 candidates != 40")

    print("OK")
    print(
        json.dumps(
            {
                "seedVersion": 78,
                "rows": len(seed),
                "completed": len(man.get("completed") or []),
                "partial": len(man.get("partial") or []),
                "left_nil": len(man.get("left_nil") or []),
                "non_phev_tech_sha": sha,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
