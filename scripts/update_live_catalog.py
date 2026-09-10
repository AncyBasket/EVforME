#!/usr/bin/env python3
"""Un solo comando: foto listino Quattroruote + pubblica catalogo + aggiorna URL app.

  python3 scripts/update_live_catalog.py
  python3 scripts/update_live_catalog.py --skip-enrich   # solo publish
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def run(script: str, extra: list[str] | None = None) -> int:
    cmd = [sys.executable, str(REPO / "scripts" / script), *(extra or [])]
    print("+", " ".join(cmd), flush=True)
    return subprocess.call(cmd, cwd=str(REPO))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-enrich", action="store_true", help="Solo publish")
    parser.add_argument("--resume", action="store_true", default=True)
    parser.add_argument("--limit", type=int, default=0, help="Max pair Quattroruote (0=tutti)")
    args = parser.parse_args()

    if not args.skip_enrich:
        extra = ["--resume"] if args.resume else []
        if args.limit:
            extra += ["--limit", str(args.limit)]
        code = run("enrich_images_from_quattroruote.py", extra)
        if code != 0:
            return code

    return run("publish_catalog_cdn.py")


if __name__ == "__main__":
    raise SystemExit(main())
