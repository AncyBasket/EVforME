#!/usr/bin/env python3
"""Strip vehicle imageURL hosts that are risky for App Store / TestFlight review.

Default: remove Quattroruote/Edidomus + Wikimedia (and catbox image hotlinks).
Keeps local/bundled behavior: UI already shows a placeholder when imageURL is null.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.parse import urlparse

# Risky / unlicensed hotlinks. Do NOT blanket-strip Wikimedia/Flickr:
# CC0/PD URLs may be applied via docs/image-pipeline (see apply_free_vehicle_images.py).
BLOCKED_HOST_PARTS = (
    "edidomus.it",
    "quattroruote",
    "catbox.moe",
    "source.unsplash.com",
    "images.unsplash.com",
)


def should_strip(url: str | None) -> bool:
    if not url:
        return False
    host = (urlparse(url).netloc or "").lower()
    return any(part in host for part in BLOCKED_HOST_PARTS)


def scrub_items(items: list[dict]) -> tuple[int, int]:
    total = 0
    stripped = 0
    for item in items:
        url = item.get("imageURL") or item.get("imageUrl")
        if not url:
            continue
        total += 1
        if should_strip(url):
            item["imageURL"] = None
            if "imageUrl" in item:
                item["imageUrl"] = None
            stripped += 1
    return total, stripped


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "paths",
        nargs="*",
        type=Path,
        default=[
            Path("EVforME?/Data/vehicles.seed.quality.json"),
            Path("EVforME?/Data/vehicles.seed.wltp_enriched.json"),
            Path("EVforME?/Data/vehicles.seed.nhtsa_enriched.with_images.json"),
            Path("api/static/vehicles.catalog.json"),
            Path("api/static/vehicles.catalog.min.json"),
        ],
    )
    args = parser.parse_args()

    for path in args.paths:
        if not path.exists():
            print(f"skip missing {path}")
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            total, stripped = scrub_items(data)
            path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
            print(f"{path}: stripped {stripped}/{total} imageURL")
        elif isinstance(data, dict) and isinstance(data.get("vehicles"), list):
            total, stripped = scrub_items(data["vehicles"])
            path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
            print(f"{path}: stripped {stripped}/{total} imageURL")
        else:
            print(f"skip unsupported shape {path}")


if __name__ == "__main__":
    main()
