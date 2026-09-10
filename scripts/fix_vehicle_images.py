#!/usr/bin/env python3
"""
Ripara imageURL del catalogo:
- rimuove source.unsplash.com (servizio morto → 503)
- applica mappa Wikimedia curata per modelli popolari
- propaga la stessa foto a tutti gli anni dello stesso brand+model
"""

from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
QUALITY = REPO / "EVforME?" / "Data" / "vehicles.seed.quality.json"
STATIC = REPO / "api" / "static" / "vehicles.catalog.json"
STATIC_MIN = REPO / "api" / "static" / "vehicles.catalog.min.json"

# Host stabile (catbox) — Wikimedia rate-limitta i client iOS.
CURATED: dict[str, str] = {
    "volkswagen|golf": "https://files.catbox.moe/8adajq.jpg",
    "volkswagen|golf gti": "https://files.catbox.moe/8adajq.jpg",
    "volkswagen|golf alltrack": "https://files.catbox.moe/8adajq.jpg",
    "volkswagen|e-golf": "https://files.catbox.moe/8adajq.jpg",
    "tesla|model 3": "https://files.catbox.moe/cqz90e.jpg",
    "tesla|model y": "https://files.catbox.moe/lf33s6.jpg",
    "tesla|model s": "https://files.catbox.moe/cqz90e.jpg",
    "fiat|500e": "https://files.catbox.moe/8zw74f.jpg",
    "fiat|500": "https://files.catbox.moe/8zw74f.jpg",
    "fiat|500x": "https://files.catbox.moe/8zw74f.jpg",
    "fiat|500l": "https://files.catbox.moe/8zw74f.jpg",
    # fallback Wikimedia (possono fallire sotto rate-limit)
    "renault|clio": "https://upload.wikimedia.org/wikipedia/commons/0/04/Renault-Clio-Tandil.jpg",
    "toyota|yaris": "https://upload.wikimedia.org/wikipedia/commons/0/07/2024_Toyota_Yaris_Hybrid_130_%28XP210%29.jpg",
    "audi|a3": "https://upload.wikimedia.org/wikipedia/commons/6/67/2024_Audi_A3_8Y_Sedan_IMG_1019.jpg",
}


def is_dead_host(url: str | None) -> bool:
    if not url:
        return False
    u = url.lower()
    return "source.unsplash.com" in u or "images.unsplash.com/featured" in u


def is_good(url: str | None) -> bool:
    if not url or is_dead_host(url):
        return False
    return url.startswith("https://")


def pair_key(brand: str, model: str) -> str:
    return f"{brand.strip().lower()}|{model.strip().lower()}"


def main() -> int:
    rows = json.loads(QUALITY.read_text(encoding="utf-8"))

    stripped = 0
    curated_hits = 0
    kept_wiki = 0

    # 1) strip dead unsplash
    for r in rows:
        url = r.get("imageURL")
        if is_dead_host(url):
            r["imageURL"] = None
            stripped += 1
        elif url and "upload.wikimedia.org" in url:
            kept_wiki += 1

    # 2) curated by brand|model
    for r in rows:
        key = pair_key(r["brand"], r["model"])
        if key in CURATED:
            r["imageURL"] = CURATED[key]
            curated_hits += 1

    # 3) propagate: best URL per brand|model across years
    best: dict[str, str] = {}
    for r in rows:
        key = pair_key(r["brand"], r["model"])
        url = r.get("imageURL")
        if is_good(url):
            best.setdefault(key, url)  # type: ignore[arg-type]
    # curated wins
    for key, url in CURATED.items():
        best[key] = url

    propagated = 0
    for r in rows:
        key = pair_key(r["brand"], r["model"])
        if key in best and r.get("imageURL") != best[key]:
            r["imageURL"] = best[key]
            propagated += 1
        elif key in best:
            r["imageURL"] = best[key]

    with_img = sum(1 for r in rows if r.get("imageURL"))
    QUALITY.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")

    compact = [{k: v for k, v in row.items() if v is not None} for row in rows]
    STATIC.parent.mkdir(parents=True, exist_ok=True)
    STATIC.write_text(json.dumps(compact, ensure_ascii=False), encoding="utf-8")
    STATIC_MIN.write_text(json.dumps(compact, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")

    # sanity on starters
    for sid in ("volkswagen-golf-2026", "tesla-model-3-2026"):
        hit = next(r for r in rows if r["id"] == sid)
        print(sid, "→", (hit.get("imageURL") or "")[:90])

    print(
        json.dumps(
            {
                "rows": len(rows),
                "stripped_unsplash": stripped,
                "curated_rows": curated_hits,
                "kept_wikimedia_before_propagate": kept_wiki,
                "propagated_updates": propagated,
                "with_image_after": with_img,
                "coverage_pct": round(100 * with_img / len(rows), 1),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
