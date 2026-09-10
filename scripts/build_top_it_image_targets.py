#!/usr/bin/env python3
"""Build a shortlist of Italy-relevant vehicles for free CC0/PD image search.

Reads EVforME?/Data/vehicles.seed.quality.json and writes
docs/image-pipeline/top_it_targets.json (150–300 rows).
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

# Brands commonly sold / familiar in IT (normalized compare is casefold).
PRIORITY_BRANDS: list[tuple[str, int]] = [
    ("Fiat", 100),
    ("Jeep", 95),
    ("Alfa Romeo", 94),
    ("Lancia", 90),
    ("Volkswagen", 88),
    ("Toyota", 86),
    ("Renault", 84),
    ("Peugeot", 82),
    ("Ford", 80),
    ("BMW", 78),
    ("Mercedes-Benz", 76),
    ("Audi", 74),
    ("Opel", 72),
    ("Citroen", 70),
    ("Hyundai", 68),
    ("Kia", 66),
    ("Tesla", 64),
    ("Skoda", 62),
    ("SEAT", 60),
    ("Cupra", 58),
    ("Nissan", 56),
    ("Dacia", 54),
    ("Volvo", 52),
    ("Mazda", 50),
    ("Suzuki", 48),
    ("Mini", 46),
    ("Porsche", 44),
    ("MG", 42),
]

POWERTRAIN_BONUS = {"ev": 8, "phev": 6, "ice": 0}
MIN_YEAR = 2018
TARGET_COUNT = 260
MAX_PER_BRAND = 16


def brand_weight(brand: str) -> int | None:
    b = brand.casefold()
    for name, weight in PRIORITY_BRANDS:
        if name.casefold() == b:
            return weight
    return None


def score_row(row: dict) -> int:
    w = brand_weight(row["brand"])
    if w is None:
        return -1
    year = int(row.get("year") or 0)
    if year < MIN_YEAR:
        return -1
    pt = str(row.get("powertrain") or "ice").lower()
    return w * 1000 + year + POWERTRAIN_BONUS.get(pt, 0)


def pick_targets(rows: list[dict], limit: int) -> list[dict]:
    """One row per (brand, model, powertrain) — newest year wins — then top N by score.

    Caps per brand so mid-tier IT brands (Audi, Mercedes, Hyundai, …) are not
    crowded out by long VW/Ford/BMW lineups.
    """
    best: dict[tuple[str, str, str], dict] = {}
    for row in rows:
        s = score_row(row)
        if s < 0:
            continue
        key = (
            str(row["brand"]).casefold(),
            str(row["model"]).casefold(),
            str(row.get("powertrain") or "ice").lower(),
        )
        prev = best.get(key)
        if prev is None or int(row["year"]) > int(prev["year"]):
            best[key] = row

    ranked = sorted(best.values(), key=score_row, reverse=True)
    out: list[dict] = []
    per_brand: dict[str, int] = {}
    for row in ranked:
        brand_key = str(row["brand"]).casefold()
        if per_brand.get(brand_key, 0) >= MAX_PER_BRAND:
            continue
        per_brand[brand_key] = per_brand.get(brand_key, 0) + 1
        out.append(
            {
                "id": row["id"],
                "brand": row["brand"],
                "model": row["model"],
                "year": row["year"],
                "powertrain": row.get("powertrain"),
                "priority": len(out) + 1,
            }
        )
        if len(out) >= limit:
            break
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=TARGET_COUNT)
    parser.add_argument(
        "--seed",
        type=Path,
        default=Path("EVforME?/Data/vehicles.seed.quality.json"),
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("docs/image-pipeline/top_it_targets.json"),
    )
    args = parser.parse_args()

    rows = json.loads(args.seed.read_text(encoding="utf-8"))
    targets = pick_targets(rows, args.limit)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_seed": str(args.seed),
        "min_year": MIN_YEAR,
        "selection": (
            "Italy-friendly brands × recent years; one id per brand+model+powertrain "
            "(newest year); ranked by brand priority then year; EV/PHEV slight boost; "
            f"max {MAX_PER_BRAND} models per brand."
        ),
        "count": len(targets),
        "targets": targets,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(targets)} targets → {args.out}")


if __name__ == "__main__":
    main()
