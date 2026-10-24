#!/usr/bin/env python3
"""
Fail if EEA IT Status F+P (or 2022 diesel/DIESEL casing) are still summed into n,
or if any EEA-labeled seed row cites an n that does not match the Status-F
cell (sum of F across Ft casing; P only if no F) for the same variant / fuel / year.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import fill_catalog_fuels_from_eea as eea
import fix_catalog_truth as truth
import refresh_eea_status_f_caches as refresh

# (cache file, Cn, year, ft_norm, expect_n_after_F, bad_summed_or_P)
CASES = [
    ("IT_MERCEDES-BENZ_fuels.json", "C 220 D", 2022, "DIESEL", 1218.0, 2436.0),
    ("IT_TOYOTA_fuels.json", "TOYOTA LAND CRUISER (150 SERIES)", 2022, "DIESEL", 264.0, 528.0),
    ("IT_MERCEDES-BENZ_fuels.json", "C 200 D", 2024, "DIESEL", 845.0, 1690.0),
    ("IT_RENAULT_fuels.json", "SCENIC E-TECH ELECTRIC", 2024, "ELECTRIC", 449.0, 898.0),
    ("IT_DS_fuels.json", "DS7", 2024, "DIESEL", 2927.0, 5854.0),
    ("IT_VOLKSWAGEN_fuels.json", "TOUAREG", 2024, "DIESEL", 317.0, 634.0),
    ("IT_ALFA_ROMEO_fuels.json", "STELVIO", 2023, "DIESEL", 6120.0, 12240.0),
    ("IT_KIA_fuels.json", "CEED", 2019, "PETROL", 1298.0, 1788.0),
    # F and P on different Ft casing — must take F (or sum of F), never larger P
    ("IT_KIA_fuels.json", "NIRO", 2022, "PETROL", 2239.0, 2432.0),
    ("IT_KIA_fuels.json", "SPORTAGE", 2022, "PETROL", 6597.0, 7062.0),
    ("IT_KIA_fuels.json", "SORENTO", 2022, "PETROL", 174.0, 251.0),
    ("IT_KIA_fuels.json", "CEED", 2022, "PETROL", 55.0, 60.0),
    ("IT_LAND_ROVER_fuels.json", "RANGE ROVER SPORT", 2022, "DIESEL", 738.0, 739.0),
    ("IT_RENAULT_fuels.json", "CAPTUR", 2018, "PETROL", 8400.0, 8399.0),
    ("IT_RENAULT_fuels.json", "CAPTUR", 2018, "DIESEL", 20696.0, 20694.0),
    ("IT_RENAULT_fuels.json", "CLIO", 2018, "PETROL", 15672.0, 15671.0),
    ("IT_RENAULT_fuels.json", "MEGANE", 2018, "DIESEL", 8605.0, 8603.0),
    ("IT_RENAULT_fuels.json", "SCENIC", 2018, "DIESEL", 6753.0, 6751.0),
]

N_PAT = re.compile(r"\bn=(\d+)\b")
EEA_LABEL_PAT = re.compile(r"^EEA\b", re.I)

SEED_N_CASES = [
    ("alfa-romeo-stelvio-diesel-2023", 6120),
    ("kia-ceed-2019", 1298),
    ("kia-niro-2022", 2239),
    ("kia-sportage-2022", 6597),
    ("kia-sorento-2022", 174),
    ("kia-ceed-2022", 55),
    ("land-rover-range-rover-sport-2022", 738),
    ("land-rover-range-rover-sport-diesel-2022", 738),
    ("renault-captur-2018", 8400),
    ("renault-captur-diesel-2018", 20696),
    ("renault-clio-2018", 15672),
    ("renault-megane-diesel-2018", 8605),
    ("renault-scenic-diesel-2018", 6753),
    ("bmw-3-series-2023", 4073),
    ("bmw-3-series-2021", 3716),
    ("bmw-3-series-2019", 5003),
    ("bmw-3-series-2020", 4905),
    ("bmw-3-series-2022", 2767),
    ("bmw-5-series-2019", 3516),
    ("bmw-5-series-2020", 1848),
    ("bmw-5-series-2021", 1860),
    ("bmw-5-series-2022", 1956),
    ("bmw-x3-2020", 3149),
    ("bmw-x3-2021", 3485),
    ("bmw-1-series-2022", 2002),
    ("hyundai-i10-2021", 11699),
    ("hyundai-i20-2021", 5612),
    ("hyundai-tucson-2019", 10593),
    ("renault-clio-2021", 13394),
    ("mercedes-benz-glc-2023", 130),
    ("renault-clio-2023", 4948),
    ("land-rover-range-rover-evoque-2018", 5836),
    ("lancia-ypsilon-hybrid-2025", 8584),
]

# Bad cited n that must fail (pre-merge / thin-F stubs).
SEED_N_MUST_FAIL = [
    ("hyundai-i10-2021", 12),
    ("bmw-3-series-2021", 3615),
]

# Labels that must name the counted Cn / list aggregated variants.
SEED_LABEL_SUBSTR = [
    ("bmw-3-series-2023", "M340D"),
    ("mercedes-benz-glc-2023", "GLC 300"),
    ("renault-clio-2023", "E-TECH HYBRID"),
    ("audi-a4-2018", "A4 AVANT"),
    ("renault-clio-2021", "E-Tech"),
    ("porsche-911-2023", "911 S/T"),  # full list, not truncated with …
    ("land-rover-range-rover-evoque-2018", "EVOQUE"),
]

# (cache, merge_key_norm, year, ft, expect_n after Cn strip+casefold merge)
MODEL_MERGE_CASES = [
    ("IT_BMW_fuels.json", "X3XDRIVE20D", 2020, "DIESEL", 3149.0),
    ("IT_BMW_fuels.json", "X3XDRIVE20D", 2021, "DIESEL", 3485.0),
    ("IT_BMW_fuels.json", "118D", 2022, "DIESEL", 2002.0),
    ("IT_HYUNDAI_fuels.json", "I10", 2021, "PETROL", 11699.0),
    ("IT_HYUNDAI_fuels.json", "I20", 2021, "PETROL", 5612.0),
    ("IT_HYUNDAI_fuels.json", "TUCSONIX35", 2019, "DIESEL", 10593.0),
]


def _merged_ft_n(wrap: dict, merge_key: str, year: int, ft: str) -> float:
    """Sum Status F (else P / thin-F→P) across Cn variants sharing merge_key."""
    fuel_buckets: list[dict] = []
    for mb in wrap["response"]["aggregations"]["models"]["buckets"]:
        if eea.model_name_merge_key(str(mb.get("key", ""))) != merge_key:
            continue
        for yb in mb["years"]["buckets"]:
            if int(yb["key"]) != year:
                continue
            fuel_buckets.extend(yb.get("fuels", {}).get("buckets") or [])
    if not fuel_buckets:
        return 0.0
    deduped = eea.dedupe_fuel_buckets(fuel_buckets)
    return float(deduped.get(ft, {}).get("n") or 0)


def _normalize_ice_keys(ice: dict, hev: dict) -> None:
    for maps in (ice, hev):
        for key in list(maps.keys()):
            if "_" in key and key != "MERCEDES-BENZ":
                fixed = key.replace("_", " ")
                if fixed not in maps or len(maps[fixed]) < len(maps[key]):
                    maps[fixed] = maps.pop(key)
                elif key in maps:
                    maps.pop(key, None)


def main() -> int:
    failures: list[str] = []
    for fname, model, year, ft, expect_n, bad in CASES:
        path = eea.CACHE_DIR / fname
        if not path.is_file():
            failures.append(f"missing cache {fname}")
            continue
        wrap = json.loads(path.read_text(encoding="utf-8"))
        found = False
        for mb in wrap["response"]["aggregations"]["models"]["buckets"]:
            if mb.get("key") != model:
                continue
            for yb in mb["years"]["buckets"]:
                if int(yb["key"]) != year:
                    continue
                # Merge sibling Cn spellings (CEED / CEE'D, 320d / 320D, …).
                got = _merged_ft_n(wrap, eea.model_name_merge_key(model), year, ft)
                fuels = yb["fuels"]["buckets"]
                deduped = eea.dedupe_fuel_buckets(fuels)
                status = deduped.get(ft, {}).get("status")
                found = True
                has_status = any((f.get("status") or {}).get("buckets") for f in fuels)
                if not has_status and year <= 2024:
                    failures.append(
                        f"{fname} {model} {year}: missing Status sub-agg (re-fetch caches)"
                    )
                if abs(got - expect_n) > 0.5:
                    failures.append(
                        f"{fname} {model} {year}: n={got} want {expect_n} "
                        f"(must not be P/sum {bad}; status={status})"
                    )
                if abs(got - bad) < 0.5:
                    failures.append(
                        f"{fname} {model} {year}: still using bad n={got} (P or F+P)"
                    )
                if status == "P" and year <= 2024 and expect_n != bad:
                    # F must win when present for these spot cases
                    failures.append(f"{fname} {model} {year}: status=P but F expected")
        if not found:
            failures.append(f"missing cell {fname} {model} {year}")

    ice = truth.load_ice_maps()
    hev = truth.load_hev_maps()
    _normalize_ice_keys(ice, hev)

    checks = [
        ("MERCEDES-BENZ", ("C220D", 2022, "DIESEL"), 1218.0),
        ("MERCEDES-BENZ", ("C200D", 2024, "DIESEL"), 845.0),
        ("KIA", ("NIRO", 2022, "PETROL"), 2239.0),
        ("KIA", ("SPORTAGE", 2022, "PETROL"), 6597.0),
        ("KIA", ("CEED", 2019, "PETROL"), 1298.0),
        ("ALFA ROMEO", ("STELVIO", 2023, "DIESEL"), 6120.0),
        ("RENAULT", ("CAPTUR", 2018, "DIESEL"), 20696.0),
        ("LAND ROVER", ("RANGEROVERSPORT", 2022, "DIESEL"), 738.0),
    ]
    for brand, key, expect in checks:
        got = float((ice.get(brand) or {}).get(key, {}).get("n") or 0)
        if abs(got - expect) > 0.5:
            failures.append(f"ice_map {brand} {key}: n={got} want {expect}")

    s450 = float(
        (ice.get("MERCEDES-BENZ") or {}).get(("S450D4MATIC", 2025, "DIESEL"), {}).get("n") or 0
    )
    if abs(s450 - 54.0) > 0.5:
        failures.append(f"ice_map S450D4MATIC 2025: n={s450} want 54 (P-only year)")

    # BMW 3 Series family after Cn casing merge
    for year, expect in ((2019, 5003.0), (2020, 4905.0), (2021, 3716.0), (2022, 2767.0), (2023, 4073.0)):
        fam = eea.bmw_3_series_diesel_hit(ice.get("BMW") or {}, year)
        got = float(fam.get("n") or 0) if fam else 0.0
        if abs(got - expect) > 0.5:
            failures.append(f"bmw_3_series_diesel_hit {year}: n={got} want {expect}")
    fam23 = eea.bmw_3_series_diesel_hit(ice.get("BMW") or {}, 2023)
    if fam23 and "M340D" not in " ".join(fam23.get("variants") or []):
        failures.append("bmw_3_series_diesel_hit 2023: variants must include M340D XDRIVE")

    for year, expect in ((2019, 3516.0), (2020, 1848.0), (2021, 1860.0), (2022, 1956.0)):
        fam = eea.bmw_5_series_diesel_hit(ice.get("BMW") or {}, year)
        got = float(fam.get("n") or 0) if fam else 0.0
        if abs(got - expect) > 0.5:
            failures.append(f"bmw_5_series_diesel_hit {year}: n={got} want {expect}")

    rows: list[dict] = json.loads(truth.SEED_PATH.read_text(encoding="utf-8"))
    by_id = {r["id"]: r for r in rows}
    for rid, expect_n in SEED_N_CASES:
        row = by_id.get(rid)
        if not row:
            failures.append(f"missing seed row {rid}")
            continue
        sn = str(row.get("sourceName") or "")
        m = N_PAT.search(sn)
        cited = int(m.group(1)) if m else None
        if cited != expect_n:
            failures.append(f"seed {rid}: sourceName n={cited} want {expect_n} ({sn})")

    for rid, bad_n in SEED_N_MUST_FAIL:
        row = by_id.get(rid)
        if not row:
            continue
        sn = str(row.get("sourceName") or "")
        m = N_PAT.search(sn)
        cited = int(m.group(1)) if m else None
        if cited == bad_n:
            failures.append(
                f"seed {rid}: still cites bad pre-merge n={bad_n} ({sn})"
            )

    for fname, merge_key, year, ft, expect_n in MODEL_MERGE_CASES:
        path = eea.CACHE_DIR / fname
        if not path.is_file():
            failures.append(f"missing cache {fname}")
            continue
        wrap = json.loads(path.read_text(encoding="utf-8"))
        got = _merged_ft_n(wrap, merge_key, year, ft)
        if abs(got - expect_n) > 0.5:
            failures.append(
                f"model-merge {fname} {merge_key} {year} {ft}: n={got} want {expect_n}"
            )

    for rid, needle in SEED_LABEL_SUBSTR:
        sn = str((by_id.get(rid) or {}).get("sourceName") or "")
        if needle not in sn:
            failures.append(f"seed {rid}: label must mention {needle!r}: {sn}")

    # Refs must name the counted Cn (not a higher-volume sibling).
    refs_path = truth.REFS_PATH
    if refs_path.is_file():
        refs = {r["id"]: r for r in json.loads(refs_path.read_text(encoding="utf-8"))}
        glc = refs.get("mercedes-benz-glc-2023") or {}
        if glc.get("n") != 130 or "300" not in str(glc.get("eea_model") or ""):
            failures.append(
                f"refs glc-2023: want n=130 GLC 300, got n={glc.get('n')} model={glc.get('eea_model')}"
            )
        clio = refs.get("renault-clio-2023") or {}
        if clio.get("n") != 4948 or "HYBRID" not in str(clio.get("eea_model") or "").upper():
            failures.append(
                f"refs clio-2023: want n=4948 E-TECH HYBRID, got n={clio.get('n')} "
                f"model={clio.get('eea_model')}"
            )

    mismatch = 0
    unresolved = 0
    for r in rows:
        sn = str(r.get("sourceName") or "")
        if not EEA_LABEL_PAT.match(sn) or "n=" not in sn:
            continue
        m = N_PAT.search(sn)
        if not m:
            failures.append(f"EEA row {r.get('id')}: sourceName missing n= ({sn})")
            unresolved += 1
            continue
        cited = int(m.group(1))
        hit = refresh.resolve_label_cell(r, ice, hev)
        if not hit:
            failures.append(f"EEA row {r.get('id')}: unresolved Status-F cell ({sn})")
            unresolved += 1
            continue
        mn, ft, cell, ey = hit
        cite_y = refresh._cite_year(sn, int(r.get("year") or 0))
        if int(ey) != cite_y:
            failures.append(
                f"EEA row {r.get('id')}: resolved year {ey} != cited year {cite_y}"
            )
            unresolved += 1
            continue
        real = int(float(cell.get("n") or 0))
        if cited != real:
            failures.append(
                f"EEA row {r.get('id')}: cited n={cited} != Status-F n={real} "
                f"({mn} {ft} {ey})"
            )
            mismatch += 1

    if failures:
        print("EEA Status F/P dedupe FAIL:", file=sys.stderr)
        for line in failures[:100]:
            print(" ", line, file=sys.stderr)
        if len(failures) > 100:
            print(f"  … and {len(failures) - 100} more", file=sys.stderr)
        print(
            f"total failures={len(failures)} mismatch={mismatch} unresolved={unresolved}",
            file=sys.stderr,
        )
        return 1
    print("EEA Status F/P dedupe OK (all EEA n= labels match Status F cells)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
