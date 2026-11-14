#!/usr/bin/env python3
"""Must-fail probes + invariants for PHEV wave2 batch2 (seed 84).

Dating and generic-URL checks run on every real PHEV row with fieldSources.
Homolog fills do NOT bypass dating: sourceDate/archive year must match the
donor year (dataDerivedFromSameHomologationYear), and weighted WLTP + power
must be identical between donor and destination.

Research pass: every filled calc field on a batch2 row must appear in the
manifest; pure CD must not equal / be derived from weighted energy.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

MI_TO_KM = 1.609344


def miles_to_km_floor(miles: float) -> int:
    """Convert printed miles to catalog km with prudent floor (never round up)."""
    return int(math.floor(float(miles) * MI_TO_KM))

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
from lib.phev_manus_v76_validate import (  # noqa: E402
    has_pure_energy_label,
    missing_calc_fields,
)

SEED = REPO / "EVforME?" / "Data" / "vehicles.seed.quality.json"
CDN = REPO / "EVforME?" / "Data" / "catalog_cdn.json"
MANIFEST = REPO / "scripts" / "cache" / "eea" / "catalog_phev_wave2_batch2_manifest.json"
INVENTORY = REPO / "scripts" / "cache" / "eea" / "catalog_phev_wave2_batch2_inventory.json"
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
    "/hybrid-elektrisch",
    "/range",
    "/elettrificate",
    "/electrified",
    "/plugin-hybrid",
    "/plug-in-hybrid",
    "/neuwagen",
)

PROVENANCE_REQUIRED_FIELDS = (
    "fuelConsumptionLPerKm",
    "energyConsumptionKWhPerKm",
    "wltpRangeKm",
    "batteryKWh",
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
    # A later calendar year in the URL/filename cannot date an earlier model year
    # (e.g. …/21-07-2025_preisliste_2025_… for MY2024), regardless of sourceDate.
    if _url_years_after(u, check_year):
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
    # Homolog reuse requires a year token / matching archive (require_year_token=True).
    if require_year_token:
        return False
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
    A URL/filename year strictly after the vehicle year always fails (even with a
    same-MY sourceDate).
    """
    # Future-year URL tokens fail for the vehicle year before homolog fallback.
    if _url_years_after(url, int(vehicle_year)):
        # Homolog onto a later donor year may still accept a donor-year URL.
        if homolog_year is None:
            return False
        if _url_years_after(url, int(homolog_year)):
            return False
        return _ok_for_year(url, source_date, int(homolog_year), require_year_token=True)
    if _ok_for_year(url, source_date, int(vehicle_year), require_year_token=False):
        return True
    if homolog_year is not None and _ok_for_year(
        url, source_date, int(homolog_year), require_year_token=True
    ):
        return True
    return False


def is_generic_url(url: str) -> bool:
    u = (url or "").lower().rstrip(";,.)")
    # Bare source tokens (EPA-FuelEconomy, etc.) are not landing-page URLs.
    if not u.startswith("http://") and not u.startswith("https://") and "web.archive.org" not in u:
        return False
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
    *,
    tan: str | None = None,
    va: str | None = None,
    ve: str | None = None,
) -> dict | None:
    """Shared-map homolog fingerprint: TAN + Va + Ve + ep (power).

    Missing ep is rejected. Candidates must carry non-empty TAN/Va/Ve.
    When tan/va/ve are provided, require an exact match on that fingerprint.
    When omitted, accept only if all year-pair+ep candidates collapse to one
    unique (TAN, Va, Ve, ep) — multiple distinct TANs at the same power → None.
    No ±kW tolerance; no frequency ranking.
    """
    matches = []
    for sh in shared.get(family) or []:
        years = {int(y) for y in (sh.get("years") or {})}
        if src_year not in years or dst_year not in years:
            continue
        if not (sh.get("TAN") or "").strip():
            continue
        if not (sh.get("Va") or "").strip():
            continue
        if not (sh.get("Ve") or "").strip():
            continue
        ep = sh.get("ep")
        if ep is None or float(ep) != float(dst_power_kw):
            continue
        if tan is not None and (sh.get("TAN") or "") != tan:
            continue
        if va is not None and (sh.get("Va") or "") != va:
            continue
        if ve is not None and (sh.get("Ve") or "") != ve:
            continue
        matches.append(sh)
    if not matches:
        return None
    keys = {
        ((m.get("TAN") or ""), (m.get("Va") or ""), (m.get("Ve") or ""), float(m["ep"]))
        for m in matches
    }
    if len(keys) != 1:
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
    if is_generic_url("https://www.ford.de/hybrid-elektrisch/energie"):
        caught += 1
    else:
        raise SystemExit("probe: /hybrid-elektrisch landing not rejected")
    if _looks_continuous_unversioned_oem_pdf(
        "https://www.ford.de/content/dam/guxeu/de/documents/price-list/cars/new-kuga/Technische_Daten_des_Ford_Kuga.pdf"
    ):
        caught += 1
    else:
        raise SystemExit("probe: continuous Ford typenblatt not flagged")

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

    # Same power (+ would pass exact_homolog_ok on weighted) but distinct TANs → rejected.
    twin_tan = {
        "demo": [
            {
                "TAN": "E1*AAA",
                "Va": "VA",
                "Ve": "VE1",
                "ep": 110,
                "years": {"2023": 1, "2024": 1},
            },
            {
                "TAN": "E1*BBB",
                "Va": "VA",
                "Ve": "VE1",
                "ep": 110,
                "years": {"2023": 1, "2024": 1},
            },
        ]
    }
    same_power = {
        "powerKw": 110.0,
        "weightedFuelConsumptionLPerKm": 0.01481,
        "weightedEnergyConsumptionKWhPerKm": 0.179,
    }
    if exact_homolog_ok(same_power, same_power) and best_shared_exact(
        "demo", 2024, 2023, 110.0, twin_tan
    ) is None:
        caught += 1
    else:
        raise SystemExit(
            "probe: distinct TAN at same power/weighted not rejected by best_shared_exact"
        )
    # Claimed fingerprint disambiguates when TAN/Va/Ve are supplied.
    if best_shared_exact(
        "demo",
        2024,
        2023,
        110.0,
        twin_tan,
        tan="E1*AAA",
        va="VA",
        ve="VE1",
    ) is None:
        raise SystemExit("probe: claimed TAN/Va/Ve fingerprint not accepted")
    caught += 1
    mazda_2025 = (
        "https://media-assets.mazda.eu/raw/upload/mazdade/globalassets/pdfs/brochure/"
        "cx-60/21-07-2025_preisliste_2025_mazda-cx-60.pdf"
    )
    # MY2024 must reject a 2025 listino URL even with a same-MY (or any 2024) sourceDate.
    if not source_year_ok(mazda_2025, "2024-01-01", 2024, homolog_year=None):
        caught += 1
    else:
        raise SystemExit("probe: Mazda 2025 URL accepted for MY2024 with sourceDate 2024-01-01")
    if not source_year_ok(mazda_2025, "2024-06-15", 2024, homolog_year=None):
        caught += 1
    else:
        raise SystemExit("probe: Mazda 2025 URL accepted for MY2024 with sourceDate 2024-06-15")
    # Positive control: official January Stellantis listino dates as 2023-01-01.
    stellantis_jan = (
        "https://www.media.stellantis.com/uploads/de/model-pricelist/"
        "preisliste_grand_cherokee_4xe_januar_20234-6486c171a11d8.pdf"
    )
    if extract_document_date(stellantis_jan) == "2023-01-01" and source_year_ok(
        stellantis_jan, "2023-01-01", 2023, homolog_year=None
    ):
        caught += 1
    else:
        raise SystemExit("probe: Stellantis januar_2023 listino not dated/accepted as 2023-01-01")

    # Future-year Audi eTD (_240314 / Date 2024) must not date MY2022.
    audi_2024 = (
        "https://uploads.audi-mediacenter.com/system/production/car_motorizations/1239/"
        "file_en/a558808317b94f42ac509c09439d17b6612fc530/"
        "eTD-Audi-Q3-Sportback-45-TFSIe-S_tronic-110kW_180kW_240314.pdf"
    )
    if not source_year_ok(audi_2024, "2024-03-14", 2022, homolog_year=None):
        caught += 1
    else:
        raise SystemExit("probe: 2024 Audi eTD accepted for MY2022")

    # Generic landing rejected.
    if is_generic_url("https://www.audi.de/de/brand/de/modelle/q3.html") or is_generic_url(
        "https://www.mercedes-benz.de/passengercars/models/suv/glc/overview.html"
    ):
        # /modelle is generic; overview may not match — count only when /modelle hits
        pass
    if is_generic_url("https://www.audi.de/de/brand/de/modelle/q3.html"):
        caught += 1
    else:
        raise SystemExit("probe: /modelle landing not rejected")

    # Pure CD must not equal weighted energy (derivation / copy).
    if not pure_cd_equals_weighted(0.179, 0.179):
        raise SystemExit("probe: equal pure/weighted not flagged")
    caught += 1
    if pure_cd_equals_weighted(0.209, 0.179):
        raise SystemExit("probe: unequal pure/weighted falsely flagged")
    caught += 1

    # Manifest must list every filled calc field for researched batch2 rows.
    fake_man = {
        "batch2_ids": ["demo-phev-2024"],
        "partial": [{"id": "demo-phev-2024", "filled": {"batteryKWh": 13.0}}],
        "completed": [],
        "homolog_reuse": [],
        "left_nil": [],
    }
    fake_row = {
        "id": "demo-phev-2024",
        "fuelConsumptionLPerKm": 0.072,
        "batteryKWh": 13.0,
    }
    if not manifest_covers_filled_fields(fake_row, fake_man):
        caught += 1
    else:
        raise SystemExit("probe: fill without manifest entry not caught")
    # Positive: alreadyPresent on left_nil covers pre-existing fields.
    ok_man = {
        "batch2_ids": ["demo-phev-2024"],
        "partial": [],
        "completed": [],
        "homolog_reuse": [],
        "left_nil": [
            {
                "id": "demo-phev-2024",
                "alreadyPresent": {"batteryKWh": 13.0},
            }
        ],
    }
    ok_row = {"id": "demo-phev-2024", "batteryKWh": 13.0}
    if manifest_covers_filled_fields(ok_row, ok_man):
        caught += 1
    else:
        raise SystemExit("probe: alreadyPresent on left_nil not accepted")

    # require_year_token must fail when donor-year dating has no year token / archive.
    # Same calendar sourceDate alone is not enough for homolog reuse.
    bare_press = "https://www.press.example.com/deutschland/article/attachment/T000/1"
    if not source_year_ok(bare_press, "2023-09-27", 2024, homolog_year=2023):
        caught += 1
    else:
        raise SystemExit(
            "probe: require_year_token inert — homolog donor-year cite without year token accepted"
        )

    # Mile→km conversions for EAER must floor (prudent min). 29.8 mi → 47.96… → 47, not 48.
    if miles_to_km_floor(29.8) == 47 and miles_to_km_floor(29.8) != 48:
        caught += 1
    else:
        raise SystemExit(
            f"probe: miles_to_km_floor(29.8) want 47 got {miles_to_km_floor(29.8)}"
        )
    if miles_to_km_floor(35.4) == 56:  # 35.4*1.609344=56.97… → 56, not 57
        caught += 1
    else:
        raise SystemExit(
            f"probe: miles_to_km_floor(35.4) want 56 got {miles_to_km_floor(35.4)}"
        )

    if caught < 21:
        raise SystemExit(f"probes incomplete caught={caught}")


def assert_battery_convention_matches_seed(man: dict, by_id: dict) -> None:
    """Every structured thisPass entry must match seed batteryKWh (nil vs numeric)."""
    bc = man.get("battery_convention") or {}
    entries = bc.get("thisPass") or []
    if not entries:
        raise SystemExit("battery_convention.thisPass missing")
    for entry in entries:
        if isinstance(entry, str):
            raise SystemExit(
                f"battery_convention.thisPass must be structured {{id,batteryKWh,note}}, got string: {entry[:80]}"
            )
        rid = entry.get("id")
        if not rid or rid not in by_id:
            raise SystemExit(f"battery_convention unknown id: {rid}")
        claimed = entry.get("batteryKWh")
        actual = by_id[rid].get("batteryKWh")
        if claimed is None:
            if actual is not None:
                raise SystemExit(
                    f"battery_convention {rid}: claimed nil but seed has {actual}"
                )
        else:
            if actual is None:
                raise SystemExit(
                    f"battery_convention {rid}: claimed {claimed} but seed is nil"
                )
            if abs(float(actual) - float(claimed)) > 1e-9:
                raise SystemExit(
                    f"battery_convention {rid}: claimed {claimed} != seed {actual}"
                )
        note = (entry.get("note") or "").strip()
        if not note:
            raise SystemExit(f"battery_convention {rid}: note required")


def pure_cd_equals_weighted(pure: float | None, weighted: float | None) -> bool:
    """True when a purported pure CD value is identical to weighted energy (illegal)."""
    if pure is None or weighted is None:
        return False
    return abs(float(pure) - float(weighted)) <= 1e-12


def manifest_covers_filled_fields(row: dict, man: dict) -> bool:
    """Every non-nil calc field on a batch2 row must appear in a manifest fill entry
    or in left_nil.alreadyPresent (pre-existing from earlier waves)."""
    rid = row.get("id")
    batch = set(man.get("batch2_ids") or [])
    if rid not in batch:
        return True
    covered: set[str] = set()
    for bucket in ("completed", "partial", "homolog_reuse"):
        for entry in man.get(bucket) or []:
            if entry.get("id") != rid:
                continue
            covered.update((entry.get("filled") or {}).keys())
    for entry in man.get("left_nil") or []:
        if entry.get("id") != rid:
            continue
        covered.update((entry.get("alreadyPresent") or {}).keys())
    for field in PROVENANCE_REQUIRED_FIELDS:
        if row.get(field) is None:
            continue
        if field not in covered:
            return False
    return True


def urls_in(text: str) -> list[str]:
    found = re.findall(r"https?://[^\s)>\"]+", text or "")
    return [u.rstrip(";,.)") for u in found]


def extract_document_date(text: str) -> str | None:
    """Parse a real document date from cite/URL text — never invent YYYY-01-01."""
    t = text or ""
    m = re.search(r"(20\d{2})-(\d{2})-(\d{2})", t)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    # Explicit day.month.year / gültig ab 01/2023 / valid as of 01.01.2024
    m = re.search(
        r"(?:gültig\s+ab|valid\s+as\s+of|information\s+valid\s+as\s+of)\s*"
        r"0?1(?:[./]0?1)?[./](20\d{2})",
        t,
        re.I,
    )
    if m:
        return f"{m.group(1)}-01-01"
    m = re.search(r"(?<!\d)(\d{2})[-_/](\d{2})[-_/](20\d{2})(?!\d)", t)
    if m:
        return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
    # Compact YYYYMMDD only when clearly 8 digits (avoid januar_20234 → false 2023-04-..)
    m = re.search(r"(?<!\d)(20\d{2})(\d{2})(\d{2})(?!\d)", t)
    if m and 1 <= int(m.group(2)) <= 12 and 1 <= int(m.group(3)) <= 31:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    months = {
        "januar": 1, "january": 1, "gennaio": 1,
        "februar": 2, "february": 2, "febbraio": 2,
        "märz": 3, "maerz": 3, "march": 3, "marzo": 3,
        "april": 4, "aprile": 4,
        "mai": 5, "may": 5, "maggio": 5,
        "juni": 6, "june": 6, "giugno": 6,
        "juli": 7, "july": 7, "luglio": 7,
        "august": 8, "agosto": 8,
        "september": 9, "septembre": 9, "settembre": 9,
        "oktober": 10, "october": 10, "ottobre": 10,
        "november": 11, "novembre": 11,
        "dezember": 12, "december": 12, "dicembre": 12,
    }
    low = t.lower()
    for name, mo in months.items():
        # Filenames use underscores (4xe_januar_20234): `_` is a word char, so `\b`
        # before/after the month name fails. Allow non-letter delimiters instead.
        m = re.search(
            rf"(?<![a-zäöüß]){re.escape(name)}(?:[^a-zäöüß0-9]+)(20\d{{2}})",
            low,
        )
        if m:
            return f"{m.group(1)}-{mo:02d}-01"
        m = re.search(
            rf"(20\d{{2}})(?:[^a-zäöüß0-9]+)(?![a-zäöüß]){re.escape(name)}(?![a-zäöüß])",
            low,
        )
        if m:
            return f"{m.group(1)}-{mo:02d}-01"
    return None


def is_real_january_document_date(cite: str, date: str) -> bool:
    """True when YYYY-01-01 is grounded in the cite (month name / gültig ab / valid as of).

    Distinguishes official January listini from invented model-year-start stamps.
    """
    if not (date and date.endswith("-01-01") and len(date) >= 10 and date[:4].isdigit()):
        return False
    real = extract_document_date(cite or "")
    return real == date


def _url_years_after(url: str, year: int) -> list[int]:
    """Calendar years appearing in URL/filename that are strictly after `year`."""
    path = _url_path_for_dating(url)
    blob = f"{(url or '').lower()} {path}"
    # Strip archive.org /web/YYYYMMDDhhmmss/ stamps so snapshot years do not count
    # as document years for future-year rejection.
    blob = re.sub(r"web\.archive\.org/web/\d+(?:id_)?/", "web.archive.org/web/", blob)
    found = []
    for m in re.finditer(r"(?<!\d)(20\d{2})(?!\d)", blob):
        y = int(m.group(1))
        if y > int(year):
            found.append(y)
    return found


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

    if int(cdn.get("seedVersion") or 0) != 84:
        raise SystemExit(f"seedVersion want 84 got {cdn.get('seedVersion')}")
    if int(man.get("seedVersion") or 0) != 84:
        raise SystemExit(f"manifest seedVersion want 84 got {man.get('seedVersion')}")
    if len(seed) != 6977:
        raise SystemExit(f"rows {len(seed)}")
    by_id = {r["id"]: r for r in seed}
    if [r["id"] for r in seed] != man["ids_before"]:
        raise SystemExit("id order/set drift vs manifest")
    if len(man.get("batch2_ids") or []) != 40:
        raise SystemExit("manifest batch2_ids != 40")
    if len(man.get("left_nil") or []) + len(
        {e["id"] for e in (man.get("partial") or []) + (man.get("completed") or []) + (man.get("homolog_reuse") or []) if e["id"] in set(man.get("batch2_ids") or [])}
    ) < 40:
        # Every batch2 id must appear in completed, partial, homolog_reuse, or left_nil
        covered = {e["id"] for e in (man.get("partial") or []) + (man.get("completed") or []) + (man.get("homolog_reuse") or []) + (man.get("left_nil") or [])}
        missing = [i for i in man["batch2_ids"] if i not in covered]
        if missing:
            raise SystemExit(f"batch2 ids missing from manifest outcomes: {missing[:5]}")

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
    if b330.get("wltpRangeKm") is not None:
        # Battery press extra must not keep an unverified EAER/range figure.
        raise SystemExit("bmw-330e-2024 wltpRangeKm must be nil without a dated EAER source")
    if (b330.get("fieldSources") or {}).get("wltpRangeKm"):
        raise SystemExit("bmw-330e-2024 must not claim wltpRangeKm fieldSources from battery press")
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

    # Kuga 2023/2024: continuous typenblatt values must not linger without dated fieldSources
    for kid in ("ford-kuga-phev-2023", "ford-kuga-phev-2024"):
        kr = by_id[kid]
        if kr.get("catalogDataIncomplete") is not True:
            raise SystemExit(f"{kid} must remain incomplete without dated OEM provenance")
        for fld in PROVENANCE_REQUIRED_FIELDS:
            if kr.get(fld) is not None and not (kr.get("fieldSources") or {}).get(fld):
                raise SystemExit(f"{kid}.{fld} filled without fieldSources")
        for url in urls_in(kr.get("sourceName") or ""):
            if is_generic_url(url) or _looks_continuous_unversioned_oem_pdf(url):
                raise SystemExit(f"{kid} sourceName still cites rejected Ford URL: {url}")

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
            if pure_cd_equals_weighted(e, r.get("weightedEnergyConsumptionKWhPerKm")):
                raise SystemExit(
                    f"pure CD equals weighted energy {r['id']}: {e} == "
                    f"{r.get('weightedEnergyConsumptionKWhPerKm')}"
                )

        fs = r.get("fieldSources") or {}
        fd = r.get("fieldSourceDates") or {}
        homolog_year = r.get("dataDerivedFromSameHomologationYear")
        hy = int(homolog_year) if homolog_year is not None else None

        # Filled CS / kWh / range / battery require fieldSources
        for field in PROVENANCE_REQUIRED_FIELDS:
            if r.get(field) is not None and not fs.get(field):
                raise SystemExit(f"filled without fieldSources {r['id']}.{field}")

        if not manifest_covers_filled_fields(r, man):
            raise SystemExit(f"filled calc field without manifest entry {r['id']}")

        # sourceName must not retain generic landings or continuous typenblätter
        for url in urls_in(r.get("sourceName") or ""):
            if is_generic_url(url):
                raise SystemExit(f"generic URL in sourceName {r['id']}: {url}")
            if _looks_continuous_unversioned_oem_pdf(url):
                raise SystemExit(f"continuous OEM PDF in sourceName {r['id']}: {url}")

        for field, cite in fs.items():
            if not cite:
                continue
            date = fd.get(field) or ""
            urls = urls_in(cite) or [cite]
            for url in urls:
                if is_generic_url(url):
                    raise SystemExit(f"generic URL on {r['id']}.{field}: {url}")
                if _looks_continuous_unversioned_oem_pdf(url):
                    raise SystemExit(f"continuous OEM PDF on {r['id']}.{field}: {url}")
            # Reject invented New-Year placeholders when the cite encodes a *different*
            # real doc date, or when a URL/filename year is after the vehicle year.
            # Official January listini (januar_YYYY / gültig ab 01/YYYY / valid as of
            # 01.01.YYYY) that extract to the same YYYY-01-01 are kept.
            if date.endswith("-01-01") and urls_in(cite):
                real = extract_document_date(cite)
                if real and real != date:
                    raise SystemExit(
                        f"invented placeholder date {r['id']}.{field}: {date} vs cite {real}"
                    )
                if real is None and not is_real_january_document_date(cite, date):
                    # No extractable January signal — treat YYYY-01-01 as invented.
                    # (URL-year>MY is also caught by cite_dating_ok below.)
                    path_years = re.findall(r"(?<!\d)(20\d{2})(?!\d)", " ".join(urls_in(cite)))
                    if path_years and date[:4] not in path_years:
                        raise SystemExit(
                            f"invented MY-start date on mismatched-year URL {r['id']}.{field}: "
                            f"date={date} url_years={path_years}"
                        )
            # Non-URL cites (e.g. bare tokens) are only OK when they contain no http URL;
            # dating still required when URLs are present.
            if urls_in(cite):
                if not date:
                    raise SystemExit(f"URL cite without sourceDate {r['id']}.{field}")
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

    if len(inv.get("batch2_candidates") or []) != 40:
        raise SystemExit("batch2 candidates != 40")
    if len(man.get("batch2_ids") or []) != 40:
        raise SystemExit("manifest batch2_ids != 40")

    # Research spot-checks (batch2 fills)
    q5sb = by_id["audi-q5-sportback-phev-50-tfsi-e-2024"]
    if abs(float(q5sb.get("fuelConsumptionLPerKm") or 0) - 0.088) > 1e-9:
        raise SystemExit("Q5 SB 2024 CS expected 0.088")
    if int(q5sb.get("wltpRangeKm") or 0) != 57:
        raise SystemExit("Q5 SB 2024 EAER expected 57")
    if abs(float(q5sb.get("batteryKWh") or 0) - 14.4) > 1e-9:
        raise SystemExit("Q5 SB 2024 battery expected 14.4 net")
    if q5sb.get("energyConsumptionKWhPerKm") is not None:
        raise SystemExit("Q5 SB 2024 pure CD must stay nil")
    bat_cite = (q5sb.get("fieldSources") or {}).get("batteryKWh") or ""
    if "net" not in bat_cite.lower():
        raise SystemExit("Q5 SB 2024 battery cite must label net")
    if "240604" not in bat_cite and "06/04/24" not in bat_cite:
        raise SystemExit("Q5 SB 2024 cite must reference 240604 / 06/04/24")

    x130 = by_id["bmw-x1-phev-xdrive30e-2023"]
    if abs(float(x130.get("batteryKWh") or 0) - 14.2) > 1e-9:
        raise SystemExit("X1 30e 2023 battery expected Netto 14.2")
    if int(x130.get("wltpRangeKm") or 0) != 71:
        raise SystemExit("X1 30e 2023 EAER expected 71")
    if x130.get("fuelConsumptionLPerKm") is not None:
        raise SystemExit("X1 30e 2023 CS must stay nil (weighted-only sheet)")

    at23 = by_id["bmw-serie-2-active-tourer-225e-xdrive-2023"]
    if abs(float(at23.get("batteryKWh") or 0) - 14.2) > 1e-9:
        raise SystemExit("Active Tourer 225e 2023 battery expected 14.2")
    if int(at23.get("wltpRangeKm") or 0) != 78:
        raise SystemExit("Active Tourer 225e 2023 EAER expected 78")

    x3 = by_id["bmw-x3-phev-xdrive30e-2024"]
    if abs(float(x3.get("batteryKWh") or 0) - 19.7) > 1e-9:
        raise SystemExit("X3 30e 2024 battery expected net 19.7")
    if int(x3.get("wltpRangeKm") or 0) != 81:
        raise SystemExit("X3 30e 2024 EAER expected 81")

    # Nil control: Q5 SB 2023 must remain empty (no 2023 eTD / no homolog path)
    q5sb23 = by_id["audi-q5-sportback-phev-50-tfsi-e-2023"]
    if q5sb23.get("batteryKWh") is not None or q5sb23.get("wltpRangeKm") is not None:
        raise SystemExit("Q5 SB 2023 must stay nil without MY2023 OEM sheet")
    if q5sb23.get("fuelConsumptionLPerKm") is not None:
        raise SystemExit("Q5 SB 2023 CS must stay nil")

    # Floor probe still required (shared with batch1 rules)
    if miles_to_km_floor(29.8) != 47:
        raise SystemExit(f"miles_to_km_floor(29.8) want 47 got {miles_to_km_floor(29.8)}")

    assert_battery_convention_matches_seed(man, by_id)

    report = {
        "seedVersion": 84,
        "rows": len(seed),
        "completed": len(man.get("completed") or []),
        "partial": len(man.get("partial") or []),
        "left_nil": len(man.get("left_nil") or []),
        "non_phev_tech_sha": sha,
    }
    print("OK")
    print(json.dumps(report, sort_keys=True))
    return report


def _hashseed_parent() -> None:
    """Run full check under PYTHONHASHSEED 0..5; require identical reports."""
    import os
    import subprocess

    if os.environ.get("PHEV_WAVE2_B2_HASHSEED_CHILD") == "1":
        main()
        return
    digests = []
    reports = []
    for hs in range(6):
        env = os.environ.copy()
        env["PYTHONHASHSEED"] = str(hs)
        env["PHEV_WAVE2_B2_HASHSEED_CHILD"] = "1"
        r = subprocess.run(
            [sys.executable, str(Path(__file__).resolve())],
            cwd=str(REPO),
            env=env,
            capture_output=True,
            text=True,
        )
        if r.returncode != 0:
            raise SystemExit(
                f"HASHSEED={hs} failed:\n{r.stdout}\n{r.stderr}"
            )
        out = (r.stdout or "").strip()
        reports.append(out)
        digests.append(hashlib.sha256(out.encode()).hexdigest())
    if len(set(digests)) != 1:
        raise SystemExit(f"PYTHONHASHSEED drift: {digests}")
    print(reports[0])
    print(f"PYTHONHASHSEED 0..5 identical: {digests[0]}")


if __name__ == "__main__":
    _hashseed_parent()
