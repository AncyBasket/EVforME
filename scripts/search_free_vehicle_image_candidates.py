#!/usr/bin/env python3
"""Search Openverse (CC0) + Wikimedia Commons (CC0/PD) for top IT vehicle image candidates.

Writes docs/image-pipeline/candidates/<id>.json with approved:false by default.
Does NOT modify the seed.

Rate-limit friendly: sleeps between requests; resume-safe (skips existing unless --force).
"""

from __future__ import annotations

import argparse
import json
import re
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

UA = "EVforME-image-pipeline/1.0 (CC0 research; local; contact: github.com/AncyBasket/EVforME)"
CTX = ssl.create_default_context()

# Licenses we accept in v1 (no CC-BY / SA — attribution UX is out of scope).
ALLOWED_LICENSES = {"cc0", "pd", "public domain", "publicdomain", "cc0 1.0", "cc-zero"}


def http_get_json(url: str, timeout: int = 35) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout, context=CTX) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (s or "").casefold()).strip()


def tokens(s: str) -> set[str]:
    stop = {"the", "a", "an", "car", "auto", "vehicle", "foto", "photo", "image", "img"}
    return {t for t in norm(s).split() if len(t) > 1 and t not in stop}


def match_score(brand: str, model: str, haystack: str) -> float:
    """Require brand + model evidence in title/filename/description."""
    h = tokens(haystack)
    b = tokens(brand)
    m = tokens(model)
    if not b or not m:
        return 0.0
    # Brand: all brand tokens must appear (handles Mercedes-Benz → mercedes benz).
    if not b.issubset(h):
        # Allow last token only for multi-word brands (e.g. Romeo for Alfa Romeo is weak — require ≥1).
        if not (b & h):
            return 0.0
        brand_hit = len(b & h) / len(b)
        if brand_hit < 0.5:
            return 0.0
    else:
        brand_hit = 1.0

    # Model: majority of model tokens (Panda, Golf, Model 3 → model + 3).
    if not m:
        return 0.0
    model_hit = len(m & h) / len(m)
    if model_hit < 0.6:
        # Single distinctive token (e.g. "Panda", "Yaris") must be present.
        distinctive = max(m, key=len)
        if distinctive not in h or len(distinctive) < 3:
            return 0.0
        model_hit = 0.6

    return round(0.45 * brand_hit + 0.55 * model_hit, 3)


def license_ok(raw: str | None) -> bool:
    if not raw:
        return False
    key = raw.strip().casefold().replace("_", " ").replace("-", " ")
    key = re.sub(r"\s+", " ", key)
    if key in ALLOWED_LICENSES:
        return True
    if "cc0" in key or "public domain" in key or key == "pd":
        # Reject if also mentions by/sa/nd (mixed strings).
        if any(x in key for x in ("by sa", "by-sa", "cc by", "attribution", "sharealike")):
            return False
        return True
    return False


def search_openverse(brand: str, model: str, year: int, sleep_s: float) -> list[dict]:
    queries = [
        f"{brand} {model} car",
        f"{brand} {model}",
        f"{brand} {model} automobile",
    ]
    # Deduplicate while preserving order.
    seen_q: set[str] = set()
    uniq_queries: list[str] = []
    for q in queries:
        if q not in seen_q:
            seen_q.add(q)
            uniq_queries.append(q)

    out: list[dict] = []
    seen_urls: set[str] = set()
    for query in uniq_queries:
        params = {
            "q": query,
            "license": "cc0",
            "page_size": "12",
            "mature": "false",
        }
        url = "https://api.openverse.org/v1/images/?" + urllib.parse.urlencode(params)
        time.sleep(sleep_s)
        try:
            data = http_get_json(url)
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            out.append({"error": f"openverse: {exc}", "query": query})
            continue

        for r in data.get("results") or []:
            title = r.get("title") or ""
            foreign = r.get("foreign_landing_url") or ""
            creator = r.get("creator") or ""
            license_raw = (r.get("license") or "").strip()
            img = r.get("url") or r.get("thumbnail") or ""
            hay = " ".join([title, r.get("id") or "", foreign, creator, img])
            score = match_score(brand, model, hay)
            if score < 0.6 or not license_ok(license_raw):
                continue
            if not img.startswith("http") or img in seen_urls:
                continue
            if img.casefold().endswith(".svg"):
                continue
            seen_urls.add(img)
            out.append(
                {
                    "source": "openverse",
                    "url": img,
                    "license": "cc0",
                    "license_raw": license_raw,
                    "author": creator or None,
                    "source_page": foreign or r.get("detail_url"),
                    "title": title,
                    "query": query,
                    "match_score": score,
                    "year_hint": year,
                }
            )
        if len(out) >= 5:
            break
    return out


def wikimedia_license_from_ext(ext: dict) -> str | None:
    # Prefer LicenseShortName / UsageTerms.
    for key in ("LicenseShortName", "License", "UsageTerms"):
        node = ext.get(key) or {}
        val = (node.get("value") if isinstance(node, dict) else None) or ""
        if val:
            return str(val)
    return None


def search_wikimedia(brand: str, model: str, year: int, sleep_s: float) -> list[dict]:
    query = f"{brand} {model}"
    params = {
        "action": "query",
        "format": "json",
        "generator": "search",
        "gsrsearch": f'filetype:bitmap {query}',
        "gsrnamespace": "6",
        "gsrlimit": "8",
        "prop": "imageinfo",
        "iiprop": "url|extmetadata|mime",
        "iiurlwidth": "1280",
    }
    url = "https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode(params)
    time.sleep(sleep_s)
    try:
        data = http_get_json(url)
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        return [{"error": f"wikimedia: {exc}", "query": query}]

    pages = (data.get("query") or {}).get("pages") or {}
    out: list[dict] = []
    for page in pages.values():
        title = page.get("title") or ""
        infos = page.get("imageinfo") or []
        if not infos:
            continue
        info = infos[0]
        mime = (info.get("mime") or "").lower()
        if mime and not mime.startswith("image/"):
            continue
        license_raw = wikimedia_license_from_ext(info.get("extmetadata") or {})
        if not license_ok(license_raw):
            continue
        img = info.get("thumburl") or info.get("url")
        if not img:
            continue
        artist_node = (info.get("extmetadata") or {}).get("Artist") or {}
        artist = artist_node.get("value") if isinstance(artist_node, dict) else None
        # Strip simple HTML from artist.
        if isinstance(artist, str):
            artist = re.sub(r"<[^>]+>", "", artist).strip() or None
        hay = f"{title} {img}"
        score = match_score(brand, model, hay)
        if score < 0.6:
            continue
        page_url = "https://commons.wikimedia.org/wiki/" + urllib.parse.quote(title.replace(" ", "_"))
        lic_norm = "cc0" if "cc0" in (license_raw or "").casefold() else "pd"
        out.append(
            {
                "source": "wikimedia",
                "url": img,
                "license": lic_norm,
                "license_raw": license_raw,
                "author": artist,
                "source_page": page_url,
                "title": title,
                "query": query,
                "match_score": score,
                "year_hint": year,
            }
        )
    return out


def build_candidate_doc(target: dict, candidates: list[dict]) -> dict:
    clean = [c for c in candidates if "error" not in c]
    errors = [c for c in candidates if "error" in c]
    clean.sort(key=lambda c: c.get("match_score") or 0, reverse=True)
    # Dedupe by URL.
    seen: set[str] = set()
    deduped: list[dict] = []
    for c in clean:
        u = c["url"]
        if u in seen:
            continue
        seen.add(u)
        deduped.append(c)
    return {
        "id": target["id"],
        "brand": target["brand"],
        "model": target["model"],
        "year": target["year"],
        "powertrain": target.get("powertrain"),
        "priority": target.get("priority"),
        "approved": False,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "candidates": deduped[:5],
        "search_errors": errors,
        "notes": "approved defaults to false; set approved:true only when brand+model are obvious.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--targets",
        type=Path,
        default=Path("docs/image-pipeline/top_it_targets.json"),
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("docs/image-pipeline/candidates"),
    )
    parser.add_argument("--limit", type=int, default=0, help="0 = all targets")
    parser.add_argument("--sleep", type=float, default=0.85)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--openverse-only", action="store_true")
    parser.add_argument(
        "--ids-file",
        type=Path,
        default=None,
        help="Optional text file with one vehicle id per line (subset of targets)",
    )
    parser.add_argument(
        "--only-empty",
        action="store_true",
        help="Re-search existing candidate files that have zero candidates (implies force for those)",
    )
    args = parser.parse_args()

    payload = json.loads(args.targets.read_text(encoding="utf-8"))
    targets = payload["targets"]
    if args.ids_file:
        wanted = {
            line.strip()
            for line in args.ids_file.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.strip().startswith("#")
        }
        targets = [t for t in targets if t["id"] in wanted]
    if args.limit > 0:
        targets = targets[: args.limit]

    args.out_dir.mkdir(parents=True, exist_ok=True)
    written = 0
    skipped = 0
    with_hits = 0

    for t in targets:
        out_path = args.out_dir / f"{t['id']}.json"
        if out_path.exists() and not args.force:
            if args.only_empty:
                existing = json.loads(out_path.read_text(encoding="utf-8"))
                if existing.get("candidates"):
                    skipped += 1
                    continue
            else:
                skipped += 1
                continue
        cands: list[dict] = []
        cands.extend(search_openverse(t["brand"], t["model"], t["year"], args.sleep))
        if not args.openverse_only:
            cands.extend(search_wikimedia(t["brand"], t["model"], t["year"], args.sleep))
        doc = build_candidate_doc(t, cands)
        out_path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        written += 1
        if doc["candidates"]:
            with_hits += 1
        print(
            f"[{t.get('priority')}] {t['id']}: {len(doc['candidates'])} candidates",
            flush=True,
        )

    print(
        json.dumps(
            {
                "written": written,
                "skipped_existing": skipped,
                "with_at_least_one_candidate": with_hits,
                "out_dir": str(args.out_dir),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
