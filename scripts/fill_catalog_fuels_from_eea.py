#!/usr/bin/env python3
"""
Fill / correct ICE·HEV (+ GPL/metano) catalog rows from EEA co2cars (IT).

Publish blockers 2026-10-20 (punto 4, revisione):
- Never use avg Fc.
- Consumption from enrolment-weighted WLTP CO2 via Reg. (EU) 2017/1151
  Annex XXI Sub-Annex 7 §6 (HC=CO=0), fuel-specific coefficients.
- Correct / add ICE and HEV only — never overwrite PHEV L/100 from CO2;
  never add PHEV without charge-sustaining L/100 + kWh from a real source.
- Missing ICE fuels: ≥100 IT regs and ≥3% share; reuse seed model display name.
- Bollo ICE/HEV/PHEV: national kW formula (GPL/metano marked national estimate).
- Ghosts: curated true ghosts only (after summing petrol + Fm=H for mild hybrids).

Cache: scripts/cache/eea/
Manifest: scripts/cache/eea/fill_catalog_fuels_manifest.json
"""

from __future__ import annotations

import argparse
import json
import re
import ssl
import time
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SEED_PATH = REPO / "EVforME?" / "Data" / "vehicles.seed.quality.json"
CDN_PATH = REPO / "EVforME?" / "Data" / "catalog_cdn.json"
CACHE_DIR = REPO / "scripts" / "cache" / "eea"
MANIFEST_PATH = CACHE_DIR / "fill_catalog_fuels_manifest.json"
CATALOG_SERVICE = REPO / "EVforME?" / "Core" / "Logic" / "VehicleCatalogService.swift"

# Reg. (EU) 2017/1151 Annex XXI Sub-Annex 7 §6 — simplified FC equations (HC=CO=0).
# Petrol (E10) §6.5: FC = (0.1206 / 0.745) × (0.866·HC + 0.429·CO + 0.273·CO2)
#   → CO2/FC ≈ 22.63. Density 0.745 kg/l is within Annex IX E10 band 743–756 kg/m³.
# Diesel (B7) §6.10: FC = (0.1162 / 0.834) × (0.861·HC + 0.429·CO + 0.273·CO2)
#   → CO2/FC ≈ 26.32.
# LPG / NG: same Sub-Annex 7 coefficients (pre-existing).
C_PETROL = 0.1206
C_DIESEL = 0.1162
C_LPG = 0.1212
C_NG = 0.1336
D_PETROL = 0.745  # kg/l — Annex IX petrol (E10) reference density used in §6.5
D_DIESEL = 0.834  # kg/l — B7 reference density used in §6.10
D_LPG = 0.538
D_NG = 0.654  # kg/m³
CO2_FACTOR = 0.273
PETROL_CO2_PER_L100 = D_PETROL / (C_PETROL * CO2_FACTOR)  # ≈ 22.63
DIESEL_CO2_PER_L100 = D_DIESEL / (C_DIESEL * CO2_FACTOR)  # ≈ 26.32

REFERENCE_YEAR = 2026

MILD_HYBRID_BRANDS = {
    "FIAT", "LANCIA", "SUZUKI", "OPEL", "PEUGEOT", "CITROEN", "CITROËN", "JEEP",
}

BRAND_TO_EEA_MK = {
    "CITROËN": "CITROEN",
}

# Curated true ghosts only (manual review). Do NOT auto-drop Fiat 500 MHEV, Panda CNG, etc.
TRUE_GHOST_IDS = {
    "toyota-rav4-diesel-2019",
    "toyota-rav4-diesel-2020",
    "toyota-rav4-diesel-2021",
    "opel-corsa-e-2019",
    "citroen-e-c3-2023",
    "citroën-e-c3-2023",
    # Weighted WLTP L/100 too low for charge-sustaining use; no honest CS+kWh source.
    "ford-transit-custom-phev-phev-2024",
}


def http_get_json(url: str, timeout: int = 120) -> dict:
    ctx = ssl.create_default_context()
    req = urllib.request.Request(url, headers={"User-Agent": "EVforME-eea-fill/1.1"})
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


def eea_query(payload: dict) -> dict:
    src = urllib.parse.quote(json.dumps(payload, separators=(",", ":")))
    url = f"https://co2cars.apps.eea.europa.eu/tools/api?source={src}"
    last: Exception | None = None
    for attempt in range(4):
        try:
            return http_get_json(url)
        except Exception as exc:  # noqa: BLE001
            last = exc
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"EEA query failed: {last}")


def norm_alnum(s: str) -> str:
    return "".join(ch for ch in s.upper() if ch.isalnum())


def slugify(*parts: str) -> str:
    raw = "-".join(p.strip().lower() for p in parts if p and str(p).strip())
    return re.sub(r"[^a-z0-9]+", "-", raw).strip("-")


def normalize_ft(ft: str) -> str:
    u = re.sub(r"\s+", "", str(ft).strip().upper())
    if u.startswith("NG") or u in {"CNG", "BIOMETHANE"}:
        return "NG"
    if u in {"PETROL", "DIESEL", "LPG", "ELECTRIC"}:
        return u
    if "PETROL" in u and "ELECTRIC" in u:
        return "PETROL/ELECTRIC"
    if "DIESEL" in u and "ELECTRIC" in u:
        return "DIESEL/ELECTRIC"
    return u


def co2_to_fuel_per_100km(co2_g_km: float, fuel_kind: str) -> float | None:
    if not isinstance(co2_g_km, (int, float)) or co2_g_km <= 0:
        return None
    co2 = float(co2_g_km)
    if fuel_kind == "petrol":
        return (C_PETROL / D_PETROL) * CO2_FACTOR * co2
    if fuel_kind == "diesel":
        return (C_DIESEL / D_DIESEL) * CO2_FACTOR * co2
    if fuel_kind == "lpg":
        return (C_LPG / D_LPG) * CO2_FACTOR * co2
    if fuel_kind == "cng":
        # kg/100 km (m³ densified at D_NG cancels)
        return C_NG * CO2_FACTOR * co2
    return None


def national_bollo_eur(
    kw: float | None,
    vehicle_year: int,
    fuel_kind: str | None = None,
    reference_year: int = REFERENCE_YEAR,
) -> tuple[float, str]:
    """
    National estimate: 2.58 €/kW ≤100 + 3.87 €/kW above; superbollo >185 kW with age cuts.
    GPL/metano: same national petrol-scale formula (Lazio flat 2.84 is regional — not applied here).
    Fonte: aci.it Criteri di calcolo del bollo auto (stima nazionale).
    """
    note = "national_estimate_2.58_3.87"
    if fuel_kind in ("lpg", "cng"):
        note = "national_estimate_petrol_scale_lpg_cng_lazio_would_be_2.84_flat"
    if kw is None or not isinstance(kw, (int, float)) or kw <= 0:
        return 0.0, note + "_no_kw"
    kw = float(kw)
    base = 2.58 * min(kw, 100.0) + 3.87 * max(0.0, kw - 100.0)
    if kw > 185:
        sb = 20.0 * (kw - 185.0)
        age = max(0, reference_year - vehicle_year)
        if age >= 20:
            sb = 0.0
        elif age >= 15:
            sb *= 0.15
        elif age >= 10:
            sb *= 0.30
        elif age >= 5:
            sb *= 0.60
        base += sb
    return round(base, 2), note


def cache_path(name: str) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", name)
    return CACHE_DIR / f"{safe}.json"


def load_or_fetch(cache_name: str, payload: dict, use_cache: bool) -> dict:
    path = cache_path(cache_name)
    if use_cache and path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    data = eea_query(payload)
    wrap = {
        "_query": payload,
        "_fetched_at": datetime.now(timezone.utc).isoformat(),
        "response": data,
    }
    path.write_text(json.dumps(wrap, ensure_ascii=False), encoding="utf-8")
    return wrap


def brand_payload(brand: str, hev_only: bool = False) -> dict:
    must: list[dict] = [
        {"term": {"MS": "IT"}},
        {"term": {"Mk": brand}},
        {"range": {"year": {"gte": 2017, "lte": 2025}}},
    ]
    if hev_only:
        must.append({"term": {"Fm": "H"}})
        must.append({"range": {"year": {"gte": 2020, "lte": 2025}}})
    return {
        "size": 0,
        "query": {"bool": {"must": must}},
        "aggs": {
            "models": {
                "terms": {"field": "Cn", "size": 1500},
                "aggs": {
                    "years": {
                        "terms": {"field": "year", "size": 20},
                        "aggs": {
                            "fuels": {
                                "terms": {"field": "Ft", "size": 30},
                                "aggs": {
                                    "sum_r": {"sum": {"field": "r"}},
                                    "avg_co2": {"avg": {"field": "Ewltp__g_km_"}},
                                    "avg_kw": {"avg": {"field": "ep__KW_"}},
                                },
                            }
                        },
                    }
                },
            }
        },
    }


def dedupe_fuel_buckets(fuel_buckets: list[dict]) -> dict[str, dict]:
    merged: dict[str, dict] = {}
    for fb in fuel_buckets:
        key = normalize_ft(str(fb.get("key", "")))
        if not key:
            continue
        n = float(fb.get("sum_r", {}).get("value") or fb.get("doc_count") or 0)
        co2 = fb.get("avg_co2", {}).get("value")
        kw = fb.get("avg_kw", {}).get("value")
        if key not in merged:
            merged[key] = {"n": n, "co2": co2, "kw": kw}
            continue
        prev = merged[key]
        total = prev["n"] + n
        if total > 0 and isinstance(co2, (int, float)) and isinstance(prev["co2"], (int, float)):
            prev["co2"] = (prev["co2"] * prev["n"] + float(co2) * n) / total
        elif isinstance(co2, (int, float)) and n >= prev["n"]:
            prev["co2"] = co2
        if total > 0 and isinstance(kw, (int, float)) and isinstance(prev["kw"], (int, float)):
            prev["kw"] = (prev["kw"] * prev["n"] + float(kw) * n) / total
        elif isinstance(kw, (int, float)) and n >= prev["n"]:
            prev["kw"] = kw
        prev["n"] = total
    return merged


def strip_brand_prefix(model_norm: str, brand_norm: str) -> str:
    if brand_norm and model_norm.startswith(brand_norm) and len(model_norm) > len(brand_norm):
        return model_norm[len(brand_norm) :]
    return model_norm


def parse_brand_aggs(data_wrap: dict, brand: str) -> dict[tuple[str, int, str], dict]:
    """
    (model_norm, year, ft) → {n, co2, kw, model_raw}.
    Indexes both raw Cn and brand-stripped Cn; keeps max-n cell on collision.
    """
    resp = data_wrap.get("response", data_wrap)
    brand_n = norm_alnum(brand)
    out: dict[tuple[str, int, str], dict] = {}

    def put(model_n: str, year: int, ft: str, payload: dict, model_raw: str) -> None:
        if not model_n:
            return
        key = (model_n, year, ft)
        cell = {
            "n": payload["n"],
            "co2": payload["co2"],
            "kw": payload["kw"],
            "model_raw": model_raw,
        }
        prev = out.get(key)
        if prev is None or cell["n"] > prev["n"]:
            out[key] = cell

    for mb in resp.get("aggregations", {}).get("models", {}).get("buckets", []):
        model_raw = str(mb.get("key", ""))
        model_n = norm_alnum(model_raw)
        stripped = strip_brand_prefix(model_n, brand_n)
        for yb in mb.get("years", {}).get("buckets", []):
            year = int(yb.get("key"))
            fuels = dedupe_fuel_buckets(yb.get("fuels", {}).get("buckets", []))
            for ft, payload in fuels.items():
                put(model_n, year, ft, payload, model_raw)
                if stripped != model_n:
                    put(stripped, year, ft, payload, model_raw)
    return out


_MODEL_NOISE = (
    "METANO", "CNG", "GPL", "LPG", "HYBRID", "MILDHYBRID", "PLUGIN", "PHEV",
    "ELECTRIC", "ELETTRICA", "ELETTRICO", "EV", "CLASS", "CLASSE",
)


def clean_model_norm(seed_model: str) -> str:
    sn = norm_alnum(seed_model)
    for noise in _MODEL_NOISE:
        sn = sn.replace(noise, "")
    # A-Class → A after stripping CLASS
    return sn


def match_model(seed_model: str, eea_models: set[str]) -> str | None:
    candidates = [clean_model_norm(seed_model), norm_alnum(seed_model)]
    # Keep ACLASS for Mercedes A-Class (stripping CLASS → "A" is too weak).
    raw = norm_alnum(seed_model)
    if raw in {"ACLASS", "CLASSEA"}:
        candidates = ["ACLASS", "A"] + candidates
    # Short tokens (C, 500, 911) are handled by family_eea_hit — avoid greedy substring matches.
    weak_short = {c for c in candidates if c and len(c) <= 3}
    for sn in candidates:
        if sn and sn in eea_models and sn not in weak_short:
            return sn
        if sn and sn in eea_models and sn in weak_short and sn in {"A4", "I10", "I20"}:
            return sn
    best: tuple[int, str] | None = None
    for sn in candidates:
        if not sn or len(sn) <= 2:
            continue
        for em in eea_models:
            if not em:
                continue
            if sn == em or sn in em or em in sn:
                score = min(len(sn), len(em))
                # Prefer longer seed token; among equals prefer shorter EEA key
                # (911 over 911GT3MANTHEYPERFORMANCE).
                score = score * 1000 + len(sn) * 10 - len(em)
                if best is None or score > best[0]:
                    best = (score, em)
    return best[1] if best and best[0] >= 3000 else None


def _aggregate_family_hit(
    ice_map: dict[tuple[str, int, str], dict],
    year: int,
    ft: str,
    predicate,
    label: str,
) -> dict | None:
    """Enrolment-weighted average of EEA cells matching predicate(model_norm)."""
    total_n = 0.0
    co2_acc = 0.0
    co2_n = 0.0
    kw_acc = 0.0
    kw_n = 0.0
    for (model_n, y, fuel), payload in ice_map.items():
        if y != year or fuel != ft:
            continue
        if not predicate(model_n):
            continue
        n = float(payload.get("n") or 0)
        if n <= 0:
            continue
        total_n += n
        if isinstance(payload.get("co2"), (int, float)) and float(payload["co2"]) > 0:
            co2_acc += float(payload["co2"]) * n
            co2_n += n
        if isinstance(payload.get("kw"), (int, float)) and float(payload["kw"]) > 0:
            kw_acc += float(payload["kw"]) * n
            kw_n += n
    if total_n < 100:
        return None
    # Require enough regs with CO2 so missing-Ewltp cells cannot dilute the average.
    if co2_n < 100:
        return None
    return {
        "n": total_n,
        "co2": co2_acc / co2_n,
        "kw": (kw_acc / kw_n) if kw_n > 0 else None,
        "model_raw": label,
    }


def mercedes_a_class_diesel_hit(
    ice_map: dict[tuple[str, int, str], dict], year: int
) -> dict | None:
    """Aggregate Mercedes A 180 D / A 200 D / … diesel cells for seed model A-Class."""
    return _aggregate_family_hit(
        ice_map,
        year,
        "DIESEL",
        lambda m: bool(re.match(r"^A\d{2,3}D", m)),
        "A-Class",
    )


def mercedes_c_class_diesel_hit(
    ice_map: dict[tuple[str, int, str], dict], year: int
) -> dict | None:
    """C 200 D / C 220 D / … — exclude GLC/CLA/CLE prefixes."""
    return _aggregate_family_hit(
        ice_map,
        year,
        "DIESEL",
        lambda m: bool(re.match(r"^C\d{2,3}D", m)),
        "C-Class",
    )


def audi_a4_diesel_hit(
    ice_map: dict[tuple[str, int, str], dict], year: int
) -> dict | None:
    """A4 / A4 AVANT / LIMOUSINE / ALLROAD (not A40/A41…)."""
    return _aggregate_family_hit(
        ice_map,
        year,
        "DIESEL",
        lambda m: m == "A4"
        or (m.startswith("A4") and not m.startswith("A40") and not m.startswith("A41"))
        or m in {"AUDIA4", "AUDIA4AVANT"},
        "A4",
    )


def bmw_3_series_diesel_hit(
    ice_map: dict[tuple[str, int, str], dict], year: int
) -> dict | None:
    """320d / 330d family; exclude X3 20D etc."""
    return _aggregate_family_hit(
        ice_map,
        year,
        "DIESEL",
        lambda m: bool(re.match(r"^3[0-9]{2}D", m)),
        "3-Series",
    )


def porsche_911_petrol_hit(
    ice_map: dict[tuple[str, int, str], dict], year: int
) -> dict | None:
    return _aggregate_family_hit(
        ice_map,
        year,
        "PETROL",
        lambda m: m.startswith("911") or m.startswith("991"),
        "911",
    )


def mercedes_500_petrol_hit(
    ice_map: dict[tuple[str, int, str], dict], year: int
) -> dict | None:
    """Seed model '500' → S 500 / G 500 ICE (not EQ*)."""
    return _aggregate_family_hit(
        ice_map,
        year,
        "PETROL",
        lambda m: bool(re.match(r"^(S|G)500", m)),
        "500",
    )


def family_eea_hit(
    brand_u: str,
    model_raw: str,
    year: int,
    ft: str,
    ice_map: dict[tuple[str, int, str], dict],
) -> dict | None:
    """Special family aggregations when seed names don't match EEA Cn tokens."""
    raw = norm_alnum(model_raw)
    clean = clean_model_norm(model_raw)
    if brand_u == "MERCEDES-BENZ":
        if raw in {"ACLASS", "CLASSEA"} and ft == "DIESEL":
            return mercedes_a_class_diesel_hit(ice_map, year)
        if raw in {"CCLASS", "CLASSEC"} or clean == "C":
            if ft == "DIESEL":
                return mercedes_c_class_diesel_hit(ice_map, year)
        if raw == "500" or clean == "500":
            if ft == "PETROL":
                return mercedes_500_petrol_hit(ice_map, year)
    if brand_u == "AUDI" and (raw == "A4" or clean == "A4") and ft == "DIESEL":
        return audi_a4_diesel_hit(ice_map, year)
    if brand_u == "BMW" and (raw in {"3SERIES", "SERIES3"} or clean == "3SERIES") and ft == "DIESEL":
        return bmw_3_series_diesel_hit(ice_map, year)
    if brand_u == "PORSCHE" and (raw == "911" or clean == "911") and ft == "PETROL":
        return porsche_911_petrol_hit(ice_map, year)
    return None


def bifuel_alias_hit(
    ice_map: dict[tuple[str, int, str], dict],
    model_n: str,
    year: int,
    ft: str,
) -> dict | None:
    """Prefer BI-FUEL / BIFUEL sibling cells when the base model lacks CO2 (e.g. i10 LPG)."""
    direct = ice_map.get((model_n, year, ft))
    if direct and isinstance(direct.get("co2"), (int, float)) and direct.get("co2"):
        return direct
    for suffix in ("BIFUEL", "BIFUEL", "BIFUELLPG"):
        alt = ice_map.get((model_n + "BIFUEL", year, ft)) or ice_map.get((model_n + suffix, year, ft))
        if alt and float(alt.get("n") or 0) >= 100:
            if direct:
                # Merge n; prefer alt CO2/kW
                return {
                    "n": float(direct.get("n") or 0) + float(alt.get("n") or 0),
                    "co2": alt.get("co2") if isinstance(alt.get("co2"), (int, float)) else direct.get("co2"),
                    "kw": alt.get("kw") if isinstance(alt.get("kw"), (int, float)) else direct.get("kw"),
                    "model_raw": alt.get("model_raw") or direct.get("model_raw"),
                }
            return alt
    return direct


def seed_fuel_ft(row: dict) -> str | None:
    pt = (row.get("powertrain") or "").lower()
    fk = (row.get("fuelKind") or "").lower()
    if pt == "ev":
        return "ELECTRIC"
    if pt == "phev":
        return "DIESEL/ELECTRIC" if fk == "diesel" else "PETROL/ELECTRIC"
    if pt == "hev":
        return "DIESEL" if fk == "diesel" else "PETROL"
    return {"petrol": "PETROL", "diesel": "DIESEL", "lpg": "LPG", "cng": "NG"}.get(fk)


def effective_petrol_n(
    brand_u: str,
    model_n: str,
    year: int,
    ice_maps: dict,
    hev_maps: dict,
) -> float:
    """Petrol ICE regs + Fm=H petrol (mild hybrid bucket) for the same model/year."""
    ice = ice_maps.get(brand_u, {}).get((model_n, year, "PETROL"), {})
    hev = hev_maps.get(brand_u, {}).get((model_n, year, "PETROL"), {})
    return float(ice.get("n") or 0) + float(hev.get("n") or 0)


def bump_seed_version(new_version: int) -> None:
    cdn = json.loads(CDN_PATH.read_text(encoding="utf-8"))
    cdn["seedVersion"] = new_version
    cdn["note"] = (
        f"seedVersion {new_version}: EEA IT ICE/HEV fuels+consumptions+bollo "
        "(no Fc; CO2→FC Reg. 2017/1151 fuel-specific; no PHEV CO2 overwrite; curated ghosts)."
    )
    CDN_PATH.write_text(json.dumps(cdn, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    text = CATALOG_SERVICE.read_text(encoding="utf-8")
    text2, n = re.subn(
        r"static let bundledSeedVersion = \d+",
        f"static let bundledSeedVersion = {new_version}",
        text,
        count=1,
    )
    if n != 1:
        # fallback older private let
        text2, n = re.subn(
            r"private let seedVersion = \d+",
            f"private let seedVersion = {new_version}",
            text,
            count=1,
        )
    if n != 1:
        raise RuntimeError("Could not bump seedVersion in VehicleCatalogService.swift")
    CATALOG_SERVICE.write_text(text2, encoding="utf-8")


def display_model_for_family(seed_rows: list[dict], brand_u: str, model_n: str) -> str | None:
    """Prefer an existing seed model string for this family (e.g. Tonale not TONALE)."""
    for r in seed_rows:
        if str(r.get("brand", "")).upper() != brand_u:
            continue
        if clean_model_norm(str(r.get("model", ""))) == model_n or norm_alnum(str(r.get("model", ""))) == model_n:
            return str(r.get("model"))
    return None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-cache", action="store_true")
    parser.add_argument("--brands", nargs="*")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--seed-version", type=int, default=39)
    args = parser.parse_args()
    use_cache = not args.no_cache

    rows: list[dict] = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    seed_brands = sorted({str(r.get("brand", "")).upper() for r in rows if r.get("brand")})
    if args.brands:
        seed_brands = [b.upper() for b in args.brands]

    def eea_mk(brand: str) -> str:
        return BRAND_TO_EEA_MK.get(brand, brand)

    ice_maps: dict[str, dict[tuple[str, int, str], dict]] = {}
    hev_maps: dict[str, dict[tuple[str, int, str], dict]] = {}
    query_log: list[dict] = []

    for brand in seed_brands:
        mk = eea_mk(brand)
        print(f"EEA fetch {brand} (Mk={mk})…")
        wrap = load_or_fetch(f"IT_{mk}_fuels", brand_payload(mk, hev_only=False), use_cache)
        ice_maps[brand] = parse_brand_aggs(wrap, mk)
        query_log.append({"brand": brand, "eea_mk": mk, "kind": "all", "records": len(ice_maps[brand])})
        wrap_h = load_or_fetch(f"IT_{mk}_hev_FmH", brand_payload(mk, hev_only=True), use_cache)
        hev_maps[brand] = parse_brand_aggs(wrap_h, mk)
        query_log.append({"brand": brand, "eea_mk": mk, "kind": "hev_FmH", "records": len(hev_maps[brand])})

    family_totals: dict[tuple[str, str, int], dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for brand, mp in ice_maps.items():
        for (model_n, year, ft), payload in mp.items():
            family_totals[(brand, model_n, year)][ft] += float(payload["n"])

    corrections: list[dict] = []
    additions: list[dict] = []
    bollo_updates: list[dict] = []
    mild_trim: list[dict] = []
    skipped_no_co2 = 0
    phev_bollo_only = 0

    # --- Correct ICE/HEV consumptions; bollo for ICE/HEV/PHEV; never PHEV L/100 from CO2 ---
    for r in rows:
        brand_u = str(r.get("brand", "")).upper()
        if brand_u not in ice_maps:
            continue
        pt = (r.get("powertrain") or "").lower()
        if pt == "ev":
            continue
        model_raw = str(r.get("model", ""))
        year = int(r.get("year") or 0)
        fk = (r.get("fuelKind") or "").lower()
        eea_models = {k[0] for k in ice_maps[brand_u]}
        if brand_u == "MERCEDES-BENZ" and norm_alnum(model_raw) in {"ACLASS", "CLASSEA"}:
            model_n = "ACLASS"
        else:
            model_n = match_model(model_raw, eea_models)
        # Family aggregations (C-Class, A4, 3-Series, 911, Mercedes 500) may have no Cn match.
        want_preview = None
        if pt == "hev":
            want_preview = "DIESEL" if fk == "diesel" else "PETROL"
        elif pt == "ice":
            want_preview = {"petrol": "PETROL", "diesel": "DIESEL", "lpg": "LPG", "cng": "NG"}.get(fk)
        family_preview = (
            family_eea_hit(brand_u, model_raw, year, want_preview, ice_maps[brand_u])
            if want_preview
            else None
        )
        if not model_n and not family_preview:
            if pt == "phev" and float(r.get("taxesPerYear") or 0) == 90:
                r["taxesPerYear"] = 0
                bollo_updates.append({"id": r.get("id"), "from": 90, "to": 0, "reason": "strip_flat_90_no_match"})
            continue
        if not model_n and family_preview:
            model_n = clean_model_norm(model_raw) or norm_alnum(model_raw)

        hit = None
        source_ft = ""

        if pt == "hev":
            want = "DIESEL" if fk == "diesel" else "PETROL"
            hit = family_eea_hit(brand_u, model_raw, year, want, ice_maps[brand_u])
            if not hit:
                hit = hev_maps.get(brand_u, {}).get((model_n, year, want)) or ice_maps[brand_u].get(
                    (model_n, year, want)
                )
            source_ft = want
            if brand_u in MILD_HYBRID_BRANDS and not (brand_u == "JEEP" and year >= 2024):
                if (r.get("trim") or "") != "Mild Hybrid":
                    mild_trim.append({"id": r.get("id"), "year": year})
                    r["trim"] = "Mild Hybrid"
        elif pt == "phev":
            want = "DIESEL/ELECTRIC" if fk == "diesel" else "PETROL/ELECTRIC"
            hit = ice_maps[brand_u].get((model_n, year, want))
            source_ft = want
        else:
            want = {"petrol": "PETROL", "diesel": "DIESEL", "lpg": "LPG", "cng": "NG"}.get(fk)
            if not want:
                continue
            hit = family_eea_hit(brand_u, model_raw, year, want, ice_maps[brand_u])
            if not hit and model_n:
                hit = bifuel_alias_hit(ice_maps[brand_u], model_n, year, want)
            source_ft = want or ""

        if not hit:
            if pt == "phev" and float(r.get("taxesPerYear") or 0) == 90:
                r["taxesPerYear"] = 0
                bollo_updates.append({"id": r.get("id"), "from": 90, "to": 0, "reason": "strip_flat_90_no_eea"})
            continue

        hit_n = float(hit["n"])
        kw = hit.get("kw")
        fuel_for_tax = fk if fk in ("petrol", "diesel", "lpg", "cng") else "petrol"
        new_tax, tax_note = national_bollo_eur(
            kw if isinstance(kw, (int, float)) else None, year, fuel_kind=fuel_for_tax
        )
        old_tax = float(r.get("taxesPerYear") or 0)
        if new_tax <= 0:
            if old_tax == 90 or (old_tax > 0 and pt in ("phev", "hev", "ice")):
                if old_tax != 0:
                    bollo_updates.append({"id": r.get("id"), "from": old_tax, "to": 0, "reason": tax_note})
                r["taxesPerYear"] = 0
        elif abs(new_tax - old_tax) > 0.5 or old_tax == 90:
            bollo_updates.append(
                {"id": r.get("id"), "from": old_tax, "to": new_tax, "kw": kw, "note": tax_note, "ft": source_ft}
            )
            r["taxesPerYear"] = new_tax

        # Consumption: ICE + HEV only, n≥100, >20% delta
        if pt == "phev":
            phev_bollo_only += 1
            continue
        if hit_n < 100:
            continue
        fuel_for_fc = fk if fk in ("petrol", "diesel", "lpg", "cng") else "petrol"
        fc100 = co2_to_fuel_per_100km(hit.get("co2"), fuel_for_fc)
        if fc100 is None:
            skipped_no_co2 += 1
            continue
        new_l_per_km = round(fc100 / 100.0, 5)
        old = r.get("fuelConsumptionLPerKm")
        # Always refresh from EEA CO2 when n≥100 (propagates coefficient changes; CNG kg/100 too).
        old_l100 = round(float(old) * 100, 3) if isinstance(old, (int, float)) and old > 0 else None
        if old_l100 is None or abs(new_l_per_km - float(old)) > 1e-6 or not str(
            r.get("sourceName") or ""
        ).startswith("EEA co2cars"):
            corrections.append(
                {
                    "id": r.get("id"),
                    "brand": brand_u,
                    "model": model_raw,
                    "year": year,
                    "fuel": fk,
                    "old_l100": old_l100,
                    "new_l100": round(fc100, 3),
                    "co2": hit.get("co2"),
                    "n": hit_n,
                    "eea_model": model_n,
                }
            )
            r["fuelConsumptionLPerKm"] = new_l_per_km
            if isinstance(hit.get("co2"), (int, float)):
                r["co2gKm"] = int(round(float(hit["co2"])))
            r["sourceName"] = f"EEA co2cars IT {year} n={int(hit_n)}"
            r["confidenceScore"] = 0.8
            r["sourceUpdatedAt"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    for r in rows:
        if (r.get("powertrain") or "").lower() == "phev" and float(r.get("taxesPerYear") or 0) == 90:
            r["taxesPerYear"] = 0
            bollo_updates.append({"id": r.get("id"), "from": 90, "to": 0, "reason": "strip_remaining_flat_90"})

    # --- Add missing ICE fuels (not PHEV/EV) ---
    existing_fuel_keys: set[tuple[str, str, int, str]] = set()
    for r in rows:
        brand_u = str(r.get("brand", "")).upper()
        mn = clean_model_norm(str(r.get("model", ""))) or norm_alnum(str(r.get("model", "")))
        y = int(r.get("year") or 0)
        ft = seed_fuel_ft(r)
        if ft and (r.get("powertrain") or "").lower() in ("ice", "hev"):
            existing_fuel_keys.add((brand_u, mn, y, ft))

    ft_to_seed = {
        "PETROL": ("petrol", "ice"),
        "DIESEL": ("diesel", "ice"),
        "LPG": ("lpg", "ice"),
        "NG": ("cng", "ice"),
    }

    for (brand_u, model_n, year), fuels in family_totals.items():
        # Avoid double-counting brand-prefixed aliases: only act on stripped keys
        # if a longer prefixed key exists with same year — skip duplicate model_n
        # that still start with brand when stripped sibling exists.
        total = sum(fuels.values())
        if total < 100:
            continue
        display_model = display_model_for_family(rows, brand_u, model_n)
        if not display_model and model_n.endswith("BIFUEL"):
            display_model = display_model_for_family(rows, brand_u, model_n.replace("BIFUEL", ""))
        if not display_model:
            # Skip EEA-only commercial names with no seed family (prevents TONALE clones).
            continue
        tmpl = next(
            (
                r
                for r in rows
                if str(r.get("brand", "")).upper() == brand_u
                and (r.get("powertrain") or "").lower() in ("ice", "hev")
                and "phev" not in str(r.get("model", "")).lower()
                and (
                    clean_model_norm(str(r.get("model", ""))) == model_n
                    or norm_alnum(str(r.get("model", ""))) == model_n
                    or (
                        model_n.endswith("BIFUEL")
                        and clean_model_norm(str(r.get("model", ""))) == model_n.replace("BIFUEL", "")
                    )
                )
            ),
            None,
        )
        if not tmpl:
            continue
        # Map I10BIFUEL → seed family i10
        family_model_n = clean_model_norm(display_model) or norm_alnum(display_model)
        if model_n.endswith("BIFUEL"):
            family_model_n = model_n.replace("BIFUEL", "") or family_model_n

        for ft, n in fuels.items():
            if ft not in ft_to_seed:
                continue
            if n < 100 or (n / total) < 0.03:
                continue
            fuel_kind, powertrain = ft_to_seed[ft]
            family_key = (brand_u, family_model_n, year, ft)
            if family_key in existing_fuel_keys:
                continue
            # Also skip if any row already has this fuel for brand/model/year
            already = any(
                str(x.get("brand", "")).upper() == brand_u
                and int(x.get("year") or 0) == year
                and (x.get("fuelKind") or "").lower() == fuel_kind
                and (x.get("powertrain") or "").lower() == "ice"
                and (
                    clean_model_norm(str(x.get("model", ""))) == family_model_n
                    or norm_alnum(str(x.get("model", ""))) == family_model_n
                )
                for x in rows
            )
            if already:
                continue

            if brand_u == "MERCEDES-BENZ" and family_model_n in {"ACLASS", "A"} and ft == "DIESEL":
                hit = mercedes_a_class_diesel_hit(ice_maps[brand_u], year)
            else:
                hit = bifuel_alias_hit(ice_maps[brand_u], family_model_n, year, ft)
            if not hit:
                continue
            n = float(hit.get("n") or n)
            if n < 100:
                continue
            fc100 = co2_to_fuel_per_100km(hit.get("co2"), fuel_kind)
            if fc100 is None:
                skipped_no_co2 += 1
                continue
            taxes, tax_note = national_bollo_eur(
                hit.get("kw") if isinstance(hit.get("kw"), (int, float)) else None,
                year,
                fuel_kind=fuel_kind,
            )
            new_id = slugify(str(tmpl.get("brand")), display_model, fuel_kind, str(year))
            existing_ids = {str(x.get("id")) for x in rows}
            base_id = new_id
            suffix = 2
            while new_id in existing_ids:
                new_id = f"{base_id}-{suffix}"
                suffix += 1

            new_row = {
                "id": new_id,
                "brand": tmpl.get("brand"),
                "model": display_model,  # seed casing, never EEA TONALE
                "year": year,
                "trim": "Natural Power" if fuel_kind == "cng" and "panda" in display_model.lower() else (tmpl.get("trim") or ""),
                "powertrain": powertrain,
                "fuelKind": fuel_kind,
                "market": tmpl.get("market") or "IT",
                "fuelConsumptionLPerKm": round(fc100 / 100.0, 5),
                "energyConsumptionKWhPerKm": None,
                "wltpConsumptionKWh100km": None,
                "wltpRangeKm": None,
                "batteryKWh": None,
                "co2gKm": int(round(float(hit["co2"]))) if isinstance(hit.get("co2"), (int, float)) else None,
                "taxesPerYear": taxes,
                "maintenancePerYear": tmpl.get("maintenancePerYear") or 0,
                "lengthM": tmpl.get("lengthM"),
                "widthM": tmpl.get("widthM"),
                "heightM": tmpl.get("heightM"),
                "imageURL": None,
                "sourceName": f"EEA co2cars IT {year} n={int(n)}",
                "sourceUpdatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                "confidenceScore": 0.8,
            }
            rows.append(new_row)
            existing_fuel_keys.add(family_key)
            additions.append(
                {
                    "id": new_id,
                    "brand": brand_u,
                    "model": display_model,
                    "year": year,
                    "ft": ft,
                    "n": n,
                    "share": round(n / total, 4),
                    "l100": round(fc100, 3),
                    "taxes": taxes,
                    "tax_note": tax_note,
                }
            )

    # Mercedes A-Class diesel: EEA uses A 180 D / A 200 D / … — aggregate into seed "A-Class".
    mb_brand = "MERCEDES-BENZ"
    if mb_brand in ice_maps:
        a_tmpl = next(
            (
                r
                for r in rows
                if str(r.get("brand", "")).upper() == mb_brand
                and norm_alnum(str(r.get("model", ""))) in {"ACLASS", "CLASSEA"}
                and (r.get("powertrain") or "").lower() == "ice"
            ),
            None,
        )
        if a_tmpl:
            for year in range(2017, 2026):
                if any(
                    str(x.get("brand", "")).upper() == mb_brand
                    and norm_alnum(str(x.get("model", ""))) in {"ACLASS", "CLASSEA"}
                    and int(x.get("year") or 0) == year
                    and (x.get("fuelKind") or "").lower() == "diesel"
                    for x in rows
                ):
                    continue
                hit = mercedes_a_class_diesel_hit(ice_maps[mb_brand], year)
                if not hit:
                    continue
                fc100 = co2_to_fuel_per_100km(hit.get("co2"), "diesel")
                if fc100 is None:
                    skipped_no_co2 += 1
                    continue
                taxes, tax_note = national_bollo_eur(
                    hit.get("kw") if isinstance(hit.get("kw"), (int, float)) else None,
                    year,
                    fuel_kind="diesel",
                )
                new_id = slugify("Mercedes-Benz", "A-Class", "diesel", str(year))
                existing_ids = {str(x.get("id")) for x in rows}
                base_id = new_id
                suffix = 2
                while new_id in existing_ids:
                    new_id = f"{base_id}-{suffix}"
                    suffix += 1
                rows.append(
                    {
                        "id": new_id,
                        "brand": a_tmpl.get("brand"),
                        "model": "A-Class",
                        "year": year,
                        "trim": a_tmpl.get("trim") or "",
                        "powertrain": "ice",
                        "fuelKind": "diesel",
                        "market": a_tmpl.get("market") or "IT",
                        "fuelConsumptionLPerKm": round(fc100 / 100.0, 5),
                        "energyConsumptionKWhPerKm": None,
                        "wltpConsumptionKWh100km": None,
                        "wltpRangeKm": None,
                        "batteryKWh": None,
                        "co2gKm": int(round(float(hit["co2"]))) if isinstance(hit.get("co2"), (int, float)) else None,
                        "taxesPerYear": taxes,
                        "maintenancePerYear": a_tmpl.get("maintenancePerYear") or 0,
                        "lengthM": a_tmpl.get("lengthM"),
                        "widthM": a_tmpl.get("widthM"),
                        "heightM": a_tmpl.get("heightM"),
                        "imageURL": None,
                        "sourceName": f"EEA co2cars IT {year} n={int(hit['n'])}",
                        "sourceUpdatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                        "confidenceScore": 0.8,
                    }
                )
                additions.append(
                    {
                        "id": new_id,
                        "brand": mb_brand,
                        "model": "A-Class",
                        "year": year,
                        "ft": "DIESEL",
                        "n": hit["n"],
                        "l100": round(fc100, 3),
                        "taxes": taxes,
                        "tax_note": tax_note,
                        "aggregated": "A*D",
                    }
                )

    # --- Ghost candidates (informational) + curated removals only ---
    ghost_candidates: list[dict] = []
    for r in rows:
        brand_u = str(r.get("brand", "")).upper()
        if brand_u not in ice_maps:
            continue
        year = int(r.get("year") or 0)
        eea_models = {k[0] for k in ice_maps[brand_u]}
        model_n = match_model(str(r.get("model", "")), eea_models)
        if not model_n:
            continue
        fam = family_totals.get((brand_u, model_n, year), {})
        fam_total = sum(fam.values())
        if fam_total < 1000:
            continue
        ft = seed_fuel_ft(r)
        pt = (r.get("powertrain") or "").lower()
        if ft == "PETROL" and pt in ("ice", "hev"):
            n = effective_petrol_n(brand_u, model_n, year, ice_maps, hev_maps)
        elif ft:
            n = float(fam.get(ft, 0))
        else:
            continue
        if n < 50:
            ghost_candidates.append(
                {
                    "id": r.get("id"),
                    "brand": brand_u,
                    "model": r.get("model"),
                    "year": year,
                    "ft": ft,
                    "n": n,
                    "family_n": fam_total,
                    "protected": r.get("id") not in TRUE_GHOST_IDS
                    and not any(
                        (r.get("id") or "").startswith(g.replace("-2019", "").replace("-2020", "").replace("-2021", "").replace("-2023", ""))
                        for g in TRUE_GHOST_IDS
                    ),
                }
            )

    removed: list[dict] = []
    remove_ids = set()
    for r in rows:
        rid = str(r.get("id") or "")
        rid_l = rid.lower()
        brand_u = str(r.get("brand", "")).upper()
        model_l = str(r.get("model", "")).lower()
        year = int(r.get("year") or 0)
        fk = (r.get("fuelKind") or "").lower()
        pt = (r.get("powertrain") or "").lower()
        if rid in TRUE_GHOST_IDS or rid_l in TRUE_GHOST_IDS:
            remove_ids.add(rid)
            continue
        # RAV4 diesel 2019–2021 (ids are often toyota-rav4-2019 without -diesel-)
        if brand_u == "TOYOTA" and "rav4" in model_l and fk == "diesel" and year in (2019, 2020, 2021):
            remove_ids.add(rid)
        if re.match(r"opel-corsa-e-2019|opel-corsa.*electric-2019", rid_l) or (
            brand_u == "OPEL" and "corsa" in model_l and pt == "ev" and year == 2019
        ):
            remove_ids.add(rid)
        if re.match(r"citro[eë]n-e-c3-2023|citro[eë]n-ec3-2023", rid_l) or (
            brand_u in {"CITROEN", "CITROËN"} and re.search(r"e-?c3", model_l) and year == 2023 and pt == "ev"
        ):
            remove_ids.add(rid)

    if remove_ids:
        kept = []
        for r in rows:
            if r.get("id") in remove_ids:
                removed.append({"id": r.get("id"), "brand": r.get("brand"), "model": r.get("model"), "year": r.get("year")})
            else:
                kept.append(r)
        rows = kept

    # Unify brand casing Mini → MINI (single family in picker).
    for r in rows:
        if str(r.get("brand", "")) == "Mini":
            r["brand"] = "MINI"

    # Panda metano 2018 bollo was out of line (~113 vs ~160): same national kW formula as peers.
    panda_kw = None
    for r in rows:
        if (
            str(r.get("brand", "")).upper() == "FIAT"
            and str(r.get("model", "")).lower() == "panda"
            and (r.get("fuelKind") or "").lower() == "cng"
            and int(r.get("year") or 0) in (2019, 2020, 2021, 2022)
        ):
            # Back-calc kW from taxes ≈ 2.58 * kw when kw ≤ 100.
            tax = float(r.get("taxesPerYear") or 0)
            if tax > 100:
                panda_kw = tax / 2.58
                break
    if panda_kw:
        for r in rows:
            if (
                str(r.get("brand", "")).upper() == "FIAT"
                and str(r.get("model", "")).lower() == "panda"
                and (r.get("fuelKind") or "").lower() == "cng"
                and int(r.get("year") or 0) == 2018
            ):
                new_tax, note = national_bollo_eur(panda_kw, 2018, fuel_kind="cng")
                old = float(r.get("taxesPerYear") or 0)
                if abs(new_tax - old) > 0.5:
                    bollo_updates.append(
                        {"id": r.get("id"), "from": old, "to": new_tax, "kw": panda_kw, "note": note + "_panda_2018_align"}
                    )
                    r["taxesPerYear"] = new_tax

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "https://co2cars.apps.eea.europa.eu/tools/api",
        "filter": {"MS": "IT", "years": "2017-2025", "Mk": "uppercase"},
        "aggregation": "Cn→year→Ft; sum r; avg Ewltp; avg ep__KW_; no Fc; brand-stripped Cn aliases",
        "co2_to_fc": {
            "regulation": "Reg. (EU) 2017/1151 Annex XXI Sub-Annex 7 §6 (HC=CO=0)",
            "reference_fuels": "Petrol (E10) §6.5; Diesel (B7) §6.10; densities Annex IX",
            "petrol": {
                "CF": C_PETROL,
                "D": D_PETROL,
                "approx": f"CO2/{PETROL_CO2_PER_L100:.2f}",
                "co2_per_l100": round(PETROL_CO2_PER_L100, 4),
            },
            "diesel": {
                "CF": C_DIESEL,
                "D": D_DIESEL,
                "approx": f"CO2/{DIESEL_CO2_PER_L100:.2f}",
                "co2_per_l100": round(DIESEL_CO2_PER_L100, 4),
            },
            "lpg": {"CF": C_LPG, "D": D_LPG},
            "cng_kg_per_100km": {"CF": C_NG, "note": "kg/100 km"},
        },
        "bollo": {
            "formula": "national 2.58/3.87 + superbollo; GPL/metano national petrol-scale (Lazio flat 2.84 not applied)",
            "source": "aci.it Criteri di calcolo del bollo auto",
            "phev_flat_90_removed": True,
            "phev_consumption_not_overwritten_from_co2": True,
        },
        "queries": query_log,
        "counts": {
            "seed_rows_in": len(json.loads(SEED_PATH.read_text(encoding="utf-8"))),
            "seed_rows_out": len(rows),
            "corrections": len(corrections),
            "additions": len(additions),
            "bollo_updates": len(bollo_updates),
            "mild_hybrid_trims": len(mild_trim),
            "ghost_candidates": len(ghost_candidates),
            "ghosts_removed": len(removed),
            "skipped_no_co2": skipped_no_co2,
            "phev_bollo_touched_no_fc_overwrite": phev_bollo_only,
        },
        "corrections": corrections,
        "additions": additions,
        "bollo_updates_total": len(bollo_updates),
        "ghost_candidates": ghost_candidates,
        "ghosts_removed": removed,
        "true_ghost_ids": sorted(TRUE_GHOST_IDS),
    }

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest["counts"], indent=2))
    print("Ghosts removed:", removed)

    if args.dry_run:
        print("Dry run — seed not written.")
        return

    SEED_PATH.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    bump_seed_version(args.seed_version)
    print(f"Wrote {SEED_PATH}; seedVersion={args.seed_version}")


if __name__ == "__main__":
    main()
