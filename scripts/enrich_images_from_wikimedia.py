#!/usr/bin/env python3
"""
Arricchisce imageURL nel catalogo usando Wikimedia API (pubblica).

Input:
- EVforME?/Data/vehicles.seed.nhtsa_enriched.json (fallback vehicles.seed.json)

Output:
- EVforME?/Data/vehicles.seed.nhtsa_enriched.with_images.json
- EVforME?/Data/external/wikimedia_image_manifest.json
"""

from __future__ import annotations

import json
import ssl
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


def http_get_json(url: str, timeout: int = 30) -> dict:
    ctx = ssl.create_default_context()
    req = urllib.request.Request(url, headers={"User-Agent": "EVforME-wikimedia-enricher/1.0"})
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


def fetch_wikimedia_image(brand: str, model: str) -> str | None:
    # Query MediaWiki image search
    q = f"{brand} {model} car"
    params = {
        "action": "query",
        "format": "json",
        "generator": "search",
        "gsrsearch": q,
        "gsrnamespace": "6",  # File namespace
        "gsrlimit": "1",
        "prop": "imageinfo",
        "iiprop": "url",
    }
    url = "https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode(params)
    try:
        data = http_get_json(url)
    except Exception:
        return None

    pages = data.get("query", {}).get("pages", {})
    for page in pages.values():
        infos = page.get("imageinfo", [])
        if infos:
            return infos[0].get("url")
    return None


def main() -> None:
    repo = Path(__file__).resolve().parents[1]
    data_dir = repo / "EVforME?" / "Data"
    ext_dir = data_dir / "external"
    ext_dir.mkdir(parents=True, exist_ok=True)

    primary = data_dir / "vehicles.seed.nhtsa_enriched.json"
    fallback = data_dir / "vehicles.seed.json"
    input_path = primary if primary.exists() else fallback
    rows = json.loads(input_path.read_text(encoding="utf-8"))

    # query una volta per brand+model, poi applica a tutti gli anni
    pairs = sorted({(r["brand"], r["model"]) for r in rows})
    image_by_pair: dict[tuple[str, str], str | None] = {}
    hits = 0
    misses = 0

    for brand, model in pairs:
        url = fetch_wikimedia_image(brand, model)
        image_by_pair[(brand, model)] = url
        if url:
            hits += 1
        else:
            misses += 1

    updated = 0
    for r in rows:
        if r.get("imageURL"):
            continue
        url = image_by_pair.get((r["brand"], r["model"]))
        if url:
            r["imageURL"] = url
            updated += 1

    out_path = data_dir / "vehicles.seed.nhtsa_enriched.with_images.json"
    out_path.write_text(json.dumps(rows, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")

    by_brand = defaultdict(int)
    for (brand, _model), url in image_by_pair.items():
        if url:
            by_brand[brand] += 1

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "input": input_path.name,
        "output": out_path.name,
        "pair_count": len(pairs),
        "pair_hits": hits,
        "pair_misses": misses,
        "rows_updated_with_image": updated,
        "hits_by_brand": dict(sorted(by_brand.items())),
        "source": "Wikimedia Commons API",
    }
    (ext_dir / "wikimedia_image_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

