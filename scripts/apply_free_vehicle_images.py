#!/usr/bin/env python3
"""Apply approved CC0/PD candidate images onto vehicles.seed.quality.json.

Rules:
- Only candidates/*.json with approved:true
- Only license in {cc0, pd, public domain}
- Picks highest match_score candidate (or preferred_url if set)
- Leaves imageURL nil on all other vehicles
- Bumps VehicleCatalogService seedVersion when writing

Usage:
  python3 scripts/apply_free_vehicle_images.py --dry-run
  python3 scripts/apply_free_vehicle_images.py
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

ALLOWED = {"cc0", "pd", "public domain", "publicdomain"}


def license_ok(raw: str | None) -> bool:
    if not raw:
        return False
    key = raw.strip().casefold().replace("_", " ").replace("-", " ")
    key = re.sub(r"\s+", " ", key)
    if key in ALLOWED:
        return True
    return "cc0" in key or "public domain" in key or key == "pd"


def pick_candidate(doc: dict) -> dict | None:
    preferred = doc.get("preferred_url")
    cands = list(doc.get("candidates") or [])
    if preferred:
        for c in cands:
            if c.get("url") == preferred and license_ok(c.get("license") or c.get("license_raw")):
                return c
    ranked = [
        c
        for c in cands
        if c.get("url") and license_ok(c.get("license") or c.get("license_raw"))
    ]
    ranked.sort(key=lambda c: float(c.get("match_score") or 0), reverse=True)
    return ranked[0] if ranked else None


def bump_seed_version(catalog_swift: Path) -> int | None:
    text = catalog_swift.read_text(encoding="utf-8")
    m = re.search(r"(private let seedVersion = )(\d+)", text)
    if not m:
        return None
    new_v = int(m.group(2)) + 1
    catalog_swift.write_text(
        text[: m.start(2)] + str(new_v) + text[m.end(2) :],
        encoding="utf-8",
    )
    return new_v


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--candidates-dir",
        type=Path,
        default=Path("docs/image-pipeline/candidates"),
    )
    parser.add_argument(
        "--seed",
        type=Path,
        default=Path("EVforME?/Data/vehicles.seed.quality.json"),
    )
    parser.add_argument(
        "--catalog-swift",
        type=Path,
        default=Path("EVforME?/Core/Logic/VehicleCatalogService.swift"),
    )
    parser.add_argument(
        "--attribution",
        type=Path,
        default=Path("docs/image-pipeline/ATTRIBUTION.md"),
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    approved_docs: list[dict] = []
    for path in sorted(args.candidates_dir.glob("*.json")):
        doc = json.loads(path.read_text(encoding="utf-8"))
        if doc.get("approved") is True:
            approved_docs.append(doc)

    picks: dict[str, dict] = {}
    skipped_no_cand = 0
    for doc in approved_docs:
        cand = pick_candidate(doc)
        if not cand:
            skipped_no_cand += 1
            continue
        picks[doc["id"]] = {"doc": doc, "cand": cand}

    seed = json.loads(args.seed.read_text(encoding="utf-8"))
    by_id = {row["id"]: row for row in seed}

    written = 0
    missing_ids = 0
    changes: list[dict] = []
    for vid, payload in picks.items():
        row = by_id.get(vid)
        if not row:
            missing_ids += 1
            continue
        url = payload["cand"]["url"]
        prev = row.get("imageURL")
        if prev != url:
            changes.append(
                {
                    "id": vid,
                    "brand": row.get("brand"),
                    "model": row.get("model"),
                    "year": row.get("year"),
                    "url": url,
                    "license": payload["cand"].get("license"),
                    "source_page": payload["cand"].get("source_page"),
                    "author": payload["cand"].get("author"),
                    "previous": prev,
                }
            )
            if not args.dry_run:
                row["imageURL"] = url
            written += 1

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dry_run": args.dry_run,
        "approved_files": len(approved_docs),
        "picked": len(picks),
        "written_or_would_write": written,
        "skipped_approved_without_candidate": skipped_no_cand,
        "missing_ids_in_seed": missing_ids,
        "seed_imageURL_nonnull_after": (
            sum(1 for r in seed if r.get("imageURL"))
            if args.dry_run
            else sum(1 for r in seed if r.get("imageURL"))
        ),
        "changes": changes,
    }

    # For dry-run, compute would-be nonnull including changes.
    if args.dry_run:
        ids = {c["id"] for c in changes}
        report["seed_imageURL_nonnull_after"] = sum(
            1 for r in seed if r.get("imageURL") or r["id"] in ids
        )

    print(json.dumps({k: v for k, v in report.items() if k != "changes"}, indent=2))
    print(f"changes: {len(changes)}")
    for c in changes[:30]:
        print(f"  - {c['id']}: {c['url'][:90]}")

    if args.dry_run:
        return

    args.seed.write_text(
        json.dumps(seed, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    new_v = bump_seed_version(args.catalog_swift)
    report["seedVersion"] = new_v

    lines = [
        "# Attribution (internal)",
        "",
        "CC0 / Public Domain vehicle images applied by `scripts/apply_free_vehicle_images.py`.",
        "Not shown in-app (CC0). Kept here for provenance.",
        "",
        f"Generated: {report['generated_at']}",
        f"seedVersion: {new_v}",
        "",
        "| id | vehicle | license | author | source |",
        "|----|---------|---------|--------|--------|",
    ]
    for c in changes:
        vehicle = f"{c.get('brand')} {c.get('model')} ({c.get('year')})"
        author = (c.get("author") or "—").replace("|", "/")
        source = c.get("source_page") or c.get("url") or ""
        lines.append(
            f"| `{c['id']}` | {vehicle} | {c.get('license')} | {author} | {source} |"
        )
    args.attribution.write_text("\n".join(lines) + "\n", encoding="utf-8")

    report_path = Path("docs/image-pipeline/last_apply_report.json")
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote seed + attribution; seedVersion={new_v}")


if __name__ == "__main__":
    main()
