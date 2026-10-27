#!/usr/bin/env python3
"""
Must-fail + coherence checks for IT PHEV catalog wave (feat/catalog-phev-it).

Fails when:
- source cites a different model year than the row
- unofficial / third-party domain for range/battery/energy
- weighted fuel or weighted energy parked in calc fields
- catalogDataIncomplete missing when CS or CD missing
- Tesla Model 3 2026 altered / removals vs baseline
- seedVersion / row counts disagree with catalog_cdn.json
- PYTHONHASHSEED-stable (sorted iteration only)
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

REPO = Path(__file__).resolve().parents[1]
SEED = REPO / "EVforME?" / "Data" / "vehicles.seed.quality.json"
CDN = REPO / "EVforME?" / "Data" / "catalog_cdn.json"
GAPS = REPO / "scripts" / "cache" / "eea" / "catalog_phev_it_gaps.json"
MANIFEST = REPO / "scripts" / "cache" / "eea" / "catalog_phev_it_manifest.json"

EXPECTED_SEED_VERSION = 66

OFFICIAL_HOST_SUFFIXES = (
    "media.stellantis.com",
    "stellantis.com",
    "jeep.de",
    "jeep.it",
    "jeep.com",
    "press.bmwgroup.com",
    "bmw.it",
    "bmwgroup.com",
    "cupraofficial.com",
    "cupraofficial.it",
    "mitsubishi-motors.nl",
    "mitsubishi-motors.com",
    "smart.com",
    "mercedes-benz.it",
    "mercedes-benz.de",
    "toyota.it",
    "toyota-europe.com",
    "ford.it",
    "ford.eu",
    "renault.it",
    "renault.com",
    "lexus.eu",
    "lexus.it",
    "mini.it",
    "mini.com",
    "alfaromeo.it",
    "alfaromeo.com",
    "audi.it",
    "audi.com",
    "subaru.it",
    "subaru.com",
    "nissan.it",
    "nissan.com",
    "landrover.it",
    "landrover.com",
    "peugeot.it",
    "peugeot.com",
    "fiat.it",
    "fiat.com",
    "volkswagen.it",
    "volkswagen.com",
    "newsroom.volkswagen.com",
    "volvo.com",
    "volvocars.com",
    "hyundai.com",
    "hyundai.it",
    "kia.com",
    "kia.it",
    "porsche.com",
    "mg.co.uk",
    "mgmotor.eu",
    "byd.com",
    "dsautomobiles.com",
    "dsautomobiles.it",
    "opel.it",
    "opel.com",
    "citroen.it",
    "citroen.com",
    "mazda.com",
    "mazda.it",
    "mazda.eu",
    "media-assets.mazda.eu",
    "volkswagen-newsroom.com",
    "eea.europa.eu",
    "fueleconomy.gov",
    "web.archive.org",
)

THIRD_PARTY_BLOCKLIST = (
    "autocatalogarchive.com",
    "wikipedia.org",
    "ev-database.org",
    "ev-database.",
    "autocar.co.uk",
    "insideevs.com",
    "electrek.co",
    "carwow.",
    "motor1.com",
    "quattroruote.it",
)


def urls_in(text: str) -> list[str]:
    return re.findall(r"https?://[^\s\]\)\"'<>]+", text or "")


def host_of(url: str) -> str:
    try:
        return (urlparse(url).hostname or "").lower()
    except Exception:
        return ""


def is_official_host(host: str) -> bool:
    h = host.lower().lstrip(".")
    if any(bad in h for bad in THIRD_PARTY_BLOCKLIST):
        return False
    return any(h == s or h.endswith("." + s) for s in OFFICIAL_HOST_SUFFIXES)


def year_mismatch(row: dict) -> bool:
    """True if sourceName claims OEM data from a clearly different model year."""
    year = int(row.get("year") or 0)
    sn = str(row.get("sourceName") or "")
    if not year or not sn:
        return False
    # Mentions of rejected wrong-MY pages ("MJ25 … not valid") are documentation, not claims.
    sn_claim = re.sub(
        r"(?i)(not valid|non valid[oa]|not attached|not found|living [^;]*pages)[^.\;]*",
        " ",
        sn,
    )
    # Only enforce MY/MJ when the row actually carries OEM numeric fields from that cite.
    has_oem_fields = any(
        row.get(k) not in (None, "", 0)
        for k in ("wltpRangeKm", "batteryKWh", "energyConsumptionKWhPerKm", "fuelConsumptionLPerKm")
    )
    if has_oem_fields:
        my = re.findall(r"\b(?:MY|MJ)\s*'?(\d{2})\b", sn_claim, flags=re.I)
        for tok in my:
            cited = 2000 + int(tok)
            if cited not in (year, year - 1, year + 1) and abs(cited - year) >= 2:
                return True
    # "EEA co2cars IT YYYY" must match row year when present (first occurrence).
    m = re.search(r"EEA co2cars IT (\d{4})", sn)
    if m and int(m.group(1)) != year:
        return True
    return False


def validate_row(row: dict) -> tuple[bool, str]:
    if not row.get("sourceName") or not row.get("sourceUpdatedAt"):
        return False, "row_without_source"
    sn = str(row.get("sourceName") or "")
    rng = row.get("wltpRangeKm")
    bat = row.get("batteryKWh")
    energy = row.get("energyConsumptionKWhPerKm")
    needs_official = (
        rng not in (None, "", 0)
        or bat not in (None, "", 0)
        or energy not in (None, "", 0)
    )
    if needs_official:
        has_cite = "EEA" in sn or "http://" in sn or "https://" in sn or "EPA" in sn.upper()
        if not has_cite:
            return False, "range_or_battery_without_same_year_source"
        for url in urls_in(sn):
            host = host_of(url)
            if host and not is_official_host(host):
                return False, "unofficial_source_domain"
            if any(bad in url.lower() for bad in THIRD_PARTY_BLOCKLIST):
                return False, "unofficial_source_domain"
    if year_mismatch(row):
        return False, "source_wrong_year"
    # Weighted must never sit in calc fields
    fuel = row.get("fuelConsumptionLPerKm")
    if fuel is not None and float(fuel) * 100.0 < 3.0 and row.get("powertrain") == "phev":
        return False, "weighted_fuel_in_calc_field"
    if row.get("energyIsWeighted") is True and energy is not None:
        return False, "weighted_energy_in_calc_field"
    return True, "ok"


def must_fail_cases() -> list[tuple[str, object, bool, str]]:
    good = {
        "id": "demo-ok",
        "model": "Demo",
        "year": 2023,
        "powertrain": "phev",
        "sourceName": "EEA co2cars IT 2023 DEMO PETROL/ELECTRIC n=10; OEM same-MY not attached",
        "sourceUpdatedAt": "2026-10-27",
        "wltpRangeKm": None,
        "batteryKWh": None,
        "energyConsumptionKWhPerKm": None,
        "fuelConsumptionLPerKm": None,
        "energyIsWeighted": True,
    }
    return [
        ("ok_row", good, True, "ok"),
        (
            "fail_source_wrong_year",
            {
                **good,
                "year": 2022,
                "batteryKWh": 11.4,
                "sourceName": (
                    "OEM MY24 tarif 2024 only — "
                    "https://www.media.stellantis.com/uploads/fr/attachment/7783/x.pdf; "
                    "EEA co2cars IT 2024 COMPASS"
                ),
            },
            False,
            "source_wrong_year",
        ),
        (
            "fail_unofficial_source_domain",
            {
                **good,
                "wltpRangeKm": 50,
                "batteryKWh": 11.4,
                "sourceName": (
                    "mirror — https://autocatalogarchive.com/wp-content/uploads/"
                    "2023/10/Jeep-Compass-4xe.pdf"
                ),
            },
            False,
            "unofficial_source_domain",
        ),
        (
            "fail_weighted_fuel_in_calc",
            {
                **good,
                "fuelConsumptionLPerKm": 0.018,  # 1.8 L/100 weighted blend
            },
            False,
            "weighted_fuel_in_calc_field",
        ),
        (
            "fail_weighted_energy_in_calc",
            {
                **good,
                "energyConsumptionKWhPerKm": 0.16,
                "energyIsWeighted": True,
            },
            False,
            "weighted_energy_in_calc_field",
        ),
    ]


def _fold(s: str) -> str:
    return (
        (s or "")
        .upper()
        .replace("É", "E")
        .replace("È", "E")
        .replace("Ë", "E")
        .replace("Ê", "E")
        .replace("Ç", "C")
        .replace("_", " ")
    )


def soft_match_phev(seed: list[dict], brand: str, model: str, year: int) -> bool:
    """Strict-ish: PHEV parent only, brand+model tokens, same year."""
    bn, mn = _fold(brand), _fold(model)
    raw_tokens = [t for t in re.split(r"[^A-Z0-9]+", mn) if t]
    # Keep model codes (A3, Q3, XC40, NX450H, DS7) intact; split only long glue.
    tokens: list[str] = []
    for t in raw_tokens:
        parts = re.findall(r"[A-Z]+\d+[A-Z]*|\d+[A-Z]+|[A-Z]{2,}|\d{2,}|[A-Z]|\d+", t)
        tokens.extend(parts)
    drop = {
        "TOYOTA",
        "BMW",
        "AUDI",
        "MAZDA",
        "BYD",
        "MG",
        "LEXUS",
        "HYUNDAI",
        "MERCEDES",
        "BENZ",
        "PLUG",
        "IN",
        "HYBRID",
        "PETROL",
        "ELECTRIC",
        "CROSSBACK",
        "IX35",
        "UNLIMITED",
        "TRON",
        "TFSIE",
        "TFSI",
        "E",
    }
    tokens = [t for t in tokens if t not in drop]
    sig = [t for t in tokens if len(t) >= 2 or (t.isdigit() and t in {"7"})]
    for r in seed:
        if r.get("parentId") or r.get("powertrain") != "phev":
            continue
        if int(r.get("year") or 0) != year:
            continue
        rb = _fold(str(r.get("brand") or ""))
        rm = _fold(f"{r.get('model') or ''} {r.get('trim') or ''}")
        # Also match id slug for accent/punctuation variants
        rid = _fold(str(r.get("id") or "")).replace("-", " ")
        brand_ok = (
            bn.split()[0] in rb
            or bn in rb
            or ("LAND" in bn and ("LAND" in rb or "ROVER" in rb))
            or ("MERCEDES" in bn and "MERCEDES" in rb)
            or ("CITROEN" in bn and "CITROEN" in rb)
        )
        if not brand_ok:
            continue
        if not sig:
            return True
        primary = next((t for t in sig if not t.isdigit()), sig[0])
        aliases = {
            "EHS": ("HS", "EHS"),
            "NX450H": ("NX", "450", "NX450H"),
            "DS7": ("7", "DS7"),
            "A3": ("A3",),
            "Q3": ("Q3",),
            "Q5": ("Q5",),
            "C5": ("C5", "AIRCROSS"),
        }
        alts = aliases.get(primary, (primary,))
        hay = f"{rm} {rid}"
        if any(a in hay for a in alts):
            # Disambiguate A3 40 vs A3 45 when both years exist
            if "40" in sig and "40" not in hay and "45" in hay:
                continue
            if "45" in sig and primary == "A3" and "45" not in hay and "40" in hay:
                continue
            # Q3 Sportback vs Q3: EEA "SPORTBACK" must land on Sportback row
            if "SPORTBACK" in mn and "SPORTBACK" not in hay:
                continue
            if "SPORTBACK" not in mn and primary == "Q3" and "SPORTBACK" in hay and "Q3 " + "SPORTBACK" in mn:
                continue
            if primary == "Q3" and "SPORTBACK" not in mn and "SPORTBACK" in _fold(str(r.get("model") or "")):
                # plain Q3 E-TRON should not match Q3 Sportback only — allow if a plain Q3 also exists; keep searching
                if "SPORTBACK" in _fold(str(r.get("model") or "")):
                    continue
            return True
    return False


def main() -> int:
    failures: list[str] = []
    must_ok = 0

    for label, payload, expect_ok, substr in must_fail_cases():
        ok, detail = validate_row(payload)  # type: ignore[arg-type]
        if ok == expect_ok and substr in detail:
            print(f"must-fail OK: {label} → {detail}")
            must_ok += 1
        else:
            failures.append(f"{label}: expected_ok={expect_ok} got {ok}/{detail}")
            print(f"must-fail FAIL: {label} → {ok}/{detail}")

    seed = json.loads(SEED.read_text(encoding="utf-8"))
    cdn = json.loads(CDN.read_text(encoding="utf-8"))
    rows = {str(r["id"]): r for r in seed}

    if int(cdn.get("seedVersion") or 0) != EXPECTED_SEED_VERSION:
        failures.append(
            f"cdn_seedVersion={cdn.get('seedVersion')} expected {EXPECTED_SEED_VERSION}"
        )
    if int(cdn.get("rows") or 0) != len(seed):
        failures.append(f"cdn_rows={cdn.get('rows')} seed={len(seed)}")

    # No removals: baseline EPA + curated EU PHEVs from before this wave must remain
    required_ids = [
        "audi-a3-e-tron-ultra-phev-2016",
        "bmw-330e-phev-2024",
        "bmw-serie-2-active-tourer-225e-xdrive-2022",
        "jeep-wrangler-4xe-2022",
        "mazda-cx-60-phev-2024",
        "volkswagen-golf-gte-phev-2024",
        "mini-countryman-cooper-se-all4-2023",
        "mitsubishi-eclipse-cross-phev-2023",
    ]
    for rid in required_ids:
        if rid not in rows:
            failures.append(f"removal_forbidden:{rid}")

    m3 = sorted(
        rid
        for rid in rows
        if rid.startswith("tesla-model-3") and int(rows[rid].get("year") or 0) == 2026
    )
    if not m3:
        failures.append("tesla_m3_2026_missing")

    phev_complete = 0
    phev_incomplete = 0
    non_eea_sources: list[tuple[str, str, int]] = []

    for rid in sorted(rows):
        r = rows[rid]
        if r.get("parentId"):
            continue
        if r.get("powertrain") != "phev":
            continue
        ok, detail = validate_row(r)
        if not ok:
            failures.append(f"{rid}:{detail}")

        fuel = r.get("fuelConsumptionLPerKm")
        energy = r.get("energyConsumptionKWhPerKm")
        incomplete = r.get("catalogDataIncomplete") is True
        cs_ok = fuel is not None and float(fuel) * 100.0 >= 3.0
        cd_ok = (
            energy is not None
            and float(energy) > 0
            and r.get("energyIsWeighted") is not True
        )
        if cs_ok and cd_ok:
            if incomplete:
                failures.append(f"{rid}:phev_complete_but_flagged_incomplete")
            phev_complete += 1
        else:
            if not incomplete:
                failures.append(f"{rid}:phev_incomplete_missing_flag")
            phev_incomplete += 1

        sn = str(r.get("sourceName") or "")
        for url in urls_in(sn):
            host = host_of(url)
            if host and "eea.europa" not in host and "fueleconomy" not in host:
                non_eea_sources.append((host, rid, int(r.get("year") or 0)))

    # Coverage: every gaps missing row must map to a seed PHEV (manifest id_to_eea or soft match)
    still_missing: list[str] = []
    covered_eea: set[str] = set()
    man: dict = {}
    if MANIFEST.exists():
        man = json.loads(MANIFEST.read_text(encoding="utf-8"))
        covered_eea = set(man.get("id_to_eea") or {}.values())
        for rid in sorted(man.get("added") or []):
            if rid not in rows:
                failures.append(f"manifest_added_missing:{rid}")
            elif not rows[rid].get("catalogDataIncomplete"):
                fuel = rows[rid].get("fuelConsumptionLPerKm")
                energy = rows[rid].get("energyConsumptionKWhPerKm")
                cs_ok = fuel is not None and float(fuel) * 100.0 >= 3.0
                cd_ok = (
                    energy is not None
                    and float(energy) > 0
                    and rows[rid].get("energyIsWeighted") is not True
                )
                if not (cs_ok and cd_ok):
                    failures.append(f"manifest_added_not_incomplete:{rid}")

    if GAPS.exists():
        gaps = json.loads(GAPS.read_text(encoding="utf-8"))
        for m in sorted(
            gaps.get("missing") or [],
            key=lambda x: (x["brand"], x["model"], x["year"]),
        ):
            key = f"{m['brand']}|{m['model']}|{m['year']}"
            if key in covered_eea:
                continue
            if soft_match_phev(seed, m["brand"], m["model"], m["year"]):
                continue
            still_missing.append(key)

    if still_missing:
        for s in still_missing[:30]:
            failures.append(f"gap_uncovered:{s}")
        if len(still_missing) > 30:
            failures.append(f"gap_uncovered_more:{len(still_missing) - 30}")

    # Dedupe non-EEA hosts for report
    hosts = sorted({(h, y) for h, _rid, y in non_eea_sources})
    print(
        f"phev_complete={phev_complete} phev_incomplete={phev_incomplete} "
        f"must_ok={must_ok} non_eea_hosts={hosts}"
    )
    print(f"still_missing_gaps={len(still_missing)} failures={len(failures)}")
    if failures:
        for f in failures:
            print(f"FAIL: {f}", file=sys.stderr)
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
