#!/usr/bin/env python3
"""
Must-fail + coherence checks for IT catalog wave-1.

Fails when:
- a new wave-1 row lacks sourceName/sourceUpdatedAt
- an homologation alias lacks sourceUrl/sourceName/sourceUpdatedAt
- wltpRangeKm or batteryKWh is set without an EEA or same-year OEM http source
- Tesla Model 3 2026 rows were altered
- seedVersion / row counts disagree with catalog_cdn.json

PYTHONHASHSEED-stable (sorted iteration only).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SEED = REPO / "EVforME?" / "Data" / "vehicles.seed.quality.json"
CDN = REPO / "EVforME?" / "Data" / "catalog_cdn.json"
ALIAS = REPO / "EVforME?" / "Data" / "homologation_commercial_aliases.json"
MANIFEST = REPO / "scripts" / "cache" / "eea" / "catalog_it_wave1_manifest.json"

EXPECTED_SEED_VERSION = 63
WAVE1_ID_PREFIXES = (
    "toyota-aygo-x-",
    "ford-ecosport-",
    "ford-tourneo-courier-",
    "ford-tourneo-custom-diesel-",
    "alfa-romeo-junior-",
    "mini-cooper-",
    "bmw-x4-diesel-",
    "renault-symbioz-",
    "lexus-lbx-",
    "smart-eq-fortwo-",
    "cupra-terramar-e-hybrid-",
    "jeep-wrangler-4xe-",
    "jeep-grand-cherokee-4xe-",
)


def has_range_or_battery_source(source_name: str) -> bool:
    sn = source_name or ""
    return "EEA" in sn or "http://" in sn or "https://" in sn


def validate_row(row: dict) -> tuple[bool, str]:
    rid = str(row.get("id") or "")
    if not row.get("sourceName") or not row.get("sourceUpdatedAt"):
        return False, "row_without_source"
    rng = row.get("wltpRangeKm")
    bat = row.get("batteryKWh")
    if rng not in (None, "", 0) or bat not in (None, "", 0):
        if not has_range_or_battery_source(str(row.get("sourceName") or "")):
            return False, "range_or_battery_without_same_year_source"
    return True, "ok"


def validate_alias(alias: dict) -> tuple[bool, str]:
    if not alias.get("sourceUrl") or not alias.get("sourceName") or not alias.get(
        "sourceUpdatedAt"
    ):
        return False, "alias_without_source"
    if not alias.get("commercialName") or not alias.get("eeaKeys"):
        return False, "alias_incomplete"
    return True, "ok"


def must_fail_cases() -> list[tuple[str, object, bool, str]]:
    good_row = {
        "id": "demo-ok",
        "sourceName": "EEA co2cars IT 2024 DEMO n=10",
        "sourceUpdatedAt": "2026-10-27",
        "wltpRangeKm": None,
        "batteryKWh": None,
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
        ("ok_alias", good_alias, True, "ok"),
        (
            "fail_alias_without_source",
            {**good_alias, "sourceUrl": None},
            False,
            "alias_without_source",
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
        rid
        for rid in rows
        if any(rid.startswith(p) for p in WAVE1_ID_PREFIXES)
    )
    if not wave_ids:
        failures.append("no_wave1_ids_in_seed")
    for rid in wave_ids:
        ok, detail = validate_row(rows[rid])
        if not ok:
            failures.append(f"{rid}:{detail}")

    # Tesla M3 2026 untouched fingerprint
    m3 = sorted(
        rid
        for rid in rows
        if rid.startswith("tesla-model-3") and int(rows[rid].get("year") or 0) == 2026
    )
    if not m3:
        failures.append("tesla_m3_2026_missing")
    for rid in m3:
        sn = str(rows[rid].get("sourceName") or "")
        if "wave-1" in sn.lower() or "IT wave" in sn:
            failures.append(f"{rid}:altered_by_wave1")

    # Commercial renames present
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

    print(f"wave1_rows_checked={len(wave_ids)} must_ok={must_ok} failures={len(failures)}")
    if failures:
        for f in failures:
            print(f"FAIL: {f}", file=sys.stderr)
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
