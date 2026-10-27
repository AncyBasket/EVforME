#!/usr/bin/env python3
"""
Regenerate docs/launch-gap-coverage.csv and print missing-family / PHEV stats.

Uses EEA IT cache + homologation aliases. PYTHONHASHSEED-stable.
"""

from __future__ import annotations

import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SEED = REPO / "EVforME?" / "Data" / "vehicles.seed.quality.json"
CACHE = REPO / "scripts" / "cache" / "eea"
ALIAS = REPO / "EVforME?" / "Data" / "homologation_commercial_aliases.json"
OUT = REPO / "docs" / "launch-gap-coverage.csv"


def norm(s: str) -> str:
    s = (s or "").upper()
    s = re.sub(r"[^A-Z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def brand_from_file(fn: str) -> str:
    name = (
        fn.replace("IT_", "")
        .replace("_fuels.json", "")
        .replace("_hev_FmH.json", "")
        .replace("_bev_Zr.json", "")
    )
    return name.replace("_", " ")


def brand_match(a: str, b: str) -> bool:
    aa, bb = norm(a), norm(b)
    return aa == bb or aa in bb or bb in aa or aa.replace(" ", "") == bb.replace(" ", "")


def load_eea() -> dict[tuple[str, str, int], dict]:
    out: dict[tuple[str, str, int], dict] = {}
    for p in sorted(CACHE.glob("IT_*.json")):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        buckets = (
            ((d.get("response") or {}).get("aggregations") or {})
            .get("models", {})
            .get("buckets")
            or []
        )
        brand = brand_from_file(p.name)
        for mb in buckets:
            mkey = mb["key"]
            for yb in (mb.get("years") or {}).get("buckets") or []:
                year = int(yb["key"])
                if year < 2022 or year > 2025:
                    continue
                fuels = {}
                for fb in (yb.get("fuels") or {}).get("buckets") or []:
                    fuel = str(fb["key"])
                    n = float((fb.get("sum_r") or {}).get("value") or fb.get("doc_count") or 0)
                    fuels[fuel] = {
                        "n": n,
                        "co2": (fb.get("avg_co2") or {}).get("value"),
                        "kw": (fb.get("avg_kw") or {}).get("value"),
                    }
                total = sum(f["n"] for f in fuels.values()) or float(yb.get("doc_count") or 0)
                # Prefer year doc_count when fuels double-count PETROL+petrol
                year_doc = float(yb.get("doc_count") or 0)
                n_use = year_doc if year_doc else total
                key = (brand, mkey, year)
                prev = out.get(key)
                if prev is None or n_use > prev["n"]:
                    out[key] = {"n": n_use, "fuels": fuels}
    return out


def build_alias_map(aliases: list[dict]) -> dict[tuple[str, str], str]:
    m: dict[tuple[str, str], str] = {}
    for a in aliases:
        b = norm(a["brand"])
        for k in a.get("eeaKeys") or []:
            m[(b, norm(k))] = norm(a["commercialName"])
    return m


def catalog_index(parents: list[dict]):
    by_brand: dict[str, list[tuple[str, int, str, str | None]]] = defaultdict(list)
    for r in parents:
        by_brand[norm(r["brand"])].append(
            (norm(r["model"]), int(r["year"]), str(r["id"]), r.get("powertrain"))
        )
    return by_brand


def catalog_hit(
    brand: str,
    model: str,
    year: int,
    by_brand,
    alias_map,
    require_pt: str | None = None,
) -> str | None:
    m = norm(model)
    commercial = alias_map.get((norm(brand), m), m)
    # strip leading brand tokens from EEA model key
    btoks = norm(brand).split()
    m2 = m
    for t in btoks:
        if m2.startswith(t + " "):
            m2 = m2[len(t) + 1 :]
    for cb, items in by_brand.items():
        if not brand_match(brand, cb):
            continue
        for cm, y, rid, pt in items:
            if y != year:
                continue
            if require_pt and pt != require_pt:
                continue
            for cand in (m, m2, commercial):
                if not cand:
                    continue
                if cand in cm or cm in cand:
                    return rid
                if cand.replace(" ", "") in cm.replace(" ", "") or cm.replace(
                    " ", ""
                ) in cand.replace(" ", ""):
                    return rid
    return None


def fuel_label(row: dict) -> str:
    pt = row.get("powertrain")
    fk = row.get("fuelKind")
    if pt == "ev":
        return "BEV"
    if pt == "phev":
        return "PHEV"
    if pt == "hev":
        return "ibrida"
    mapping = {
        "petrol": "benzina",
        "diesel": "diesel",
        "lpg": "GPL",
        "cng": "metano",
    }
    return mapping.get(str(fk or ""), str(fk or "ice"))


def main() -> int:
    seed = json.loads(SEED.read_text(encoding="utf-8"))
    parents = [r for r in seed if not r.get("parentId")]
    aliases = json.loads(ALIAS.read_text(encoding="utf-8")).get("aliases") or []
    alias_map = build_alias_map(aliases)
    by_brand = catalog_index(parents)
    eea = load_eea()

    # Brand+model year regs (max across duplicate keys)
    regs_bm_year: dict[tuple[str, str, int], float] = {}
    regs_bm_sum: dict[tuple[str, str], float] = defaultdict(float)
    # Use commercial name when alias exists for summing toward catalog match
    for (brand, model, year), info in eea.items():
        commercial = alias_map.get((norm(brand), norm(model)), norm(model))
        # Prefer short commercial for known aliases
        key_model = commercial if (norm(brand), norm(model)) in alias_map else norm(model)
        # strip brand prefix
        for t in norm(brand).split():
            if key_model.startswith(t + " "):
                key_model = key_model[len(t) + 1 :]
        k = (norm(brand), key_model, year)
        regs_bm_year[k] = max(regs_bm_year.get(k, 0), info["n"])

    for (b, m, y), n in regs_bm_year.items():
        regs_bm_sum[(b, m)] += n

    # Per-year by original EEA key for missing detection
    missing_500_families: set[tuple[str, str]] = set()
    missing_500_rows = 0
    for (brand, model, year), info in sorted(eea.items(), key=lambda x: (-x[1]["n"], x[0])):
        if info["n"] < 500:
            continue
        hit = catalog_hit(brand, model, year, by_brand, alias_map)
        if not hit:
            missing_500_rows += 1
            missing_500_families.add((norm(brand), norm(model)))

    phev_missing = 0
    phev_present = 0
    phev_seen: set[tuple[str, str, int]] = set()
    for (brand, model, year), info in eea.items():
        for fuel, f in info["fuels"].items():
            fu = fuel.upper()
            if "ELECTRIC" not in fu:
                continue
            if not any(x in fu for x in ("PETROL", "DIESEL", "/")):
                continue
            if f["n"] < 500:
                continue
            key = (norm(brand), norm(model), year)
            if key in phev_seen:
                continue
            phev_seen.add(key)
            hit = catalog_hit(brand, model, year, by_brand, alias_map, require_pt="phev")
            if hit:
                phev_present += 1
            else:
                phev_missing += 1

    # CSV rows for catalog parents
    def regs_for_parent(r: dict) -> tuple[float, float, dict[int, float]]:
        b, m = norm(r["brand"]), norm(r["model"])
        by_year = {}
        for y in (2022, 2023, 2024, 2025):
            # soft: any eea model matching
            best = 0.0
            for (eb, em, ey), n in regs_bm_year.items():
                if ey != y or not brand_match(eb, b):
                    continue
                if m in em or em in m or m.replace(" ", "") in em.replace(" ", ""):
                    best = max(best, n)
            by_year[y] = best
        s = sum(by_year.values())
        return by_year.get(int(r["year"]), 0.0), s, by_year

    children_by_parent: dict[str, list] = defaultdict(list)
    for r in seed:
        if r.get("parentId"):
            children_by_parent[str(r["parentId"])].append(r)

    rows_out = []
    for r in parents:
        my, sm, by_year = regs_for_parent(r)
        kids = children_by_parent.get(str(r["id"]), [])
        rows_out.append(
            {
                "id": r["id"],
                "brand": r["brand"],
                "model": r["model"],
                "year": r["year"],
                "fuel": fuel_label(r),
                "powertrain": r.get("powertrain"),
                "fuelKind": r.get("fuelKind"),
                "it_regs_model_year": int(my),
                "it_regs_brand_model_sum_2022_2025": int(sm),
                "it_regs_2022": int(by_year.get(2022, 0)),
                "it_regs_2023": int(by_year.get(2023, 0)),
                "it_regs_2024": int(by_year.get(2024, 0)),
                "it_regs_2025": int(by_year.get(2025, 0)),
                "has_versions": 1 if kids else 0,
                "n_versions": len(kids),
                "official_matched": 1
                if any(k.get("officialMatched") for k in kids) or r.get("officialMatched")
                else 0,
                "named_trim": 1
                if r.get("trim") and not str(r.get("trim")).startswith("Versione")
                else 0,
                "has_battery": 1 if r.get("batteryKWh") not in (None, "", 0) else 0,
                "has_wltp_range": 1 if r.get("wltpRangeKm") not in (None, "", 0) else 0,
                "has_consumption": 1
                if r.get("fuelConsumptionLPerKm") not in (None, "")
                or r.get("energyConsumptionKWhPerKm") not in (None, "")
                else 0,
                "has_list_price": 0,
                "has_source": 1 if r.get("sourceName") else 0,
                "sourceName": r.get("sourceName") or "",
                "sourceUpdatedAt": r.get("sourceUpdatedAt") or "",
                "eea_regs_note": (
                    "EEA IT model×year doc_count (all fuels combined at model grain; "
                    "max across fuels/hev/bev files). Soft string match brand+model + aliases."
                ),
            }
        )

    rows_out.sort(
        key=lambda x: (
            -x["it_regs_brand_model_sum_2022_2025"],
            -x["year"],
            x["brand"],
            x["model"],
            x["id"],
        )
    )

    fieldnames = list(rows_out[0].keys()) if rows_out else []
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for row in rows_out:
            w.writerow(row)

    phev_catalog = sum(1 for r in parents if r.get("powertrain") == "phev")
    stats = {
        "parents": len(parents),
        "csv_rows": len(rows_out),
        "missing_ge500_families": len(missing_500_families),
        "missing_ge500_year_rows": missing_500_rows,
        "phev_catalog_parents": phev_catalog,
        "phev_eea_ge500_year_present": phev_present,
        "phev_eea_ge500_year_missing": phev_missing,
    }
    print(json.dumps(stats, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
