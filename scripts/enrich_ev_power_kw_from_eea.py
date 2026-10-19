#!/usr/bin/env python3
"""
Arricchisce `powerKw` sulle EV del seed da EEA CO2 cars (`ep__KW_`).

Fonte: https://co2cars.apps.eea.europa.eu/tools/api
Campo potenza: ep__KW_ (stesso dataset da cui viene il seed WLTP).

Non scrive 0: se manca il match, lascia powerKw assente (null / chiave omessa).
"""

from __future__ import annotations

import json
import re
import ssl
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


def http_get_json(url: str, timeout: int = 90) -> dict:
    ctx = ssl.create_default_context()
    req = urllib.request.Request(url, headers={"User-Agent": "EVforME-eea-power/1.0"})
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


def norm(s: str) -> str:
    return "".join(ch for ch in s.upper() if ch.isalnum())


def model_tokens(s: str) -> list[str]:
    clean = re.sub(r"[^A-Za-z0-9]+", " ", s.upper())
    return [tok for tok in clean.split() if tok and tok not in {"THE", "NEW"}]


GENERIC_MODEL_TOKENS = {"CAR", "AUTO", "VEHICLE", "SERIES", "MODEL", "ELECTRIC", "HYBRID"}
STRICT_FUZZY_BRANDS = {
    "BMW",
    "MERCEDES",
    "MERCEDESBENZ",
    "AUDI",
    "VOLKSWAGEN",
    "TOYOTA",
    "FORD",
}


def fuzzy_score(seed_model: str, eea_model: str) -> int:
    a_raw = seed_model.upper().strip()
    b_raw = eea_model.upper().strip()
    a = norm(a_raw)
    b = norm(b_raw)
    if not a or not b:
        return -1
    if a == b:
        return 10_000
    score = 0
    if a in b or b in a:
        score += 220
    at = set(model_tokens(seed_model))
    bt = set(model_tokens(eea_model))
    common = at & bt
    if common:
        score += len(common) * 140
        score += sum(len(t) for t in common)
    if at and bt:
        union = at | bt
        score -= max(0, len(union) - len(common)) * 15
    score -= abs(len(a) - len(b)) * 2
    return score


def pick_fuzzy_match(brand_norm: str, seed_model: str, candidates: list[tuple[str, dict]]) -> dict | None:
    if not candidates:
        return None
    seed_tokens = set(model_tokens(seed_model))
    if not seed_tokens:
        return None
    best: tuple[int, dict] | None = None
    for eea_model, payload in candidates:
        eea_tokens = set(model_tokens(eea_model))
        if not eea_tokens:
            continue
        common = seed_tokens & eea_tokens
        if not common:
            continue
        if len(common) == 1:
            only = next(iter(common))
            if only in GENERIC_MODEL_TOKENS:
                continue
            if len(seed_tokens) >= 3 and len(eea_tokens) >= 3:
                continue
        if brand_norm in STRICT_FUZZY_BRANDS:
            if len(common) < 2 and not (len(seed_tokens) == 1 and len(eea_tokens) == 1):
                continue
        s = fuzzy_score(seed_model, eea_model)
        if s < 140:
            continue
        if best is None or s > best[0]:
            best = (s, payload)
    return best[1] if best else None


def eea_query(payload: dict) -> dict:
    src = urllib.parse.quote(json.dumps(payload, separators=(",", ":")))
    url = f"https://co2cars.apps.eea.europa.eu/tools/api?source={src}"
    last_exc: Exception | None = None
    for attempt in range(3):
        try:
            return http_get_json(url)
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            if attempt < 2:
                time.sleep(1.0 + attempt)
    raise RuntimeError(f"EEA query failed after retries: {last_exc}")


def get_brand_power_aggregates(brand: str) -> list[dict]:
    q = {
        "size": 0,
        "query": {"bool": {"must": [{"term": {"Mk": brand}}]}},
        "aggs": {
            "models": {
                "terms": {"field": "Cn", "size": 1200},
                "aggs": {
                    "years": {
                        "terms": {"field": "year", "size": 40},
                        "aggs": {
                            "avg_ep_kw": {"avg": {"field": "ep__KW_"}},
                        },
                    }
                },
            }
        },
    }
    data = eea_query(q)
    return data.get("aggregations", {}).get("models", {}).get("buckets", [])


def main() -> None:
    repo = Path(__file__).resolve().parents[1]
    data_dir = repo / "EVforME?" / "Data"
    path = data_dir / "vehicles.seed.quality.json"
    rows: list[dict] = json.loads(path.read_text(encoding="utf-8"))

    ev_brands = sorted({str(r["brand"]).upper() for r in rows if r.get("powertrain") == "ev"})
    lookup: dict[tuple[str, str, int], dict] = {}
    lookup_by_brand_year: dict[tuple[str, int], list[tuple[str, dict]]] = {}
    brand_ok = 0
    brand_fail = 0

    for b in ev_brands:
        try:
            buckets = get_brand_power_aggregates(b)
            brand_ok += 1
        except Exception as exc:  # noqa: BLE001
            brand_fail += 1
            print(f"brand fail {b}: {exc}")
            continue
        for model_bucket in buckets:
            model = str(model_bucket.get("key", ""))
            model_n = norm(model)
            for yb in model_bucket.get("years", {}).get("buckets", []):
                y = int(yb.get("key"))
                ep = yb.get("avg_ep_kw", {}).get("value")
                if not isinstance(ep, (int, float)) or ep <= 0:
                    continue
                payload = {"ep_kw": float(ep), "source_model": model}
                lookup[(norm(b), model_n, y)] = payload
                lookup_by_brand_year.setdefault((norm(b), y), []).append((model, payload))

    updated = 0
    skipped_no_match = 0
    for r in rows:
        if r.get("powertrain") != "ev":
            # Non forzare powerKw=0 su non-EV; rimuovi se presente vuoto.
            if r.get("powerKw") in (0, 0.0, None):
                r.pop("powerKw", None)
            continue
        brand_n = norm(str(r["brand"]))
        model_raw = str(r["model"])
        year = int(r["year"])
        hit = lookup.get((brand_n, norm(model_raw), year))
        if not hit:
            hit = pick_fuzzy_match(brand_n, model_raw, lookup_by_brand_year.get((brand_n, year), []))
        if not hit:
            r.pop("powerKw", None)
            skipped_no_match += 1
            continue
        kw = round(float(hit["ep_kw"]), 1)
        if kw <= 0:
            r.pop("powerKw", None)
            skipped_no_match += 1
            continue
        r["powerKw"] = kw
        updated += 1

    path.write_text(json.dumps(rows, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "EEA co2cars tools/api field ep__KW_",
        "ev_brands": len(ev_brands),
        "brands_ok": brand_ok,
        "brands_fail": brand_fail,
        "lookup_records": len(lookup),
        "updated_ev_rows": updated,
        "ev_rows_without_match": skipped_no_match,
    }
    (data_dir / "external" / "eea_power_kw_enrichment_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
