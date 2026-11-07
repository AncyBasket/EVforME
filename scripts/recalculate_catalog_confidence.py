#!/usr/bin/env python3
"""Recompute catalog quality scores and synchronized local mirrors.

Run without --write for a preview; --write applies the migration and bumps seedVersion.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from collections import Counter

from catalog_confidence import POLICY_VERSION, apply_confidence

ROOT = Path(__file__).resolve().parents[1]
SEED = ROOT / "EVforME?" / "Data" / "vehicles.seed.quality.json"
APP_MANIFEST = ROOT / "EVforME?" / "Data" / "catalog_cdn.json"
API_JSON = ROOT / "api" / "static" / "vehicles.catalog.json"
API_MIN = ROOT / "api" / "static" / "vehicles.catalog.min.json"
API_MANIFEST = ROOT / "api" / "static" / "catalog_cdn.json"


def compact_json(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")


def pretty_json(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def migrate_rows(rows: list[dict]) -> tuple[list[dict], Counter]:
    counts: Counter = Counter()
    migrated = []
    for original in rows:
        row = dict(original)
        apply_confidence(row, preserve_legacy=True)
        counts[(row["confidenceScore"], row["confidenceEvidence"]["reasonCode"])] += 1
        migrated.append(row)
    return migrated, counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="write seed, mirrors and manifests; otherwise preview")
    args = parser.parse_args()

    rows = json.loads(SEED.read_text(encoding="utf-8"))
    migrated, counts = migrate_rows(rows)
    print(f"policy=v{POLICY_VERSION}; rows={len(migrated)}; mode={'write' if args.write else 'preview'}")
    for (score, reason), n in sorted(counts.items(), key=lambda item: (item[0][0], item[0][1])):
        print(f"{score:.2f}\t{n}\t{reason}")

    if not args.write:
        return

    app_manifest = json.loads(APP_MANIFEST.read_text(encoding="utf-8"))
    api_manifest = json.loads(API_MANIFEST.read_text(encoding="utf-8"))
    old_version = int(app_manifest["seedVersion"])
    api_old_version = int(api_manifest["seedVersion"])
    already_current = all(
        original.get("confidencePolicyVersion") == POLICY_VERSION
        and original.get("confidenceScore") == migrated_row.get("confidenceScore")
        and original.get("confidenceEvidence") == migrated_row.get("confidenceEvidence")
        and original.get("confidenceScoreLegacy") is not None
        for original, migrated_row in zip(rows, migrated)
    )
    new_version = old_version if already_current and api_old_version == old_version else max(old_version, api_old_version) + 1
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    seed_bytes = compact_json(migrated)
    min_api_bytes = seed_bytes
    pretty_api_bytes = pretty_json(migrated)
    app_manifest.update({
        "rows": len(migrated),
        "bytes": len(seed_bytes),
        "seedVersion": new_version,
        "updatedAt": now,
        "note": (
            f"seedVersion {new_version}: confidenceScore ricalcolato con policy deterministica v{POLICY_VERSION}; "
            "indice ordinale di qualità dati, non probabilità. Score legacy conservato in confidenceScoreLegacy."
        ),
    })
    api_manifest.update({
        "rows": len(migrated),
        "bytes": len(min_api_bytes),
        "seedVersion": new_version,
        "updatedAt": now,
        "note": (
            f"seedVersion {new_version}: confidenceScore ricalcolato con policy deterministica v{POLICY_VERSION}; "
            "indice ordinale di qualità dati, non probabilità. Score legacy conservato in confidenceScoreLegacy."
        ),
    })

    SEED.write_bytes(seed_bytes)
    API_MIN.write_bytes(min_api_bytes)
    API_JSON.write_bytes(pretty_api_bytes)
    APP_MANIFEST.write_bytes(pretty_json(app_manifest))
    API_MANIFEST.write_bytes(pretty_json(api_manifest))
    action = "already current; mirror sync" if already_current else f"seedVersion {old_version} -> {new_version}"
    print(f"{action}; seed bytes={len(seed_bytes)}; mirrors synchronized")


if __name__ == "__main__":
    main()
