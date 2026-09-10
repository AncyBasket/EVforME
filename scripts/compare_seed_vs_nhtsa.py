#!/usr/bin/env python3
"""
Confronta i modelli presenti nel seed con i candidati NHTSA estratti.
Output:
- EVforME?/Data/external/seed_vs_nhtsa_report.json
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
    seed_path = repo / "EVforME?" / "Data" / "vehicles.seed.json"
    cand_path = repo / "EVforME?" / "Data" / "external" / "nhtsa_seed_candidates.json"
    out_path = repo / "EVforME?" / "Data" / "external" / "seed_vs_nhtsa_report.json"

    seed = json.loads(seed_path.read_text(encoding="utf-8"))
    cands = json.loads(cand_path.read_text(encoding="utf-8")).get("candidates", {})

    seed_models_by_brand: dict[str, set[str]] = {}
    for v in seed:
        seed_models_by_brand.setdefault(v["brand"], set()).add(v["model"])

    report: dict[str, dict] = {}
    total_seed_models = 0
    total_matches = 0

    for brand, seed_models in sorted(seed_models_by_brand.items()):
        total_seed_models += len(seed_models)
        cand_models = set(cands.get(brand, []))
        cand_norm = {norm(m) for m in cand_models}

        matched = sorted([m for m in seed_models if norm(m) in cand_norm])
        missing_in_nhtsa = sorted([m for m in seed_models if norm(m) not in cand_norm])

        # suggerimenti: modelli NHTSA non presenti in seed
        seed_norm = {norm(m) for m in seed_models}
        extra_nhtsa = sorted([m for m in cand_models if norm(m) not in seed_norm])[:40]

        total_matches += len(matched)
        coverage = (len(matched) / len(seed_models)) if seed_models else 0.0
        report[brand] = {
            "seed_model_count": len(seed_models),
            "nhtsa_candidate_count": len(cand_models),
            "matched_seed_models": matched,
            "missing_seed_models_in_nhtsa": missing_in_nhtsa,
            "nhtsa_extra_suggestions_top40": extra_nhtsa,
            "coverage_ratio": round(coverage, 3),
        }

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_seed_models": total_seed_models,
        "matched_seed_models": total_matches,
        "overall_coverage_ratio": round((total_matches / total_seed_models) if total_seed_models else 0.0, 3),
        "by_brand": report,
    }
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(out_path)


if __name__ == "__main__":
    main()

