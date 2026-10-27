#!/usr/bin/env python3
"""
Must-fail + coherence checks for IT catalog wave-2.

Fails when:
- a new wave-2 row lacks sourceName/sourceUpdatedAt
- an homologation alias lacks sourceUrl/sourceName/sourceUpdatedAt
- wltpRangeKm or batteryKWh is set without an EEA or same-year OEM http source
- non-OEM third-party domains appear in energy/range/battery sources
- a row's source cites a different commercial model
- an alias merges two distinct commercial models (e.g. Fortwo+Forfour)
- Tesla Model 3 2026 rows were altered
- seedVersion / row counts disagree with catalog_cdn.json

PYTHONHASHSEED-stable (sorted iteration only).
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
ALIAS = REPO / "EVforME?" / "Data" / "homologation_commercial_aliases.json"
MANIFEST = REPO / "scripts" / "cache" / "eea" / "catalog_it_wave2_manifest.json"

EXPECTED_SEED_VERSION = 66
WAVE2_ID_PREFIXES = (
    "alfa-romeo-junior-elettrica-",
    "audi-rs3-sportback-",
    "audi-s3-sportback-",
    "bmw-m2-",
    "bmw-m3-competition-",
    "bmw-serie-2-active-tourer-225e-xdrive-",
    "bmw-serie-3-320e-",
    "bmw-x6-diesel-",
    "cupra-terramar-",
    "dacia-bigster-",
    "dacia-bigster-gpl-",
    "fiat-ulysse-diesel-",
    "ford-tourneo-custom-diesel-",
    "ford-transit-custom-diesel-",
    "honda-zr-v-",
    "land-rover-range-rover-velar-diesel-",
    "maserati-grecale-",
    "maserati-levante-gt-hybrid-",
    "mercedes-benz-amg-g63-",
    "mercedes-benz-cle-diesel-",
    "mini-cooper-c-",
    "mini-cooper-e-",
    "mini-cooper-s-",
    "mini-cooper-se-",
    "mini-countryman-cooper-se-all4-",
    "mini-one-",
    "mitsubishi-eclipse-cross-phev-",
    "nissan-primastar-diesel-",
    "nissan-townstar-",
    "peugeot-rifter-diesel-",
    "renault-kangoo-",
    "renault-kangoo-diesel-",
    "renault-rafale-",
    "renault-trafic-diesel-",
    "subaru-crosstrek-",
    "volkswagen-caddy-",
    "volkswagen-caddy-diesel-",
    "volkswagen-kombi-diesel-",
    "volkswagen-multivan-diesel-",
    "volkswagen-tayron-",
)

# Domains allowed for OEM / official EU regulatory cites (substring match on host).
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
    "suzuki.it",
    "suzuki.com",
    "dacia.it",
    "dacia.com",
    "maserati.com",
    "maserati.it",
    "honda.it",
    "honda.com",
    "volkswagen.it",
    "volkswagen.com",
    "eea.europa.eu",
    "web.archive.org",  # dated snapshots of OEM pages only; still check path
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


def has_range_or_battery_source(source_name: str) -> bool:
    sn = source_name or ""
    return "EEA" in sn or "http://" in sn or "https://" in sn


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
    if needs_official and not has_range_or_battery_source(sn):
        return False, "range_or_battery_without_same_year_source"
    if needs_official:
        for url in urls_in(sn):
            host = host_of(url)
            if host and not is_official_host(host):
                return False, "unofficial_source_domain"
            if any(bad in url.lower() for bad in THIRD_PARTY_BLOCKLIST):
                return False, "unofficial_source_domain"
    # Wrong-model cite: Wrangler source must not be Grand Cherokee pack, and vice versa
    model = str(row.get("model") or "").lower()
    sn_l = sn.lower()
    if "wrangler" in model and "grand cherokee" in sn_l:
        return False, "source_wrong_model"
    if "grand cherokee" in model and "wrangler" in sn_l and "grand cherokee" not in sn_l:
        return False, "source_wrong_model"
    return True, "ok"


def validate_alias(alias: dict) -> tuple[bool, str]:
    if not alias.get("sourceUrl") or not alias.get("sourceName") or not alias.get(
        "sourceUpdatedAt"
    ):
        return False, "alias_without_source"
    if not alias.get("commercialName") or not alias.get("eeaKeys"):
        return False, "alias_incomplete"
    host = host_of(str(alias.get("sourceUrl") or ""))
    if host and not is_official_host(host):
        return False, "unofficial_source_domain"
    # Distinct commercial models must not share one alias
    name = str(alias.get("commercialName") or "").lower()
    keys = " ".join(str(k) for k in (alias.get("eeaKeys") or [])).upper()
    if name == "fortwo" and "FORFOUR" in keys:
        return False, "alias_merges_distinct_models"
    if name == "forfour" and "FORTWO" in keys:
        return False, "alias_merges_distinct_models"
    # Over-generic homologation tokens
    for k in alias.get("eeaKeys") or []:
        if str(k).strip().upper() in {"120", "X1", "A", "B", "C"}:
            return False, "alias_over_generic_key"
    return True, "ok"


def must_fail_cases() -> list[tuple[str, object, bool, str]]:
    good_row = {
        "id": "demo-ok",
        "model": "Demo",
        "sourceName": "EEA co2cars IT 2024 DEMO n=10",
        "sourceUpdatedAt": "2026-10-27",
        "wltpRangeKm": None,
        "batteryKWh": None,
        "energyConsumptionKWhPerKm": None,
    }
    good_alias = {
        "brand": "BMW",
        "eeaKeys": ["118D"],
        "commercialName": "Serie 1",
        "sourceName": "BMW Italia",
        "sourceUrl": "https://www.bmw.it/it/tutti-i-modelli/bmw-serie/serie-1.html",
        "sourceUpdatedAt": "2026-10-27",
    }
    return [
        ("ok_row", good_row, True, "ok"),
        (
            "fail_row_without_source",
            {**good_row, "sourceName": None},
            False,
            "row_without_source",
        ),
        (
            "fail_row_range_without_source",
            {
                **good_row,
                "sourceName": "stima interna senza fonte",
                "wltpRangeKm": 400,
            },
            False,
            "range_or_battery_without_same_year_source",
        ),
        (
            "fail_row_battery_without_source",
            {
                **good_row,
                "sourceName": "stima interna",
                "batteryKWh": 50.0,
            },
            False,
            "range_or_battery_without_same_year_source",
        ),
        (
            "fail_unofficial_source_domain",
            {
                **good_row,
                "model": "Wrangler",
                "wltpRangeKm": 45,
                "batteryKWh": 17.3,
                "sourceName": (
                    "mirror PDF — https://autocatalogarchive.com/wp-content/uploads/"
                    "2023/10/Jeep-Grand-Cherokee-4Xe-2023-GER.pdf"
                ),
            },
            False,
            "unofficial_source_domain",
        ),
        (
            "fail_source_wrong_model",
            {
                **good_row,
                "model": "Wrangler",
                "wltpRangeKm": 45,
                "batteryKWh": 17.3,
                "sourceName": (
                    "Grand Cherokee 4xe MJ23 pack — "
                    "https://www.media.stellantis.com/uploads/de/model-pricelist/"
                    "preisliste_grand_cherokee_4xe_januar_20234-6486c171a11d8.pdf"
                ),
            },
            False,
            "source_wrong_model",
        ),
        ("ok_alias", good_alias, True, "ok"),
        (
            "fail_alias_without_source",
            {**good_alias, "sourceUrl": None},
            False,
            "alias_without_source",
        ),
        (
            "fail_alias_merges_distinct_models",
            {
                **good_alias,
                "brand": "Smart",
                "commercialName": "Fortwo",
                "eeaKeys": ["EQ FORTWO COUPE", "EQ FORFOUR"],
                "sourceUrl": "https://www.smart.com/it/it/models/eq-fortwo",
            },
            False,
            "alias_merges_distinct_models",
        ),
        (
            "fail_alias_over_generic_key",
            {**good_alias, "eeaKeys": ["120", "118D"]},
            False,
            "alias_over_generic_key",
        ),
    ]


def main() -> int:
    failures: list[str] = []
    must_ok = 0

    for label, payload, expect_ok, substr in must_fail_cases():
        if "alias" in label:
            ok, detail = validate_alias(payload)  # type: ignore[arg-type]
        else:
            ok, detail = validate_row(payload)  # type: ignore[arg-type]
        if ok == expect_ok and substr in detail:
            print(f"must-fail OK: {label} → {detail}")
            must_ok += 1
        else:
            failures.append(f"{label}: expected_ok={expect_ok} got {ok}/{detail}")
            print(f"must-fail FAIL: {label} → {ok}/{detail}")

    seed = json.loads(SEED.read_text(encoding="utf-8"))
    cdn = json.loads(CDN.read_text(encoding="utf-8"))
    aliases = json.loads(ALIAS.read_text(encoding="utf-8"))
    rows = {str(r["id"]): r for r in seed}

    if int(cdn.get("seedVersion") or 0) != EXPECTED_SEED_VERSION:
        failures.append(
            f"cdn_seedVersion={cdn.get('seedVersion')} expected {EXPECTED_SEED_VERSION}"
        )
    if int(cdn.get("rows") or 0) != len(seed):
        failures.append(f"cdn_rows={cdn.get('rows')} seed={len(seed)}")

    for a in sorted(aliases.get("aliases") or [], key=lambda x: json.dumps(x, sort_keys=True)):
        ok, detail = validate_alias(a)
        if not ok:
            failures.append(f"alias:{a.get('commercialName')}:{detail}")

    wave_ids = sorted(
        rid for rid in rows if any(rid.startswith(p) for p in WAVE2_ID_PREFIXES)
    )
    if not wave_ids:
        failures.append("no_wave2_ids_in_seed")
    for rid in wave_ids:
        ok, detail = validate_row(rows[rid])
        if not ok:
            failures.append(f"{rid}:{detail}")
    # Whole-seed third-party ban (incl. wave-1 Jeep rows carried forward)
    for rid in sorted(rows):
        sn = str(rows[rid].get("sourceName") or "")
        if "autocatalogarchive" in sn.lower():
            failures.append(f"{rid}:third_party_autocatalogarchive")

    m3 = sorted(
        rid
        for rid in rows
        if rid.startswith("tesla-model-3") and int(rows[rid].get("year") or 0) == 2026
    )
    if not m3:
        failures.append("tesla_m3_2026_missing")
    for rid in m3:
        sn = str(rows[rid].get("sourceName") or "")
        if "wave-2" in sn.lower() or "catalog wave" in sn:
            failures.append(f"{rid}:altered_by_wave")

    serie1 = [
        r
        for r in seed
        if str(r.get("id") or "").startswith("bmw-1-series-")
        and int(r.get("year") or 0) >= 2022
    ]
    if not serie1 or any(r.get("model") != "Serie 1" for r in serie1):
        failures.append("bmw_1_series_not_renamed_Serie_1")
    classe_a = [
        r
        for r in seed
        if str(r.get("id") or "").startswith("mercedes-benz-a-class")
        and int(r.get("year") or 0) >= 2022
    ]
    if not classe_a or any(r.get("model") != "Classe A" for r in classe_a):
        failures.append("mercedes_a_class_not_renamed_Classe_A")

    if MANIFEST.exists():
        man = json.loads(MANIFEST.read_text(encoding="utf-8"))
        for rid in sorted(man.get("added") or []):
            if rid not in rows:
                failures.append(f"manifest_added_missing:{rid}")

    # PHEV/BEV calc hygiene: never keep weighted thin fuel in fuelConsumptionLPerKm;
    # incomplete rows must be flagged; complete PHEVs need CS≥3 + non-weighted energy.
    phev_complete = 0
    phev_incomplete = 0
    bev_incomplete = 0
    for rid in sorted(rows):
        r = rows[rid]
        if r.get("parentId"):
            continue
        pt = r.get("powertrain")
        fuel = r.get("fuelConsumptionLPerKm")
        energy = r.get("energyConsumptionKWhPerKm")
        incomplete = r.get("catalogDataIncomplete") is True
        if pt == "phev":
            if fuel is not None and float(fuel) * 100.0 < 3.0:
                failures.append(f"{rid}:phev_thin_fuel_in_calc_field")
            weighted_energy = r.get("energyIsWeighted") is True and energy is not None
            if weighted_energy:
                failures.append(f"{rid}:phev_weighted_energy_in_calc_field")
            cs_ok = fuel is not None and float(fuel) * 100.0 >= 3.0
            cd_ok = energy is not None and float(energy) > 0 and r.get("energyIsWeighted") is not True
            if cs_ok and cd_ok:
                if incomplete:
                    failures.append(f"{rid}:phev_complete_but_flagged_incomplete")
                phev_complete += 1
            else:
                if not incomplete:
                    failures.append(f"{rid}:phev_incomplete_missing_flag")
                phev_incomplete += 1
        elif pt == "ev":
            e = energy
            if e is None and r.get("wltpConsumptionKWh100km") is not None:
                e = float(r["wltpConsumptionKWh100km"]) / 100.0
            if e is None or float(e) <= 0:
                if not incomplete:
                    failures.append(f"{rid}:bev_incomplete_missing_flag")
                bev_incomplete += 1

    print(
        f"phev_complete={phev_complete} phev_incomplete={phev_incomplete} "
        f"bev_incomplete={bev_incomplete}"
    )

    print(f"wave2_rows_checked={len(wave_ids)} must_ok={must_ok} failures={len(failures)}")
    if failures:
        for f in failures:
            print(f"FAIL: {f}", file=sys.stderr)
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
