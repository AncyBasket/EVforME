#!/usr/bin/env python3
"""
Re-fetch IT_* EEA fuel caches with Status nested under Ft, then rewrite only
`n=` citations in vehicles.seed.quality.json (label-only; no consumption/kW).

Prefer Status F; fall back to P when F is absent (e.g. 2025).
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
import fix_catalog_truth as truth

NEW_SEED_VERSION = 47
REPORT_PATH = truth.CACHE_DIR / "catalog_restore_v47_report.json"
N_PAT = re.compile(r"\bn=(\d+)\b")


def refresh_caches() -> dict:
    fuels = sorted(truth.CACHE_DIR.glob("IT_*_fuels.json"))
    hevs = sorted(truth.CACHE_DIR.glob("IT_*_hev_FmH.json"))
    stats = {"fuels": 0, "hev": 0, "errors": []}
    for path in fuels:
        mk = path.name[len("IT_") : -len("_fuels.json")].replace("_", "-")
        # MERCEDES-BENZ etc. — cache names use hyphen already in some; restore spaces for Mk
        mk_query = mk.replace("-", " ") if mk not in ("MERCEDES-BENZ",) else mk
        # Filenames: IT_MERCEDES-BENZ_fuels.json → MERCEDES-BENZ
        mk_query = path.name[len("IT_") : -len("_fuels.json")]
        print(f"refresh fuels Mk={mk_query}…")
        try:
            eea.load_or_fetch(f"IT_{mk_query}_fuels", eea.brand_payload(mk_query, hev_only=False), use_cache=False)
            stats["fuels"] += 1
        except Exception as exc:  # noqa: BLE001
            stats["errors"].append(f"fuels {mk_query}: {exc}")
            print("  FAIL", exc)
        time.sleep(0.35)
    for path in hevs:
        mk_query = path.name[len("IT_") : -len("_hev_FmH.json")]
        print(f"refresh hev Mk={mk_query}…")
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


def label_only_halve_n(rows: list[dict], ice_maps: dict, hev_maps: dict) -> list[dict]:
    """Replace n= citations when they are exactly 2× the Status-F (or P) cell."""
    changes: list[dict] = []
    for r in rows:
        sn = str(r.get("sourceName") or "")
        if "n=" not in sn:
            continue
        m = N_PAT.search(sn)
        if not m:
            continue
        cited = int(m.group(1))
        pt = (r.get("powertrain") or "").lower()
        hit = None
        if pt == "ev":
            # Resolve ELECTRIC cell for EV rows (Scenic etc.).
            brand = truth.brand_u(r)
            year = int(r.get("year") or 0)
            fam = truth.family_prefix(str(r.get("model") or ""))
            best = None
            for (mn, y, ft), cell in (ice_maps.get(brand) or {}).items():
                if y != year or ft != "ELECTRIC":
                    continue
                if fam and fam not in mn and not mn.startswith(fam[: min(6, len(fam))]):
                    # Scenic E-Tech: model Scenic E-Tech → family may be SCENIC…
                    model_u = eea.norm_alnum(str(r.get("model") or ""))
                    if model_u and model_u not in mn and mn not in model_u:
                        if "SCENIC" in model_u and "SCENIC" in mn:
                            pass
                        else:
                            continue
                if best is None or float(cell.get("n") or 0) > float(best[2].get("n") or 0):
                    best = (mn, ft, cell)
            if best:
                hit = (best[0], best[1], best[2], year)
        else:
            hit = truth.resolve_eea_hit(
                r, ice_maps, hev_maps, prefer_seed_fuel=True, volume_first=False
            )
            if not hit:
                hit = truth.resolve_eea_hit(
                    r, ice_maps, hev_maps, volume_first=True, prefer_seed_fuel=False
                )
            # Mercedes class / BMW series specials for volume-first labeled rows
            if not hit or int(hit[3]) != int(r.get("year") or 0):
                import fix_catalog_restore_v45 as v45

                alt = v45.resolve_hit(r, ice_maps, hev_maps)
                if alt and int(alt[3]) == int(r.get("year") or 0):
                    hit = alt

        if not hit:
            continue
        mn, ft, cell, ey = hit
        if int(ey) != int(r.get("year") or 0):
            # Prior-year stima: still fix n if the cited year matches ey
            ym = re.search(r"(?:EEA(?: co2cars)? IT |da EEA IT )(\d{4})", sn, re.I)
            if not ym or int(ym.group(1)) != int(ey):
                continue
        real = int(float(cell.get("n") or 0))
        if real <= 0:
            continue
        if cited == real:
            continue
        if cited != real * 2:
            # Not a clean F+P double — leave alone
            continue
        new_sn = N_PAT.sub(f"n={real}", sn, count=1)
        if new_sn == sn:
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
            }
        )
    return changes


def bump_metadata(rows: list[dict], report: dict) -> None:
    eea.bump_seed_version(NEW_SEED_VERSION)
    raw = truth.SEED_PATH.read_bytes()
    cdn = json.loads(truth.CDN_PATH.read_text(encoding="utf-8"))
    cdn["seedVersion"] = NEW_SEED_VERSION
    cdn["rows"] = len(rows)
    cdn["bytes"] = len(raw)
    cdn["updatedAt"] = datetime.now(timezone.utc).isoformat()
    cdn["note"] = (
        f"seedVersion {NEW_SEED_VERSION}: EEA n labels use Status F (else P); "
        f"no consumption/kW change — F/P share the same metrics."
    )
    truth.CDN_PATH.write_text(json.dumps(cdn, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report["seedVersion"] = NEW_SEED_VERSION
    report["rows"] = len(rows)
    report["bytes"] = len(raw)


def main() -> int:
    skip_fetch = "--skip-fetch" in sys.argv
    report: dict = {"skip_fetch": skip_fetch}
    if not skip_fetch:
        report["cache_refresh"] = refresh_caches()
    else:
        report["cache_refresh"] = {"skipped": True}

    # Spot-check parse after refresh
    ice = truth.load_ice_maps()
    c200 = ice.get("MERCEDES-BENZ", {}).get(("C200D", 2024, "DIESEL"), {})
    scenic = None
    for (mn, y, ft), cell in (ice.get("RENAULT") or {}).items():
        if y == 2024 and ft == "ELECTRIC" and "SCENIC" in mn:
            if scenic is None or float(cell.get("n") or 0) > float(scenic.get("n") or 0):
                scenic = cell
                scenic_mn = mn
    print("spot C200D 2024", c200.get("n"), c200.get("status"))
    print("spot Scenic 2024", scenic_mn if scenic else None, scenic.get("n") if scenic else None, scenic.get("status") if scenic else None)

    rows: list[dict] = json.loads(truth.SEED_PATH.read_text(encoding="utf-8"))
    hev = truth.load_hev_maps()
    changes = label_only_halve_n(rows, ice, hev)
    report["label_n_fixes"] = len(changes)
    report["label_n_sample"] = changes[:40]
    report["examples"] = {
        "mercedes-benz-c-class-2024": next(
            (c for c in changes if c["id"] == "mercedes-benz-c-class-2024"), None
        ),
        "renault-scenic-2024": next((c for c in changes if c["id"] == "renault-scenic-2024"), None),
        "ds-ds-7-2024": next((c for c in changes if c["id"] == "ds-ds-7-2024"), None),
        "volkswagen-touareg-2024": next(
            (c for c in changes if c["id"] == "volkswagen-touareg-2024"), None
        ),
    }

    truth.SEED_PATH.write_text(
        json.dumps(rows, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8"
    )
    refs = truth.build_refs(rows, ice, hev)
    truth.REFS_PATH.write_text(json.dumps(refs, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    fixture = truth.REPO / "EVforME?Tests" / "Fixtures" / "catalog_truth_eea_refs.json"
    if fixture.parent.is_dir():
        fixture.write_text(json.dumps(refs, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    bump_metadata(rows, report)
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"v47: label n fixes={len(changes)} rows={len(rows)} "
        f"C200D2024={c200.get('n')} scenic={scenic.get('n') if scenic else None}"
    )
    # Verify examples in seed
    by = {r["id"]: r for r in rows}
    for rid in (
        "mercedes-benz-c-class-2024",
        "renault-scenic-2024",
        "ds-ds-7-2024",
        "volkswagen-touareg-2024",
        "mercedes-benz-s-class-2025",
        "mercedes-benz-c-class-2022",
    ):
        print(rid, (by[rid].get("sourceName") or "")[:100])
    return 0 if not report.get("cache_refresh", {}).get("errors") else 1


if __name__ == "__main__":
    sys.exit(main())
