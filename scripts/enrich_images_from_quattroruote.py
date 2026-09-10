#!/usr/bin/env python3
"""
Foto “da listino” (non Wikipedia): Quattroruote → storage.edidomus.it

Per ogni brand+model unico:
  1) prova URL listino Quattroruote (slug IT + alias)
  2) se manca, match fuzzy sui modelli della marca in /listino/{marca}
  3) prende FOTO_A_16_9_1280 (foto ufficiale listino 16:9)
  4) scrive imageURL su vehicles.seed.quality.json + static API
  5) opzionale: publish CDN

Uso:
  python3 scripts/enrich_images_from_quattroruote.py
  python3 scripts/enrich_images_from_quattroruote.py --resume --limit 50
  python3 scripts/enrich_images_from_quattroruote.py --no-publish
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
import urllib.parse
from difflib import SequenceMatcher
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
QUALITY = REPO / "EVforME?" / "Data" / "vehicles.seed.quality.json"
MAP_PATH = REPO / "EVforME?" / "Data" / "external" / "vehicle_image_map_quattroruote.json"
STATIC = REPO / "api" / "static" / "vehicles.catalog.json"
STATIC_MIN = REPO / "api" / "static" / "vehicles.catalog.min.json"

DEFAULT_ICE = "https://files.catbox.moe/8adajq.jpg"
DEFAULT_EV = "https://files.catbox.moe/cqz90e.jpg"
DEFAULT_PHEV = "https://files.catbox.moe/lf33s6.jpg"

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# Foto generiche sulle pagine “listino non trovato” (sempre le stesse due).
PLACEHOLDER_IDS = {"00075293", "00075480"}

BRAND_SLUG_ALIASES: dict[str, list[str]] = {
    "mercedes-benz": ["mercedes", "mercedes-benz"],
    "mercedes benz": ["mercedes", "mercedes-benz"],
    "alfa romeo": ["alfa-romeo"],
    "land rover": ["land-rover"],
    "rolls-royce": ["rolls-royce"],
    "aston martin": ["aston-martin"],
    "ds automobiles": ["ds"],
    "ds": ["ds"],
    "citroën": ["citroen"],
    "citroen": ["citroen"],
    "škoda": ["skoda"],
    "skoda": ["skoda"],
    "volkswagen": ["volkswagen", "vw"],
    "bmw": ["bmw"],
    "mini": ["mini"],
    "tesla": ["tesla"],
}

# model catalog → slug listino QR
MODEL_SLUG_ALIASES: dict[str, list[str]] = {
    "3 series": ["serie-3", "3-series"],
    "1 series": ["serie-1"],
    "2 series": ["serie-2-coupe", "serie-2-active-tourer", "serie-2-gran-coupe"],
    "4 series": ["serie-4"],
    "5 series": ["serie-5"],
    "7 series": ["serie-7"],
    "serie 3": ["serie-3"],
    "serie 1": ["serie-1"],
    "serie 5": ["serie-5"],
    "c-class": ["classe-c"],
    "a-class": ["classe-a", "classe-a-5p"],
    "e-class": ["classe-e"],
    "s-class": ["classe-s"],
    "g-class": ["classe-g"],
    "classe c": ["classe-c"],
    "classe a": ["classe-a", "classe-a-5p"],
    "208": ["208-e-208", "208"],
    "2008": ["2008-e-2008", "2008"],
    "model 3": ["model-3"],
    "model y": ["model-y"],
    "model s": ["model-s"],
    "model x": ["model-x"],
    "500e": ["500", "500e", "nuova-500"],
    "500": ["500", "500e"],
    "megane": ["megane-e-tech", "megane", "megane-station"],
    "megane e-tech": ["megane-e-tech", "5-e-tech-electric"],
    "scenic": ["scenic-e-tech", "scenic"],
    "scenic e-tech": ["scenic-e-tech"],
    "twingo": ["twingo-e-tech-electric", "twingo"],
    "s60": ["s60", "s60-recharge"],
    "xc40 recharge": ["xc40", "ex40"],
    "c40 recharge": ["ex40", "c40"],
    "id.3": ["id3", "id-3"],
    "id.4": ["id4", "id-4"],
    "id.7": ["id7", "id-7"],
    "golf": ["golf", "golf-station"],
    "cooper": ["mini-3-porte", "mini-5-porte", "mini-all-electric"],
    "convertible": ["mini-cooper-cabrio"],
    "countryman": ["mini-countryman"],
    "ioniq 5": ["ioniq-5"],
    "ioniq 6": ["ioniq-6"],
}


def curl_text(url: str, timeout: int = 28) -> tuple[int, str]:
    try:
        out = subprocess.check_output(
            [
                "curl",
                "-sS",
                "-L",
                "-A",
                UA,
                "--max-time",
                str(timeout),
                "-w",
                "\n__HTTP__%{http_code}",
                url,
            ],
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except subprocess.CalledProcessError:
        return 0, ""
    if "__HTTP__" not in out:
        return 0, out
    body, _, code = out.rpartition("__HTTP__")
    try:
        return int(code.strip()), body
    except ValueError:
        return 0, body


def slugify(text: str) -> str:
    s = text.lower().strip()
    repl = {
        "à": "a",
        "è": "e",
        "é": "e",
        "ì": "i",
        "ò": "o",
        "ù": "u",
        "ü": "u",
        "ä": "a",
        "ö": "o",
        "ß": "ss",
        "š": "s",
        "č": "c",
        "ž": "z",
        "ñ": "n",
        "ç": "c",
    }
    for a, b in repl.items():
        s = s.replace(a, b)
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s


def pair_key(brand: str, model: str) -> str:
    return f"{brand.strip().lower()}|{model.strip().lower()}"


def brand_slugs(brand: str) -> list[str]:
    b = brand.strip().lower()
    out: list[str] = []
    for cand in BRAND_SLUG_ALIASES.get(b, []) + [slugify(brand)]:
        if cand and cand not in out:
            out.append(cand)
    return out


def model_slug_candidates(brand: str, model: str) -> list[str]:
    m = model.strip().lower()
    out: list[str] = []
    for cand in MODEL_SLUG_ALIASES.get(m, []):
        if cand not in out:
            out.append(cand)
    base = slugify(model)
    if base and base not in out:
        out.append(base)
    # BMW "3 Series" → serie-3
    if brand.strip().lower() == "bmw":
        mm = re.search(r"\b([1-8])\s*series\b", m)
        if mm:
            s = f"serie-{mm.group(1)}"
            if s not in out:
                out.insert(0, s)
    # Mercedes "C-Class" → classe-c
    if "mercedes" in brand.strip().lower():
        mm = re.search(r"\b([a-z])\s*-?\s*class\b", m)
        if mm:
            s = f"classe-{mm.group(1)}"
            if s not in out:
                out.insert(0, s)
        mm = re.search(r"\bclasse\s+([a-z0-9]+)\b", m)
        if mm:
            s = f"classe-{mm.group(1)}"
            if s not in out:
                out.insert(0, s)
    # peugeot 208 → 208-e-208
    if brand.strip().lower() == "peugeot" and re.fullmatch(r"\d{3}", base or ""):
        s = f"{base}-e-{base}"
        if s not in out:
            out.insert(0, s)
    return out


def is_placeholder(url: str) -> bool:
    m = re.search(r"/(\d+)\.JPG$", url, re.I)
    return bool(m and m.group(1) in PLACEHOLDER_IDS)


def to_1280(url: str) -> str:
    return url.replace("/FOTO_A_16_9_640/", "/FOTO_A_16_9_1280/")


def extract_listino_photos(html: str) -> list[str]:
    urls = re.findall(
        r"https://storage\.edidomus\.it/ListinoAuto/FOTO_A_16_9_(?:640|1280)/\d+\.JPG",
        html,
        re.I,
    )
    out: list[str] = []
    seen: set[str] = set()
    # prefer 1280 first
    ordered = [u for u in urls if "1280" in u] + [u for u in urls if "640" in u]
    for u in ordered:
        u2 = to_1280(u)
        if is_placeholder(u2):
            continue
        if u2 not in seen:
            seen.add(u2)
            out.append(u2)
    return out


def model_title_tokens(model: str) -> list[str]:
    """Token utili per verificare che la pagina sia del modello giusto."""
    m = model.strip().lower()
    toks = [t for t in re.split(r"[^a-z0-9]+", m) if len(t) >= 2]
    # scarta rumore generico
    stop = {"series", "serie", "class", "classe", "new", "nuova", "the"}
    return [t for t in toks if t not in stop]


def page_looks_valid(html: str, brand: str, model: str) -> bool:
    title_m = re.search(r"<title>([^<]+)", html, re.I)
    title = (title_m.group(1) if title_m else "").strip()
    if not title:
        return False
    # pagina generica listino = miss
    if re.search(r"^Listino Prezzi Automobili\s*\|", title, re.I):
        return False
    if "listino" not in title.lower():
        return False
    tl = title.lower()
    brand_tok = brand.strip().lower().split()[0]
    # brand (o prima parola) nel titolo
    if brand_tok not in tl and slugify(brand).replace("-", " ") not in tl:
        if "mercedes" in brand.lower() and "mercedes" not in tl:
            return False
        if "mercedes" not in brand.lower():
            return False
    # almeno un token del modello nel titolo (evita Giulia→Giulietta / Q4→Q6)
    tokens = model_title_tokens(model)
    if tokens:
        # richiedi il token più lungo, o almeno uno ≥3
        primary = max(tokens, key=len)
        if len(primary) >= 3 and primary not in tl:
            # eccezioni: "3 series" → titolo ha "Serie 3"
            if not any(t in tl for t in tokens if len(t) >= 3):
                # numeri corti (208, a3): ok se presenti come parola
                if not any(re.search(rf"(?<![a-z0-9]){re.escape(t)}(?![a-z0-9])", tl) for t in tokens):
                    return False
        elif len(primary) < 3:
            if not any(re.search(rf"(?<![a-z0-9]){re.escape(t)}(?![a-z0-9])", tl) for t in tokens):
                return False
    photos = extract_listino_photos(html)
    return len(photos) >= 1


def fetch_photo_from_url(url: str, brand: str, model: str) -> str | None:
    code, html = curl_text(url)
    if code != 200 or not html:
        return None
    if not page_looks_valid(html, brand, model):
        return None
    photos = extract_listino_photos(html)
    return photos[0] if photos else None


_brand_model_cache: dict[str, list[str]] = {}


def listino_models_for_brand(brand_slug: str) -> list[str]:
    if brand_slug in _brand_model_cache:
        return _brand_model_cache[brand_slug]
    code, html = curl_text(f"https://www.quattroruote.it/listino/{brand_slug}")
    slugs: list[str] = []
    if code == 200 and html:
        for path in re.findall(rf"/listino/{re.escape(brand_slug)}/([a-z0-9\-]+)", html, re.I):
            if path not in slugs:
                slugs.append(path.lower())
    _brand_model_cache[brand_slug] = slugs
    return slugs


def fuzzy_model_slug(brand_slug: str, model: str) -> list[str]:
    available = listino_models_for_brand(brand_slug)
    if not available:
        return []
    target = slugify(model)
    toks = [t for t in re.split(r"[-_\s]+", target) if len(t) > 1]
    scored: list[tuple[float, str]] = []
    for s in available:
        ratio = SequenceMatcher(None, target, s).ratio()
        # tutti i token lunghi devono comparire nello slug (evita giulia↔giulietta)
        long_toks = [t for t in toks if len(t) >= 4]
        if long_toks and not all(t in s for t in long_toks):
            continue
        bonus = sum(0.1 for t in toks if t in s)
        scored.append((ratio + bonus, s))
    scored.sort(key=lambda x: -x[0])
    return [s for score, s in scored if score >= 0.72][:3]


def fetch_quattroruote_photo(brand: str, model: str) -> str | None:
    for bslug in brand_slugs(brand):
        # 1) candidate slugs diretti
        for mslug in model_slug_candidates(brand, model):
            url = f"https://www.quattroruote.it/listino/{bslug}/{mslug}"
            photo = fetch_photo_from_url(url, brand, model)
            if photo:
                return photo
            time.sleep(0.12)
        # 2) fuzzy dalla pagina marca
        for mslug in fuzzy_model_slug(bslug, model):
            url = f"https://www.quattroruote.it/listino/{bslug}/{mslug}"
            photo = fetch_photo_from_url(url, brand, model)
            if photo:
                return photo
            time.sleep(0.12)
    return None


def default_for_powertrain(pt: str) -> str:
    if pt == "ev":
        return DEFAULT_EV
    if pt == "phev":
        return DEFAULT_PHEV
    return DEFAULT_ICE


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--resume", action="store_true", help="Continua mappa Quattroruote esistente")
    parser.add_argument("--sleep", type=float, default=0.25)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--publish", action="store_true", default=True)
    parser.add_argument("--no-publish", action="store_true")
    parser.add_argument(
        "--keep-existing-on-miss",
        action="store_true",
        default=True,
        help="Se QR manca, lascia imageURL già presente nello seed",
    )
    args = parser.parse_args()
    if args.no_publish:
        args.publish = False

    rows = json.loads(QUALITY.read_text(encoding="utf-8"))
    MAP_PATH.parent.mkdir(parents=True, exist_ok=True)
    image_map: dict[str, str | None] = {}
    if args.resume and MAP_PATH.exists():
        image_map = json.loads(MAP_PATH.read_text(encoding="utf-8"))

    pairs = sorted({(r["brand"], r["model"]) for r in rows})
    pending = [
        (b, m)
        for b, m in pairs
        if pair_key(b, m) not in image_map or not image_map.get(pair_key(b, m))
    ]
    print(f"unique_pairs={len(pairs)} pending={len(pending)} cached={len(image_map)}", flush=True)

    fetched = 0
    hits = 0
    for brand, model in pending:
        if args.limit and fetched >= args.limit:
            break
        key = pair_key(brand, model)
        url = fetch_quattroruote_photo(brand, model)
        image_map[key] = url
        fetched += 1
        if url:
            hits += 1
            print(f"[{fetched}/{len(pending)}] OK {brand} {model} -> {url}", flush=True)
        else:
            print(f"[{fetched}/{len(pending)}] MISS {brand} {model}", flush=True)
        if fetched % 8 == 0:
            MAP_PATH.write_text(json.dumps(image_map, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        time.sleep(args.sleep)

    MAP_PATH.write_text(json.dumps(image_map, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # Brand best from QR hits
    brand_best: dict[str, str] = {}
    for key, url in image_map.items():
        if not url:
            continue
        brand = key.split("|", 1)[0]
        brand_best.setdefault(brand, url)

    assigned_qr = assigned_keep = assigned_brand = assigned_default = 0
    for r in rows:
        key = pair_key(r["brand"], r["model"])
        qr = image_map.get(key)
        if qr:
            r["imageURL"] = qr
            assigned_qr += 1
            continue
        if args.keep_existing_on_miss and r.get("imageURL"):
            assigned_keep += 1
            continue
        bb = brand_best.get(r["brand"].strip().lower())
        if bb:
            r["imageURL"] = bb
            assigned_brand += 1
            continue
        r["imageURL"] = default_for_powertrain(r.get("powertrain", "ice"))
        assigned_default += 1

    QUALITY.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    compact = [{k: v for k, v in row.items() if v is not None} for row in rows]
    STATIC.parent.mkdir(parents=True, exist_ok=True)
    STATIC.write_text(json.dumps(compact, ensure_ascii=False), encoding="utf-8")
    STATIC_MIN.write_text(json.dumps(compact, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")

    print(
        json.dumps(
            {
                "rows": len(rows),
                "map_hits": sum(1 for v in image_map.values() if v),
                "map_total": len(image_map),
                "assigned_quattroruote": assigned_qr,
                "assigned_kept_previous": assigned_keep,
                "assigned_brand_fallback": assigned_brand,
                "assigned_default": assigned_default,
                "source": "quattroruote/edidomus listino 16:9",
            },
            indent=2,
        ),
        flush=True,
    )

    if args.publish:
        return subprocess.call([sys.executable, str(REPO / "scripts" / "publish_catalog_cdn.py")])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
