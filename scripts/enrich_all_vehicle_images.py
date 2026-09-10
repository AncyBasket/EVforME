#!/usr/bin/env python3
"""
Garantisce imageURL “normali” (esterno auto moderno) per ogni veicolo.

1) Wikipedia / Commons: sceglie la migliore tra più candidate (score su filename)
2) Scarta interni, loghi, diagrammi, auto d’epoca tipiche
3) Fallback marca → default ICE/EV su host stabile
4) Opzionale: upload CDN

Uso:
  python3 scripts/enrich_all_vehicle_images.py
  python3 scripts/enrich_all_vehicle_images.py --resume
  python3 scripts/enrich_all_vehicle_images.py --refresh-bad   # riscarica URL “strani”
"""

from __future__ import annotations

import argparse
import json
import re
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
QUALITY = REPO / "EVforME?" / "Data" / "vehicles.seed.quality.json"
MAP_PATH = REPO / "EVforME?" / "Data" / "external" / "vehicle_image_map.json"
STATIC = REPO / "api" / "static" / "vehicles.catalog.json"
STATIC_MIN = REPO / "api" / "static" / "vehicles.catalog.min.json"

DEFAULT_ICE = "https://files.catbox.moe/8adajq.jpg"
DEFAULT_EV = "https://files.catbox.moe/cqz90e.jpg"
DEFAULT_PHEV = "https://files.catbox.moe/lf33s6.jpg"

UA = "EVforME-catalog-images/1.1 (local enricher; contact: offline)"
CTX = ssl.create_default_context()

BAD_TOKENS = (
    "interior",
    "dashboard",
    "cockpit",
    "engine_bay",
    "enginebay",
    "badge",
    "logo",
    "emblem",
    "wordmark",
    "diagram",
    "cutaway",
    "chassis",
    "blueprint",
    "schematic",
    "icon",
    "drawing",
    "sketch",
    "cartoon",
    "illustration",
    "steering_wheel",
    "steeringwheel",
    "crash_test",
    "wreck",
    "golf_club",
    "golf_course",
    "golfer",
    "swing",
    "motorsport",
    "racing_driver",
)

# Match solo come estensione / pezzi chiari (non “seat” marca, non “motor” in MG Motor foto auto)
BAD_REGEX = (
    re.compile(r"(^|[^a-z])(engine)([^a-z]|$)"),
    re.compile(r"\.svg($|\.)"),
    re.compile(r"(^|[^a-z])(logo)([^a-z]|$)"),
)

GOOD_TOKENS = (
    "exterior",
    "front",
    "rear",
    "side",
    "three-quarter",
    "3_4",
    "34",
    "street",
    "road",
    "parked",
    "facelift",
    "sedan",
    "hatchback",
    "suv",
    "crossover",
    "coupe",
    "estate",
    "wagon",
)

# Anni tipici di auto d’epoca (nel filename, non “DSC_1920”)
OLD_YEAR_RE = re.compile(r"(?:^|_|-)(19[0-8]\d|199[0-4])(?:_|-|\.|$)")
MODERN_YEAR_RE = re.compile(r"(?:^|_|-)(20(?:1[5-9]|2[0-6]))(?:_|-|\.|$)")


def http_get_json(url: str, timeout: int = 25) -> dict | list | None:
    try:
        out = subprocess.check_output(
            [
                "curl",
                "-sS",
                "-A",
                UA,
                "-H",
                "Accept: application/json",
                "--max-time",
                str(timeout),
                url,
            ],
            text=True,
        )
        if not out.strip():
            return None
        return json.loads(out)
    except Exception:
        return None


def http_get_json_retry(url: str, retries: int = 4) -> dict | list | None:
    delay = 1.5
    for _ in range(retries):
        data = http_get_json(url)
        if data is not None:
            return data
        time.sleep(delay)
        delay *= 1.8
    return None


def clean_url(url: str | None) -> str | None:
    if not url:
        return None
    url = url.strip().split("?")[0]
    if not url.startswith("https://"):
        return None
    if "source.unsplash.com" in url:
        return None
    return url


def is_wikimedia_image(url: str) -> bool:
    host = urllib.parse.urlparse(url).netloc.lower()
    return host.endswith("wikimedia.org") or host.endswith("wikipedia.org")


def to_thumb_1280(url: str) -> str:
    url = url.split("?")[0]
    url = url.replace(
        "https://thumb.wikimedia.org/wikipedia/commons/",
        "https://upload.wikimedia.org/wikipedia/commons/",
    )
    if "/thumb/" in url and "px-" in url:
        return re.sub(r"/\d+px-", "/1280px-", url)
    return url


def filename_from_url(url: str) -> str:
    path = urllib.parse.unquote(urllib.parse.urlparse(url).path)
    name = path.rsplit("/", 1)[-1].lower()
    if name.startswith(("120px-", "220px-", "320px-", "640px-", "800px-", "1024px-", "1280px-")):
        name = name.split("-", 1)[-1]
    return name


def score_image_url(url: str | None) -> int:
    """Punteggio: più alto = più “normale”. < 0 = da scartare."""
    if not url:
        return -100
    name = filename_from_url(url)
    if not name or name.endswith(".svg"):
        return -50
    score = 10
    for tok in BAD_TOKENS:
        if tok in name:
            return -40
    for rx in BAD_REGEX:
        if rx.search(name):
            return -40
    # Loghi marchio tipici
    if "logo" in name or name.endswith(".svg.png"):
        return -40
    for tok in GOOD_TOKENS:
        if tok in name:
            score += 8
    if OLD_YEAR_RE.search(name):
        score -= 35
    if MODERN_YEAR_RE.search(name):
        score += 18
    if name.endswith((".jpg", ".jpeg", ".png", ".webp")):
        score += 4
    stem = name.rsplit(".", 1)[0]
    if len(stem) < 8:
        score -= 8
    return score


def is_acceptable_url(url: str | None, min_score: int = 0) -> bool:
    return score_image_url(url) >= min_score


def wiki_titles(brand: str, model: str) -> list[str]:
    b = brand.strip()
    m = model.strip()
    candidates = [
        f"{b} {m}",
        f"{b}_{m}".replace(" ", "_"),
        f"{m} ({b})",
        f"{b} {m} (car)",
        m,
    ]
    if b.lower() == "mercedes-benz":
        candidates.append(f"Mercedes-Benz {m}")
        candidates.append(f"Mercedes {m}")
    if b.lower() == "volkswagen":
        candidates.append(f"VW {m}")
    if "series" in m.lower():
        candidates.append(f"{b} {m.replace('Series', 'series')}")
    seen: set[str] = set()
    out: list[str] = []
    for c in candidates:
        key = c.lower()
        if key not in seen:
            seen.add(key)
            out.append(c)
    return out


def opensearch_titles(brand: str, model: str, lang: str = "en") -> list[str]:
    q = f"{brand} {model} car"
    params = {
        "action": "opensearch",
        "search": q,
        "limit": "8",
        "namespace": "0",
        "format": "json",
    }
    url = f"https://{lang}.wikipedia.org/w/api.php?" + urllib.parse.urlencode(params)
    data = http_get_json_retry(url)
    if not isinstance(data, list) or len(data) < 2:
        return []
    titles = data[1] or []
    brand_tok = brand.lower().split()[0]
    model_toks = [tok for tok in model.lower().replace("-", " ").split() if len(tok) > 1]
    scored: list[tuple[int, str]] = []
    for t in titles:
        tl = t.lower()
        if brand_tok not in tl and brand.lower() not in tl:
            continue
        # evita sport / golf club / people
        if any(x in tl for x in ("golf club", "golfer", "disambiguation", "album", "song", "film")):
            continue
        score = 0
        if brand.lower() in tl:
            score += 5
        if brand_tok in tl:
            score += 3
        score += sum(2 for tok in model_toks if tok in tl)
        if "car" in tl or "automobile" in tl or "(car)" in tl or "vehicle" in tl:
            score += 3
        scored.append((score, t))
    scored.sort(key=lambda x: -x[0])
    return [t for _, t in scored]


def page_image_candidates(title: str, lang: str) -> list[str]:
    """Thumbnail della pagina + pageimage (niente lista file lenta)."""
    enc = urllib.parse.quote(title.replace(" ", "_"), safe="()_")
    urls: list[str] = []
    summary = http_get_json_retry(f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{enc}")
    if isinstance(summary, dict) and summary.get("type") != "disambiguation":
        for key in ("originalimage", "thumbnail"):
            src = clean_url((summary.get(key) or {}).get("source"))
            if src and is_wikimedia_image(src):
                urls.append(to_thumb_1280(src))

    params = {
        "action": "query",
        "format": "json",
        "prop": "pageimages",
        "titles": title,
        "piprop": "original|thumbnail",
        "pithumbsize": "1280",
    }
    data = http_get_json_retry(f"https://{lang}.wikipedia.org/w/api.php?" + urllib.parse.urlencode(params))
    pages = ((data or {}).get("query") or {}).get("pages") or {}
    for page in pages.values():
        if "missing" in page:
            continue
        thumb = clean_url((page.get("thumbnail") or {}).get("source"))
        orig = clean_url((page.get("original") or {}).get("source"))
        for src in (orig, thumb):
            if src and is_wikimedia_image(src):
                urls.append(to_thumb_1280(src))

    seen: set[str] = set()
    out: list[str] = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


def commons_search(brand: str, model: str) -> list[str]:
    q = f"{brand} {model} automobile exterior"
    params = {
        "action": "query",
        "format": "json",
        "list": "search",
        "srsearch": q,
        "srnamespace": "6",  # File
        "srlimit": "8",
    }
    data = http_get_json_retry("https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode(params))
    results = ((data or {}).get("query") or {}).get("search") or []
    urls: list[str] = []
    for hit in results:
        title = hit.get("title") or ""
        if not title.startswith("File:"):
            continue
        fl = title.lower()
        if any(tok in fl for tok in BAD_TOKENS):
            continue
        fparams = {
            "action": "query",
            "format": "json",
            "titles": title,
            "prop": "imageinfo",
            "iiprop": "url",
            "iiurlwidth": "1280",
        }
        fdata = http_get_json_retry(
            "https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode(fparams)
        )
        pages = ((fdata or {}).get("query") or {}).get("pages") or {}
        for fp in pages.values():
            infos = fp.get("imageinfo") or []
            if not infos:
                continue
            src = clean_url(infos[0].get("thumburl") or infos[0].get("url"))
            if src and is_wikimedia_image(src):
                urls.append(to_thumb_1280(src))
        time.sleep(0.05)
    return urls


def pick_best(urls: list[str]) -> str | None:
    ranked = sorted(((score_image_url(u), u) for u in urls), key=lambda x: -x[0])
    for score, url in ranked:
        if score >= 5:
            return url
    for score, url in ranked:
        if score >= 0:
            return url
    return None


def fetch_best_image(brand: str, model: str) -> str | None:
    titles: list[str] = []
    for lang in ("en", "it"):
        titles.extend(opensearch_titles(brand, model, lang))
    titles.extend(wiki_titles(brand, model))

    candidates: list[str] = []
    seen_titles: set[str] = set()
    for title in titles:
        key = title.lower()
        if key in seen_titles:
            continue
        seen_titles.add(key)
        for lang in ("en", "it"):
            candidates.extend(page_image_candidates(title, lang))
            time.sleep(0.08)
        if pick_best(candidates):
            break

    candidates.extend(commons_search(brand, model))
    return pick_best(candidates)


def pair_key(brand: str, model: str) -> str:
    return f"{brand.strip().lower()}|{model.strip().lower()}"


def default_for_powertrain(pt: str) -> str:
    if pt == "ev":
        return DEFAULT_EV
    if pt == "phev":
        return DEFAULT_PHEV
    return DEFAULT_ICE


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--sleep", type=float, default=0.25)
    parser.add_argument("--limit", type=int, default=0, help="max new fetches (0=all)")
    parser.add_argument(
        "--refresh-bad",
        action="store_true",
        help="Riscarta URL con score basso e rifetch",
    )
    parser.add_argument(
        "--publish",
        action="store_true",
        default=True,
        help="Dopo l’enrich, pubblica e aggiorna URL app (default: sì)",
    )
    parser.add_argument("--no-publish", action="store_true")
    args = parser.parse_args()
    if args.no_publish:
        args.publish = False

    rows = json.loads(QUALITY.read_text(encoding="utf-8"))
    MAP_PATH.parent.mkdir(parents=True, exist_ok=True)

    image_map: dict[str, str | None] = {}
    if args.resume and MAP_PATH.exists():
        image_map = json.loads(MAP_PATH.read_text(encoding="utf-8"))
    elif MAP_PATH.exists() and (args.refresh_bad or args.resume):
        image_map = json.loads(MAP_PATH.read_text(encoding="utf-8"))

    # Se refresh-bad: carica mappa esistente
    if args.refresh_bad and MAP_PATH.exists():
        image_map = json.loads(MAP_PATH.read_text(encoding="utf-8"))
        bad_keys = [k for k, v in image_map.items() if not is_acceptable_url(v, min_score=5)]
        print(f"refresh_bad: clearing {len(bad_keys)} low-score entries")
        for k in bad_keys:
            image_map.pop(k, None)

    pairs = sorted({(r["brand"], r["model"]) for r in rows})
    pending = [
        (b, m)
        for b, m in pairs
        if pair_key(b, m) not in image_map or not is_acceptable_url(image_map.get(pair_key(b, m)), min_score=5)
    ]
    # Se resume senza refresh: solo missing
    if args.resume and not args.refresh_bad:
        pending = [
            (b, m)
            for b, m in pairs
            if pair_key(b, m) not in image_map or not image_map.get(pair_key(b, m))
        ]

    print(f"unique_pairs={len(pairs)} pending={len(pending)} cached={len(image_map)}")

    fetched = 0
    for brand, model in pending:
        if args.limit and fetched >= args.limit:
            break
        key = pair_key(brand, model)
        url = fetch_best_image(brand, model)
        image_map[key] = url
        fetched += 1
        sc = score_image_url(url)
        status = f"OK({sc})" if url else "MISS"
        print(f"[{fetched}/{len(pending)}] {status} {brand} {model}")
        if fetched % 5 == 0:
            MAP_PATH.write_text(json.dumps(image_map, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        time.sleep(args.sleep)

    MAP_PATH.write_text(json.dumps(image_map, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    brand_best: dict[str, tuple[int, str]] = {}
    for key, url in image_map.items():
        if not is_acceptable_url(url, min_score=5):
            continue
        brand = key.split("|", 1)[0]
        sc = score_image_url(url)
        prev = brand_best.get(brand)
        if prev is None or sc > prev[0]:
            brand_best[brand] = (sc, url)  # type: ignore[assignment]

    curated = {
        "volkswagen|golf": DEFAULT_ICE,
        "volkswagen|golf gti": DEFAULT_ICE,
        "volkswagen|golf alltrack": DEFAULT_ICE,
        "tesla|model 3": DEFAULT_EV,
        "tesla|model y": DEFAULT_PHEV,
        "fiat|500e": "https://files.catbox.moe/8zw74f.jpg",
        "fiat|500": "https://files.catbox.moe/8zw74f.jpg",
        # Esterni moderni (Commons)
        "alfa romeo|giulia": "https://upload.wikimedia.org/wikipedia/commons/thumb/3/37/2017_Alfa_Romeo_Giulia_Veloce_TB_Automatic_2.0.jpg/1280px-2017_Alfa_Romeo_Giulia_Veloce_TB_Automatic_2.0.jpg",
        "alfa romeo|giulietta": "https://upload.wikimedia.org/wikipedia/commons/thumb/7/76/2011_Alfa_Romeo_Giulietta_Veloce_JTDm-2_2.0_Front.jpg/1280px-2011_Alfa_Romeo_Giulietta_Veloce_JTDm-2_2.0_Front.jpg",
        "honda|jazz": "https://upload.wikimedia.org/wikipedia/commons/thumb/2/24/2018_Honda_Jazz_RS_%28facelift%29_%28front%29%2C_Malang.jpg/1280px-2018_Honda_Jazz_RS_%28facelift%29_%28front%29%2C_Malang.jpg",
        "mini|convertible": "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c4/Mini_Hatch_%28J01%29_Ditzingen_Mobil_IMG_9772_%28cropped%29.jpg/1280px-Mini_Hatch_%28J01%29_Ditzingen_Mobil_IMG_9772_%28cropped%29.jpg",
        "mini|cooper": "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c4/Mini_Hatch_%28J01%29_Ditzingen_Mobil_IMG_9772_%28cropped%29.jpg/1280px-Mini_Hatch_%28J01%29_Ditzingen_Mobil_IMG_9772_%28cropped%29.jpg",
        "volvo|s60": "https://upload.wikimedia.org/wikipedia/commons/thumb/d/de/Volvo_S60_%283rd_generation%29_IMG_8468.jpg/1280px-Volvo_S60_%283rd_generation%29_IMG_8468.jpg",
        "mg|mg3": "https://upload.wikimedia.org/wikipedia/commons/thumb/1/12/MG4_Electric_%E2%80%93_f_21042025.jpg/1280px-MG4_Electric_%E2%80%93_f_21042025.jpg",
        "mg|mg4": "https://upload.wikimedia.org/wikipedia/commons/thumb/1/12/MG4_Electric_%E2%80%93_f_21042025.jpg/1280px-MG4_Electric_%E2%80%93_f_21042025.jpg",
        "mg|mg5": "https://upload.wikimedia.org/wikipedia/commons/thumb/1/12/MG4_Electric_%E2%80%93_f_21042025.jpg/1280px-MG4_Electric_%E2%80%93_f_21042025.jpg",
    }
    for k, v in curated.items():
        image_map[k] = v
        brand_best[k.split("|", 1)[0]] = (100, v)

    assigned_direct = assigned_brand = assigned_default = 0
    for r in rows:
        key = pair_key(r["brand"], r["model"])
        url = clean_url(image_map.get(key))
        if is_acceptable_url(url, min_score=0):
            r["imageURL"] = url
            assigned_direct += 1
            continue
        brand_entry = brand_best.get(r["brand"].strip().lower())
        if brand_entry:
            r["imageURL"] = brand_entry[1]
            assigned_brand += 1
            continue
        r["imageURL"] = default_for_powertrain(r.get("powertrain", "ice"))
        assigned_default += 1

    assert all(r.get("imageURL") for r in rows), "coverage incomplete"

    QUALITY.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    compact = [{k: v for k, v in row.items() if v is not None} for row in rows]
    STATIC.parent.mkdir(parents=True, exist_ok=True)
    STATIC.write_text(json.dumps(compact, ensure_ascii=False), encoding="utf-8")
    STATIC_MIN.write_text(json.dumps(compact, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")

    wiki_hits = sum(1 for v in image_map.values() if is_acceptable_url(v, min_score=0))
    print(
        json.dumps(
            {
                "rows": len(rows),
                "unique_pairs": len(pairs),
                "map_hits": wiki_hits,
                "assigned_direct": assigned_direct,
                "assigned_brand_fallback": assigned_brand,
                "assigned_powertrain_default": assigned_default,
                "coverage": sum(1 for r in rows if r.get("imageURL")),
                "avg_score_sample": round(
                    sum(score_image_url(r.get("imageURL")) for r in rows[:200]) / min(200, len(rows)),
                    1,
                ),
            },
            indent=2,
        )
    )

    if args.publish:
        pub = subprocess.call([sys.executable, str(REPO / "scripts" / "publish_catalog_cdn.py")])
        if pub != 0:
            return pub
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
