#!/usr/bin/env python3
"""
Pipeline locale end-to-end:
1) fetch fonti pubbliche
2) snapshot/report
3) arricchimento seed da NHTSA
4) sync dell'API locale (se attiva)
"""

from __future__ import annotations

import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path


def run(cmd: list[str], cwd: Path) -> None:
    print(">", " ".join(cmd))
    subprocess.run(cmd, cwd=cwd, check=True)


def try_api_sync() -> None:
    url = "http://127.0.0.1:8787/catalog/sync"
    req = urllib.request.Request(url, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            print("API sync:", resp.status, resp.read().decode("utf-8", errors="replace"))
    except urllib.error.URLError:
        print("API sync skipped: local API not running")


def main() -> None:
    repo = Path(__file__).resolve().parents[1]
    run([sys.executable, "scripts/fetch_public_vehicle_sources.py"], repo)
    run([sys.executable, "scripts/fetch_official_energy_costs.py"], repo)
    run([sys.executable, "scripts/build_public_source_snapshot.py"], repo)
    run([sys.executable, "scripts/extract_nhtsa_candidates_for_seed.py"], repo)
    run([sys.executable, "scripts/compare_seed_vs_nhtsa.py"], repo)
    run([sys.executable, "scripts/apply_nhtsa_suggestions_to_seed.py"], repo)
    run([sys.executable, "scripts/enrich_consumption_from_eea.py"], repo)
    run([sys.executable, "scripts/validate_catalog_quality.py"], repo)
    try_api_sync()
    print("Pipeline completed.")


if __name__ == "__main__":
    main()

