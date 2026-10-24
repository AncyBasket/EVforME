#!/usr/bin/env python3
"""
Re-fetch IT_* EEA fuel caches with Status nested under Ft, then rewrite every
`n=` citation on EEA-labeled seed rows from the Status-F cell (P if no F).

Label-only: never touch consumption, kW, or bollo.
"""

from __future__ import annotations

import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import fill_catalog_fuels_from_eea as eea
import fix_catalog_restore_v45 as v45
import fix_catalog_truth as truth

NEW_SEED_VERSION = 51
REPORT_PATH = truth.CACHE_DIR / "catalog_restore_v51_report.json"
N_PAT = re.compile(r"\bn=(\d+)\b")
EEA_LABEL_PAT = re.compile(r"^EEA\b", re.I)
BMW_SERIES_PAT = re.compile(r"^(\d)\s*series", re.I)
# Trailing annotation after n= (variant list / kWh note) — stripped when rewriting.
EEA_TAIL_PAT = re.compile(
    r"^(EEA co2cars IT \d{4})(?:\s+.+?)?\s+n=(\d+)(.*)$", re.I
)


def mk_from_cache_filename(path: Path, *, kind: str) -> str:
    """
    Map cache filename → co2cars Mk.

    Filenames sanitize spaces to underscores (IT_ALFA_ROMEO_fuels.json), but the
    API term is 'ALFA ROMEO' / 'LAND ROVER'. MERCEDES-BENZ keeps the hyphen.
    """
    if kind == "fuels":
        raw = path.name[len("IT_") : -len("_fuels.json")]
    else:
        raw = path.name[len("IT_") : -len("_hev_FmH.json")]
    if raw == "MERCEDES-BENZ":
        return "MERCEDES-BENZ"
    return raw.replace("_", " ")


def refresh_caches(*, only_empty: bool = False) -> dict:
    fuels = sorted(truth.CACHE_DIR.glob("IT_*_fuels.json"))
    hevs = sorted(truth.CACHE_DIR.glob("IT_*_hev_FmH.json"))
    stats: dict = {"fuels": 0, "hev": 0, "skipped": 0, "errors": []}
    for path in fuels:
        mk_query = mk_from_cache_filename(path, kind="fuels")
        if only_empty:
            wrap = json.loads(path.read_text(encoding="utf-8"))
            buckets = (
                wrap.get("response", {})
                .get("aggregations", {})
                .get("models", {})
                .get("buckets")
                or []
            )
            if buckets:
                stats["skipped"] += 1
                continue
        print(f"refresh fuels Mk={mk_query!r}…")
        try:
            eea.load_or_fetch(
                f"IT_{mk_query}_fuels", eea.brand_payload(mk_query, hev_only=False), use_cache=False
            )
            stats["fuels"] += 1
        except Exception as exc:  # noqa: BLE001
            stats["errors"].append(f"fuels {mk_query}: {exc}")
            print("  FAIL", exc)
        time.sleep(0.35)
    for path in hevs:
        mk_query = mk_from_cache_filename(path, kind="hev")
        if only_empty:
            wrap = json.loads(path.read_text(encoding="utf-8"))
            buckets = (
                wrap.get("response", {})
                .get("aggregations", {})
                .get("models", {})
                .get("buckets")
                or []
            )
            if buckets:
                stats["skipped"] += 1
                continue
        print(f"refresh hev Mk={mk_query!r}…")
        try:
            eea.load_or_fetch(
                f"IT_{mk_query}_hev_FmH", eea.brand_payload(mk_query, hev_only=True), use_cache=False
            )
            stats["hev"] += 1
        except Exception as exc:  # noqa: BLE001
            stats["errors"].append(f"hev {mk_query}: {exc}")
            print("  FAIL", exc)
        time.sleep(0.35)
    return stats


def best_bmw_series_fuel(
    ice_map: dict, digit: int, year: int, want: str | None
) -> tuple[str, str, dict] | None:
    """Max-n among Cn like 218DACTIVETOURER for series digit, preferring seed fuel."""
    candidates: list[tuple[float, str, str, dict]] = []
    pat = re.compile(rf"^{digit}\d{{2}}")
    for (mn, y, ft), cell in ice_map.items():
        if y != year or "ELECTRIC" in ft:
            continue
        if not pat.match(mn):
            continue
        n = float(cell.get("n") or 0)
        if n <= 0:
            continue
        if want and ft != want:
            continue
        penalty = 0.0
        if mn.endswith("M") or "MCOMPETITION" in mn or "M40" in mn or "M50" in mn:
            penalty = n * 0.4
        candidates.append((n - penalty, mn, ft, cell))
    if not candidates and want:
        # Fall back to any fuel in the series (volume label).
        return best_bmw_series_fuel(ice_map, digit, year, None)
    if not candidates:
        return None
    candidates.sort(key=lambda t: -t[0])
    _, mn, ft, cell = candidates[0]
    return mn, ft, cell


# Seed model → EEA Cn token when match_model / family prefix miss.
MODEL_CN_ALIASES: dict[tuple[str, str], str] = {
    ("SUZUKI", "SCROSS"): "SX4",
    ("SUZUKI", "S-CROSS"): "SX4",
    ("VOLKSWAGEN", "GOLFGTI"): "GOLF",
    ("FIAT", "TIPOCROSS"): "TIPO",
    ("BMW", "318IC"): "318I",
    ("BMW", "318IS"): "318I",
    ("ALFA ROMEO", "GIULIETTA"): "ALFAGIULIETTA",
}


def _cite_year(source_name: str, row_year: int) -> int:
    """Year to resolve against: prefer 'da EEA IT YYYY' / 'EEA … IT YYYY' when row is 2026+."""
    sn = source_name or ""
    m = re.search(r"da EEA IT (\d{4})", sn, re.I)
    if m:
        return int(m.group(1))
    m = re.search(r"EEA(?: co2cars)? IT (\d{4})", sn, re.I)
    if m:
        y = int(m.group(1))
        if row_year >= 2026 or y == row_year:
            return y
    return row_year


def _family_cells(
    ice_map: dict, hev_map: dict, token: str, year: int, want: str | None
) -> list[tuple[str, str, dict]]:
    """All Status-F cells for year/fuel whose Cn contains the family token."""
    out: list[tuple[str, str, dict]] = []
    if not token or len(token) < 2:
        return out
    for mp in (ice_map, hev_map):
        for (mn, y, ft), cell in mp.items():
            if y != year:
                continue
            if want and ft != want:
                continue
            if "ELECTRIC" in ft and want and "ELECTRIC" not in want:
                continue
            if token in mn or mn == token or mn.startswith(token):
                if float(cell.get("n") or 0) >= 1:
                    out.append((mn, ft, cell))
    return out


def resolve_label_cell(
    row: dict, ice_maps: dict, hev_maps: dict
) -> tuple[str, str, dict, int] | None:
    """
    Same variante + carburante + anno as the seed row (or cited EEA year for 2026).

    If the current n= already equals a Status-F (else P) cell for that family/fuel/year,
    keep that cell (preserves CLA 220 vs CLA 200). Otherwise pick the preferred cell
    (family aggregate / max-n / match_model).
    """
    brand = truth.brand_u(row)
    row_year = int(row.get("year") or 0)
    sn = str(row.get("sourceName") or "")
    year = _cite_year(sn, row_year)
    if year < 2017:
        return None
    pt = (row.get("powertrain") or "").lower()
    ice_map = ice_maps.get(brand) or {}
    hev_map = hev_maps.get(brand) or {}
    model_raw = str(row.get("model") or "")
    want = eea.seed_fuel_ft(row)
    locked = truth.seed_fuel_locked(row)
    if locked == "diesel":
        want = "DIESEL"
    elif locked == "lpg":
        want = "LPG"
    elif locked == "cng":
        want = "NG"

    cited_m = N_PAT.search(sn)
    cited_n = int(cited_m.group(1)) if cited_m else None

    def pick_preferred() -> tuple[str, str, dict, int] | None:
        if pt == "ev":
            fam = truth.family_prefix(model_raw)
            best = None
            for (mn, y, ft), cell in ice_map.items():
                if y != year or ft != "ELECTRIC":
                    continue
                model_u = eea.norm_alnum(model_raw)
                if fam and fam not in mn and not mn.startswith(fam[: min(6, len(fam))]):
                    if model_u and model_u not in mn and mn not in model_u:
                        if not ("SCENIC" in model_u and "SCENIC" in mn):
                            continue
                if best is None or float(cell.get("n") or 0) > float(best[2].get("n") or 0):
                    best = (mn, ft, cell)
            if best:
                return best[0], best[1], best[2], year
            return None

        # Mercedes A/B/C/…: max-sum_r single Cn (C 200 D), never family sum of all C*D.
        letter = v45.mb_class_letter(model_raw)
        if brand.startswith("MERCEDES") and letter:
            if want:
                cands: list[tuple[float, str, str, dict]] = []
                pat = re.compile(rf"^{re.escape(letter)}\d{{2,3}}")
                for (mn, y, ft), cell in ice_map.items():
                    if y != year or ft != want:
                        continue
                    if not pat.match(mn):
                        continue
                    if letter == "C" and (
                        mn.startswith("CL")
                        or mn.startswith("CLA")
                        or mn.startswith("CLE")
                        or mn.startswith("GLC")
                    ):
                        continue
                    if letter == "A" and (mn.startswith("AMG") or mn.startswith("GLA")):
                        continue
                    n = float(cell.get("n") or 0)
                    if n >= 1:
                        cands.append((n, mn, ft, cell))
                if cands:
                    cands.sort(key=lambda t: -t[0])
                    _, mn, ft, cell = cands[0]
                    return mn, ft, cell, year
            hit = v45.best_hit_mercedes_class(ice_map, letter, year)
            if hit and float(hit[2].get("n") or 0) >= 1:
                return hit[0], hit[1], hit[2], year

        # Mercedes CLA/GLA/GLC/… nameplates — max-n Cn with seed fuel (before match_model).
        if brand.startswith("MERCEDES") and want:
            tok = eea.norm_alnum(model_raw)
            if tok in {"CLA", "GLA", "GLB", "GLC", "GLE", "GLS", "CLS", "SLC", "SL", "EQA", "EQB", "EQC", "EQE", "EQS"}:
                best = truth.best_hit_for_family(
                    ice_map, tok, year, prefer_ft=want, thermal_only=True
                )
                if best and float(best[2].get("n") or 0) >= 1:
                    return best[0], best[1], best[2], year

        # BMW "2 Series Active Tourer" → max Cn; "3 Series"/"5 Series" → family aggregate.
        bm = BMW_SERIES_PAT.match(model_raw.strip())
        if brand == "BMW" and bm:
            digit = int(bm.group(1))
            if want:
                fam_hit = eea.family_eea_hit(brand, model_raw, year, want, ice_map)
                if fam_hit and float(fam_hit.get("n") or 0) >= 1:
                    return str(fam_hit.get("model_raw") or model_raw), want, fam_hit, year
            hit = best_bmw_series_fuel(ice_map, digit, year, want)
            if hit and float(hit[2].get("n") or 0) >= 1:
                return hit[0], hit[1], hit[2], year

        if brand == "MINI":
            if re.search(r"convertible|cabrio", model_raw, re.I) or "convertible" in str(
                row.get("id") or ""
            ):
                hit = v45.best_hit_mini_convertible(ice_map, year)
            else:
                hit = v45.best_hit_mini_hatch(ice_map, year)
            if hit and float(hit[2].get("n") or 0) >= 1:
                return hit[0], hit[1], hit[2], year

        # Renault Clio 2021: Status F on bare CLIO already includes E-Tech hybrid
        # regs (n=13394). Do not use the Fm=H subset (≈7005) or E-TECH-only P.
        if (
            brand == "RENAULT"
            and eea.norm_alnum(model_raw) == "CLIO"
            and year == 2021
            and (want or "PETROL") == "PETROL"
        ):
            clio = ice_map.get(("CLIO", 2021, "PETROL"))
            if clio and float(clio.get("n") or 0) >= 1:
                return "CLIO", "PETROL", clio, year

        # Full hybrid: HYBRID/E-TECH Cn only (never petrol sibling YARIS / CLIO).
        # Prefer ice (all Status) over hev Fm=H subset for the cited n=.
        full_hybrid_row = pt == "hev" and (
            brand in eea.FULL_HYBRID_BRANDS
            or "hybrid" in model_raw.lower()
            or "e-tech" in model_raw.lower()
            or str(row.get("trim") or "").lower() == "hybrid"
        )
        if full_hybrid_row and want:
            eea_models_h = {k[0] for k in ice_map} | {k[0] for k in hev_map}
            hy_key, hy_hit = eea.match_full_hybrid_model(
                model_raw, eea_models_h, ice_map, ice_map, year, want
            )
            if not hy_hit:
                hy_key, hy_hit = eea.match_full_hybrid_model(
                    model_raw, eea_models_h, hev_map, hev_map, year, want
                )
            if hy_hit and float(hy_hit.get("n") or 0) >= 1:
                return hy_key or model_raw, want, hy_hit, year

        # Family aggregates for A4 / Tucson / 911 / … (not Mercedes — handled above).
        if want and pt in ("ice", "hev") and not brand.startswith("MERCEDES"):
            fam_hit = eea.family_eea_hit(brand, model_raw, year, want, ice_map)
            if fam_hit and float(fam_hit.get("n") or 0) >= 1:
                label = str(fam_hit.get("model_raw") or model_raw)
                return label, want, fam_hit, year
            # 911 / Panamera often lack Ewltp — still sum Status-F n for the label.
            tok = eea.norm_alnum(model_raw)
            if tok in {"911", "PANAMERA"} or model_raw.strip().upper() in {"911", "PANAMERA"}:
                cells = _family_cells(ice_map, hev_map, tok, year, want)
                total = sum(float(c.get("n") or 0) for _, _, c in cells)
                if total >= 1:
                    return tok, want, {"n": total, "model_raw": model_raw}, year

        # Explicit Cn aliases (S-Cross→SX4, Golf GTI→GOLF, …).
        alias_key = eea.norm_alnum(model_raw)
        alias = MODEL_CN_ALIASES.get((brand, alias_key)) or MODEL_CN_ALIASES.get(
            (brand, model_raw.strip().upper())
        )
        if alias and want:
            hit = ice_map.get((alias, year, want)) or hev_map.get((alias, year, want))
            if hit and float(hit.get("n") or 0) >= 1:
                return alias, want, hit, year

        # Exact / fuzzy Cn match for seed fuel.
        # Prefer ice fuels map over hev Fm=H (subset) so n= matches Status-F cells.
        eea_models = {k[0] for k in ice_map} | {k[0] for k in hev_map}
        model_n = eea.match_model(model_raw, eea_models, for_ice=(pt == "ice"))
        if model_n and want:
            hit = eea.bifuel_alias_hit(ice_map, model_n, year, want)
            if not hit:
                hit = ice_map.get((model_n, year, want)) or hev_map.get((model_n, year, want))
            if hit and float(hit.get("n") or 0) >= 1:
                # Prefer a high-volume sibling (Tucson → TUCSON IX35) over a tiny exact Cn.
                best = truth.best_hit_for_family(
                    ice_map, model_n, year, prefer_ft=want, thermal_only=True
                )
                if (
                    best
                    and float(best[2].get("n") or 0) >= 100
                    and float(best[2].get("n") or 0) > float(hit.get("n") or 0) * 5
                ):
                    return best[0], best[1], best[2], year
                return model_n, want, hit, year

        # Land Rover / special family prefixes BEFORE contains (Evoque strips "EV").
        fam = v45.family_for_row(row)
        if fam and want:
            best = truth.best_hit_for_family(ice_map, fam, year, prefer_ft=want, thermal_only=True)
            if best and float(best[2].get("n") or 0) >= 1:
                return best[0], best[1], best[2], year
            best_h = truth.best_hit_for_family(hev_map, fam, year, prefer_ft=want, thermal_only=True)
            if best_h and float(best_h[2].get("n") or 0) >= 1:
                return best_h[0], best_h[1], best_h[2], year

        # Contains-token fallback (Giulietta → ALFAGIULIETTA, Tipo Cross → TIPO).
        # Never match a shorter parent Cn inside the token (RANGEROVER ⊂ RANGEROVEROQUE).
        token = fam or eea.norm_alnum(model_raw)
        if token and want and len(token) >= 3:
            cands = []
            for (mn, y, ft), cell in ice_map.items():
                if y != year or ft != want:
                    continue
                if mn == token or mn.startswith(token) or token in mn:
                    n = float(cell.get("n") or 0)
                    if n >= 1:
                        cands.append((n, mn, ft, cell))
            if cands:
                cands.sort(key=lambda t: -t[0])
                _, mn, ft, cell = cands[0]
                return mn, ft, cell, year

        hit = truth.resolve_eea_hit(row, ice_maps, hev_maps, prefer_seed_fuel=True, volume_first=False)
        if hit and int(hit[3]) == year and float(hit[2].get("n") or 0) >= 1:
            return hit
        hit = truth.resolve_eea_hit(row, ice_maps, hev_maps, volume_first=True, prefer_seed_fuel=False)
        if hit and int(hit[3]) == year and float(hit[2].get("n") or 0) >= 1:
            return hit
        alt = v45.resolve_hit(row, ice_maps, hev_maps)
        if alt and int(alt[3]) == year and float(alt[2].get("n") or 0) >= 1:
            return alt
        return None

    preferred = pick_preferred()

    # Family aggregates (A4 / 3-Series / Clio diesel / …) always win — the label
    # must list the summed variants even when a single Cn matched the old n=.
    if preferred and isinstance(preferred[2].get("variants"), list) and len(preferred[2]["variants"]) >= 2:
        return preferred

    # Keep cited n only when it matches preferred or a Cn that properly belongs
    # to the seed family (token ⊂ Cn), not a shorter parent nameplate.
    # Search ice fuels first — hev Fm=H is a subset (Ypsilon 8575 vs ice 8584).
    if cited_n is not None and want and preferred:
        pref_n = int(float(preferred[2].get("n") or 0))
        if pref_n == cited_n:
            return preferred
        # Don't keep a thin leftover Cn (TUCSON n=1) when preferred is the real volume.
        if pref_n >= 100 and cited_n < 30 and pref_n > cited_n * 5:
            return preferred
        fam = v45.family_for_row(row)
        tokens = {t for t in (fam, eea.norm_alnum(model_raw)) if t and len(t) >= 3}
        for tok in tokens:
            for mn, ft, cell in _family_cells(ice_map, {}, tok, year, want):
                if int(float(cell.get("n") or 0)) != cited_n:
                    continue
                # Reject parent Cn shorter than the family token (RANGE ROVER vs Evoque).
                if len(mn) < len(tok) and mn != tok:
                    continue
                return mn, ft, cell, year
            for mn, ft, cell in _family_cells({}, hev_map, tok, year, want):
                if int(float(cell.get("n") or 0)) != cited_n:
                    continue
                if len(mn) < len(tok) and mn != tok:
                    continue
                # Skip Fm=H subset when ice has a different (usually fuller) n.
                ice_cell = ice_map.get((mn, year, ft))
                if ice_cell and int(float(ice_cell.get("n") or 0)) != cited_n:
                    continue
                return mn, ft, cell, year

    return preferred


def format_eea_source_name(
    year: int,
    n: int,
    *,
    eea_model: str,
    cell: dict,
    seed_model: str,
    prior_sn: str,
) -> str:
    """
    Build EEA sourceName. Aggregates list summed variants; single Cn that differs
    from the seed model is named explicitly (GLC 300 4MATIC, CLIO E-TECH HYBRID).
    Preserve trailing notes (kWh) from the previous label when present.
    """
    tail = ""
    m = EEA_TAIL_PAT.match(prior_sn.strip())
    if m and m.group(3):
        # Keep "; kWh/…" style notes only (not old variant lists in parens).
        raw_tail = m.group(3).strip()
        if raw_tail.startswith(";"):
            tail = " " + raw_tail
        elif raw_tail.startswith("(") and "kWh" in raw_tail.lower():
            tail = " " + raw_tail

    variants = cell.get("variants") or []
    if isinstance(variants, list) and len(variants) >= 2:
        # Full list — no "…" truncation so the sum stays reconstructible (911 etc.).
        shown = "+".join(str(v) for v in variants)
        return f"EEA co2cars IT {year} n={n} ({shown}){tail}"

    display = str(cell.get("model_raw") or eea_model or "").strip()
    seed_u = eea.norm_alnum(seed_model)
    disp_u = eea.norm_alnum(display)
    status = str(cell.get("status") or "").upper()
    provisional = ""
    if status == "P":
        fetched = str(cell.get("fetched_at") or "").strip()
        if fetched:
            provisional = f" (provvisorio, dati {fetched[:10]})"
        else:
            provisional = " (provvisorio)"

    # Clio petrol F cell includes E-Tech hybrid regs under bare "CLIO".
    if disp_u == "CLIO" and year == 2021 and n >= 10000:
        return (
            f"EEA co2cars IT {year} CLIO n={n} "
            f"(F include E-Tech hybrid){tail}"
        )

    # Always name sparse cells (n<30) so hygiene can accept them.
    if n < 30 and display:
        return f"EEA co2cars IT {year} {display} n={n}{provisional}{tail}"
    # Name the counted Cn when it is not the bare seed model family.
    if display and disp_u and disp_u != seed_u and not disp_u.startswith(seed_u + "SERIES"):
        # Skip generic aggregate labels like "3-Series" / "A4" / "911".
        if display not in {
            "3-Series",
            "5-Series",
            "A4",
            "911",
            "Panamera",
            "A-Class",
            "B-Class",
            "C-Class",
            "Tucson",
        }:
            return f"EEA co2cars IT {year} {display} n={n}{provisional}{tail}"
    # Still name Evoque / Discovery Sport etc. when seed alnum differs only by spaces.
    if display and ("EVOQUE" in disp_u or "DISCOVERYSPORT" in disp_u):
        return f"EEA co2cars IT {year} {display} n={n}{provisional}{tail}"
    return f"EEA co2cars IT {year} n={n}{provisional}{tail}"


def label_only_recalc_n(rows: list[dict], ice_maps: dict, hev_maps: dict) -> tuple[list[dict], list[str]]:
    """Replace n= on every EEA-labeled row with Status-F (else P) cell n."""
    changes: list[dict] = []
    unresolved: list[str] = []
    for r in rows:
        sn = str(r.get("sourceName") or "")
        if not EEA_LABEL_PAT.match(sn) or "n=" not in sn:
            continue
        m = N_PAT.search(sn)
        if not m:
            unresolved.append(str(r.get("id")))
            continue
        cited = int(m.group(1))
        hit = resolve_label_cell(r, ice_maps, hev_maps)
        if not hit:
            unresolved.append(str(r.get("id")))
            continue
        mn, ft, cell, ey = hit
        cite_y = _cite_year(sn, int(r.get("year") or 0))
        if int(ey) != cite_y:
            unresolved.append(str(r.get("id")))
            continue
        real = int(float(cell.get("n") or 0))
        if real <= 0:
            unresolved.append(str(r.get("id")))
            continue
        new_sn = format_eea_source_name(
            ey,
            real,
            eea_model=str(mn),
            cell=cell,
            seed_model=str(r.get("model") or ""),
            prior_sn=sn,
        )
        if new_sn == sn and cited == real:
            continue
        r["sourceName"] = new_sn
        changes.append(
            {
                "id": r.get("id"),
                "n_from": cited,
                "n_to": real,
                "eea_model": mn,
                "ft": ft,
                "eea_year": ey,
                "status": cell.get("status"),
                "variants": cell.get("variants"),
            }
        )
    return changes, unresolved


def build_label_refs(rows: list[dict], ice_maps: dict, hev_maps: dict) -> list[dict]:
    """EEA refs aligned to the same cell/variant the sourceName n= counts."""
    refs: list[dict] = []
    for r in rows:
        sn = str(r.get("sourceName") or "")
        if not EEA_LABEL_PAT.match(sn) or "n=" not in sn:
            continue
        pt = (r.get("powertrain") or "").lower()
        if pt not in ("ice", "hev"):
            continue
        hit = resolve_label_cell(r, ice_maps, hev_maps)
        if not hit:
            continue
        eea_model, ft, cell, eea_year = hit
        n = float(cell.get("n") or 0)
        if n < 1:
            continue
        locked = truth.seed_fuel_locked(r)
        fk = locked or truth.ft_to_fuel_kind(ft)
        fc100 = eea.co2_to_fuel_per_100km(
            cell.get("co2"), fk if fk in ("petrol", "diesel", "lpg", "cng") else "petrol"
        )
        ref = {
            "id": r.get("id"),
            "n": int(n),
            "eea_year": eea_year,
            "eea_model": eea_model,
            "ft": ft,
            "powerKw": cell.get("kw"),
            "fuelKind": fk,
        }
        if cell.get("variants"):
            ref["variants"] = cell["variants"]
        if fc100 is not None:
            ref["eea_l100"] = round(fc100, 3)
        display = str(cell.get("model_raw") or eea_model)
        if display and not cell.get("variants"):
            ref["eea_model"] = eea.norm_alnum(display) if " " not in display else display
            # Prefer readable model_raw for humans/tests.
            if cell.get("model_raw"):
                ref["eea_model"] = str(cell["model_raw"])
        refs.append(ref)
    for r in rows:
        rid = r.get("id")
        if rid in truth.EV_EEA_KWH100:
            refs.append({"id": rid, "eea_kwh100": truth.EV_EEA_KWH100[rid], "kind": "ev"})
    return refs


def bump_metadata(rows: list[dict], report: dict) -> None:
    eea.bump_seed_version(NEW_SEED_VERSION)
    raw = truth.SEED_PATH.read_bytes()
    cdn = json.loads(truth.CDN_PATH.read_text(encoding="utf-8"))
    cdn["seedVersion"] = NEW_SEED_VERSION
    cdn["rows"] = len(rows)
    cdn["bytes"] = len(raw)
    cdn["updatedAt"] = datetime.now(timezone.utc).isoformat()
    cdn["note"] = (
        f"seedVersion {NEW_SEED_VERSION}: every EEA n= from Status F (sum F across "
        f"Mk+Cn strip+casefold and Ft casing; DS≡DS AUTOMOBILES; P only if no F / "
        f"thin incomplete F); aggregates list full variants — label-only."
    )
    truth.CDN_PATH.write_text(json.dumps(cdn, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report["seedVersion"] = NEW_SEED_VERSION
    report["rows"] = len(rows)
    report["bytes"] = len(raw)


def main() -> int:
    skip_fetch = "--skip-fetch" in sys.argv
    only_empty = "--only-empty" in sys.argv or not skip_fetch
    # Default: refresh empty caches (Alfa/LR) with correct Mk; --all-fetch refreshes everything.
    if "--all-fetch" in sys.argv:
        only_empty = False
    report: dict = {"skip_fetch": skip_fetch, "only_empty": only_empty and not skip_fetch}
    if not skip_fetch:
        report["cache_refresh"] = refresh_caches(only_empty=only_empty)
    else:
        report["cache_refresh"] = {"skipped": True}

    ice = truth.load_ice_maps()
    hev = truth.load_hev_maps()
    # Normalize ice keys: underscore Mk → space (legacy bad caches).
    for maps in (ice, hev):
        for key in list(maps.keys()):
            if "_" in key and key != "MERCEDES-BENZ":
                fixed = key.replace("_", " ")
                if fixed not in maps or len(maps[fixed]) < len(maps[key]):
                    maps[fixed] = maps.pop(key)
                elif key in maps:
                    maps.pop(key, None)

    c200 = ice.get("MERCEDES-BENZ", {}).get(("C200D", 2024, "DIESEL"), {})
    stelvio = ice.get("ALFA ROMEO", {}).get(("STELVIO", 2023, "DIESEL"), {})
    ceed = ice.get("KIA", {}).get(("CEED", 2019, "PETROL"), {})
    print("spot C200D 2024", c200.get("n"), c200.get("status"))
    print("spot STELVIO diesel 2023", stelvio.get("n"), stelvio.get("status"))
    print("spot CEED petrol 2019", ceed.get("n"), ceed.get("status"))

    rows: list[dict] = json.loads(truth.SEED_PATH.read_text(encoding="utf-8"))
    changes, unresolved = label_only_recalc_n(rows, ice, hev)
    report["label_n_fixes"] = len(changes)
    report["label_n_unresolved"] = unresolved
    report["label_n_sample"] = changes[:50]
    report["examples"] = {
        "alfa-romeo-stelvio-diesel-2023": next(
            (c for c in changes if c["id"] == "alfa-romeo-stelvio-diesel-2023"), None
        ),
        "kia-ceed-2019": next((c for c in changes if c["id"] == "kia-ceed-2019"), None),
        "bmw-2-series-2023": next((c for c in changes if c["id"] == "bmw-2-series-2023"), None),
        "hyundai-bayon-2023": next((c for c in changes if c["id"] == "hyundai-bayon-2023"), None),
    }

    if unresolved:
        print(f"WARNING: {len(unresolved)} EEA rows unresolved (will fail check)", file=sys.stderr)
        for rid in unresolved[:30]:
            print(" ", rid, file=sys.stderr)

    truth.SEED_PATH.write_text(
        json.dumps(rows, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8"
    )
    refs = build_label_refs(rows, ice, hev)
    truth.REFS_PATH.write_text(json.dumps(refs, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    fixture = truth.REPO / "EVforME?Tests" / "Fixtures" / "catalog_truth_eea_refs.json"
    if fixture.parent.is_dir():
        fixture.write_text(json.dumps(refs, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    bump_metadata(rows, report)
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    niro = ice.get("KIA", {}).get(("NIRO", 2022, "PETROL"), {})
    print(
        f"v51: label n fixes={len(changes)} unresolved={len(unresolved)} rows={len(rows)} "
        f"stelvio2023={stelvio.get('n')} ceed2019={ceed.get('n')} niro2022={niro.get('n')}"
    )
    by = {r["id"]: r for r in rows}
    for rid in (
        "alfa-romeo-stelvio-diesel-2023",
        "kia-niro-2022",
        "kia-ceed-2019",
        "bmw-3-series-2023",
        "mercedes-benz-glc-2023",
        "renault-clio-2023",
        "land-rover-range-rover-evoque-2018",
        "renault-captur-diesel-2018",
        "mercedes-benz-c-class-2024",
    ):
        if rid in by:
            print(rid, (by[rid].get("sourceName") or "")[:120])
    errs = report.get("cache_refresh", {}).get("errors") or []
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())
