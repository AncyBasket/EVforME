#!/usr/bin/env python3
"""
Costruisce uno snapshot riassuntivo dai file pubblici scaricati:
- NHTSA makes/models
- EEA metadata
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


def main() -> None:
    repo = Path(__file__).resolve().parents[1]
    ext = repo / "EVforME?" / "Data" / "external"

    nhtsa_makes_path = ext / "nhtsa_getallmakes.json"
    nhtsa_models_path = ext / "nhtsa_models_top120_makes.json"
    eea_meta_path = ext / "eea_co2_cars_metadata.json"

    snapshot: dict = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sources": {},
    }

    if nhtsa_makes_path.exists():
        makes_payload = json.loads(nhtsa_makes_path.read_text(encoding="utf-8"))
        makes = makes_payload.get("Results", [])
        snapshot["sources"]["nhtsa"] = {
            "makes_count": len(makes),
            "sample_makes": sorted(
                {
                    m.get("Make_Name", "") or m.get("MakeName", "")
                    for m in makes
                    if (m.get("Make_Name", "") or m.get("MakeName", ""))
                }
            )[:100],
        }

    if nhtsa_models_path.exists():
        models_payload = json.loads(nhtsa_models_path.read_text(encoding="utf-8"))
        by_make = models_payload.get("models_by_make", {})
        model_count = sum(len(v) for v in by_make.values())
        snapshot["sources"].setdefault("nhtsa", {})
        snapshot["sources"]["nhtsa"].update(
            {
                "sampled_makes_with_models": len(by_make),
                "sampled_models_count": model_count,
                "model_fetch_errors": len(models_payload.get("model_fetch_errors", {})),
            }
        )

    if eea_meta_path.exists():
        eea = json.loads(eea_meta_path.read_text(encoding="utf-8"))
        snapshot["sources"]["eea"] = {
            "doi_links": eea.get("dois_found", []),
            "dataset_table_tags": eea.get("dataset_table_tags", []),
        }

    out = ext / "public_sources_snapshot.json"
    out.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    print(out)


if __name__ == "__main__":
    main()

