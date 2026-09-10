#!/usr/bin/env python3
"""
Estrae candidati make/model dal dump NHTSA già scaricato, filtrati sui marchi usati in EVforME?.
Output:
- EVforME?/Data/external/nhtsa_seed_candidates.json
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


def norm(s: str) -> str:
    return (
        s.lower()
        .replace("-", " ")
        .replace("_", " ")
        .replace(".", " ")
        .replace("  ", " ")
        .strip()
    )


def main() -> None:
    repo = Path(__file__).resolve().parents[1]
    nhtsa_path = repo / "EVforME?" / "Data" / "external" / "nhtsa_models_top120_makes.json"
    seed_path = repo / "EVforME?" / "Data" / "vehicles.seed.json"
    out_path = repo / "EVforME?" / "Data" / "external" / "nhtsa_seed_candidates.json"

    if not nhtsa_path.exists() or not seed_path.exists():
        raise SystemExit("Missing nhtsa models dump or vehicles.seed.json")

    nhtsa = json.loads(nhtsa_path.read_text(encoding="utf-8"))
    seed = json.loads(seed_path.read_text(encoding="utf-8"))

    brands_in_seed = sorted({v["brand"] for v in seed})
    seed_brand_norm = {norm(b): b for b in brands_in_seed}

    out: dict[str, list[str]] = {}
    models_by_make = nhtsa.get("models_by_make", {})
    for make_name, rows in models_by_make.items():
        key = norm(make_name)
        if key not in seed_brand_norm:
            continue
        brand = seed_brand_norm[key]
        models = sorted(
            {
                str(r.get("Model_Name", "")).strip()
                for r in rows
                if str(r.get("Model_Name", "")).strip()
            }
        )
        if models:
            out[brand] = models

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "NHTSA vPIC models_by_make",
        "brands_in_seed": len(brands_in_seed),
        "brands_with_nhtsa_candidates": len(out),
        "candidates": out,
    }
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(out_path)


if __name__ == "__main__":
    main()

