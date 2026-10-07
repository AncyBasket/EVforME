#!/usr/bin/env python3
"""
Rimuove dal seed le righe marca/modello/anno fuori dalla finestra di produzione.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from model_production_years import resolve_year_window, year_is_plausible


def prune(path: Path, dry_run: bool = False) -> tuple[int, int, Counter]:
    rows = json.loads(path.read_text(encoding="utf-8"))
    kept: list[dict] = []
    removed = Counter()
    for r in rows:
        brand = str(r.get("brand", ""))
        model = str(r.get("model", ""))
        year = int(r.get("year", 0))
        pt = r.get("powertrain")
        if year_is_plausible(brand, model, year, pt if isinstance(pt, str) else None):
            kept.append(r)
        else:
            first, last = resolve_year_window(brand, model, pt if isinstance(pt, str) else None)
            removed[f"{brand}|{model}|{pt} want {first}-{last} got {year}"] += 1

    if not dry_run:
        path.write_text(json.dumps(kept, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    return len(rows), len(kept), removed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--path",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "EVforME?" / "Data" / "vehicles.seed.quality.json",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--also-base", action="store_true", help="Also prune vehicles.seed.json")
    args = parser.parse_args()

    paths = [args.path]
    if args.also_base:
        paths.append(args.path.parent / "vehicles.seed.json")

    for path in paths:
        if not path.exists():
            print(f"skip missing {path}")
            continue
        before, after, removed = prune(path, dry_run=args.dry_run)
        print(f"{path.name}: {before} → {after} (removed {before - after})")
        for key, n in removed.most_common(25):
            print(f"  {n:4d}  {key}")
        if len(removed) > 25:
            print(f"  … +{len(removed) - 25} other groups")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
