#!/usr/bin/env python3
"""
Arricchisce il catalogo con consumi WLTP medi da EEA CO2 cars API (pubblica).

Fonte:
- https://co2cars.apps.eea.europa.eu/tools/api

Output:
- EVforME?/Data/vehicles.seed.wltp_enriched.json
- EVforME?/Data/external/eea_wltp_enrichment_manifest.json
"""

from __future__ import annotations

import json
import ssl
import time
import urllib.parse
import urllib.request
import re
from datetime import datetime, timezone
from pathlib import Path


def http_get_json(url: str, timeout: int = 90) -> dict:
    ctx = ssl.create_default_context()
    req = urllib.request.Request(url, headers={"User-Agent": "EVforME-eea-wltp/1.0"})
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


def norm(s: str) -> str:
    return "".join(ch for ch in s.upper() if ch.isalnum())


def model_tokens(s: str) -> list[str]:
    clean = re.sub(r"[^A-Za-z0-9]+", " ", s.upper())
    return [tok for tok in clean.split() if tok and tok not in {"THE", "NEW"}]


GENERIC_MODEL_TOKENS = {
    "CAR",
    "AUTO",
    "VEHICLE",
    "SERIES",
    "MODEL",
    "ELECTRIC",
    "HYBRID",
}


STRICT_FUZZY_BRANDS = {
    # Brand con naming potenzialmente ambiguo: richiediamo vincoli piu' forti.
    "BMW",
    "MERCEDES",
    "MERCEDESBENZ",
    "AUDI",
    "VOLKSWAGEN",
    "TOYOTA",
    "FORD",
}


def fuzzy_score(seed_model: str, eea_model: str) -> int:
    """
    Score fuzzy similarity between two model labels.
    Higher is better; <= 0 means not acceptable.
    """
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
        # Penalizza mismatch troppo ampi.
        score -= max(0, len(union) - len(common)) * 15
    # Preferisci match con forma simile.
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
        # Guardrail: evita match con overlap debole.
        if not common:
            continue
        if len(common) == 1:
            only = next(iter(common))
            if only in GENERIC_MODEL_TOKENS:
                continue
            # Se i modelli hanno tanti token ma overlap minimo, scarta.
            if len(seed_tokens) >= 3 and len(eea_tokens) >= 3:
                continue
        if brand_norm in STRICT_FUZZY_BRANDS:
            # Per brand "affollati", richiedi almeno 2 token in comune o match molto corto/chiaro.
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


def get_brand_aggregates(brand: str) -> list[dict]:
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
                            "avg_fc_l100": {"avg": {"field": "Fc"}},
                            "avg_wh_km": {"avg": {"field": "z__Wh_km_"}},
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
    ext_dir = data_dir / "external"
    ext_dir.mkdir(parents=True, exist_ok=True)

    candidates = [
        data_dir / "vehicles.seed.nhtsa_enriched.with_images.json",
        data_dir / "vehicles.seed.nhtsa_enriched.json",
        data_dir / "vehicles.seed.json",
    ]
    input_path = next((p for p in candidates if p.exists()), candidates[-1])
    rows = json.loads(input_path.read_text(encoding="utf-8"))

    brands = sorted({str(r["brand"]).upper() for r in rows})
    lookup: dict[tuple[str, str, int], dict] = {}
    lookup_by_brand_year: dict[tuple[str, int], list[tuple[str, dict]]] = {}
    brand_ok = 0
    brand_fail = 0
    brand_fail_reasons: dict[str, str] = {}

    for b in brands:
        try:
            buckets = get_brand_aggregates(b)
            brand_ok += 1
        except Exception as exc:  # noqa: BLE001
            brand_fail += 1
            brand_fail_reasons[b] = str(exc)
            continue
        for model_bucket in buckets:
            model = str(model_bucket.get("key", ""))
            model_n = norm(model)
            for yb in model_bucket.get("years", {}).get("buckets", []):
                y = int(yb.get("key"))
                fc = yb.get("avg_fc_l100", {}).get("value")
                wh = yb.get("avg_wh_km", {}).get("value")
                lookup[(norm(b), model_n, y)] = {
                    "fc_l100": fc,
                    "wh_km": wh,
                    "source_model": model,
                }
                lookup_by_brand_year.setdefault((norm(b), y), []).append(
                    (
                        model,
                        {
                            "fc_l100": fc,
                            "wh_km": wh,
                            "source_model": model,
                        },
                    )
                )

    updated_ice = 0
    updated_ev = 0
    updated_with_fuzzy = 0
    no_match = 0

    for r in rows:
        brand_n = norm(str(r["brand"]))
        model_raw = str(r["model"])
        year = int(r["year"])
        key = (brand_n, norm(model_raw), year)
        hit = lookup.get(key)
        used_fuzzy = False
        if not hit:
            fuzzy_candidates = lookup_by_brand_year.get((brand_n, year), [])
            hit = pick_fuzzy_match(brand_n, model_raw, fuzzy_candidates)
            used_fuzzy = hit is not None
        if not hit:
            no_match += 1
            continue

        if r.get("powertrain") == "ice":
            fc = hit.get("fc_l100")
            if isinstance(fc, (int, float)) and fc > 0:
                r["fuelConsumptionLPerKm"] = round(float(fc) / 100.0, 4)
                updated_ice += 1
                if used_fuzzy:
                    updated_with_fuzzy += 1
        elif r.get("powertrain") == "ev":
            wh = hit.get("wh_km")
            if isinstance(wh, (int, float)) and wh > 0:
                r["energyConsumptionKWhPerKm"] = round(float(wh) / 1000.0, 4)
                updated_ev += 1
                if used_fuzzy:
                    updated_with_fuzzy += 1

    out_path = data_dir / "vehicles.seed.wltp_enriched.json"
    out_path.write_text(json.dumps(rows, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "input": input_path.name,
        "output": out_path.name,
        "brands_queried": len(brands),
        "brands_ok": brand_ok,
        "brands_fail": brand_fail,
        "lookup_records": len(lookup),
        "updated_ice_rows": updated_ice,
        "updated_ev_rows": updated_ev,
        "updated_rows_via_fuzzy_match": updated_with_fuzzy,
        "rows_without_match": no_match,
        "source": "EEA co2cars tools/api",
        "brand_fail_examples": dict(list(brand_fail_reasons.items())[:10]),
    }
    (ext_dir / "eea_wltp_enrichment_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

