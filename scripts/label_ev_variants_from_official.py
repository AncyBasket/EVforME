#!/usr/bin/env python3
"""
Apply official OEM labels to EEA EV version groups (seed v61).

Rules: no invented data; only manufacturer/press/PDF URLs; 1:1 matching;
merge duplicate official; drop EEA kW > model_max+5; unmatched → Versione n.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import fill_catalog_fuels_from_eea as eea

NEW_SEED_VERSION = 61
KW_TOL = 5.0
RANGE_TOL = 0.03

REFS_PATH = eea.CACHE_DIR / "catalog_truth_ev_variants_refs.json"
FIXTURE_REFS = eea.REPO / "EVforME?Tests" / "Fixtures" / "catalog_truth_ev_variants_refs.json"
REPORT_PATH = eea.CACHE_DIR / "catalog_ev_variants_label_report.json"
AUDIT_SET_PATH = eea.CACHE_DIR / "ev_variant_label_audit_set.json"
OFFICIAL_PATH = SCRIPT_DIR / "ev_variant_official_trims.json"
ALIAS_PATH = eea.REPO / "EVforME?" / "Data" / "ev_variant_single_aliases.json"

TESLA_M3_2026_IDS = {
    "tesla-model-3-trazione-posteriore-2026",
    "tesla-model-3-premium-trazione-posteriore-2026",
    "tesla-model-3-premium-long-range-2026",
    "tesla-model-3-performance-2026",
}

THIRD_PARTY_HOST_RE = re.compile(
    r"(ev-database|wikipedia|autocar|caranddriver|motortrend|insideevs|"
    r"electrek|carsales|carwow|whatcar|autoexpress|quattroruote|"
    r"alvolante|motor1|carmagazine)",
    re.I,
)


def is_forbidden_url(url: str) -> bool:
    host = urlparse(url).netloc.lower()
    return bool(THIRD_PARTY_HOST_RE.search(host))


def range_caption(zr_min: int, zr_max: int) -> str:
    if zr_min == zr_max:
        return f"Autonomia WLTP {zr_min} km (dipende da cerchi e optional)"
    return (
        f"Autonomia WLTP {zr_min}–{zr_max} km "
        f"(dipende da cerchi e optional)"
    )


def homologation_note(kw: float) -> str:
    return (
        f"Potenza omologata EEA {int(round(kw))} kW "
        f"(può differire dalla potenza massima)"
    )


def version_id(parent_id: str, kw: float, awd: bool, *, matched: bool, slug: str) -> str:
    if matched:
        safe = re.sub(r"[^a-z0-9]+", "-", slug.lower()).strip("-")[:40]
        return f"{parent_id}-v-{safe}-{int(round(kw))}kw"
    suffix = "awd" if awd else "rwd"
    return f"{parent_id}-v{int(round(kw))}kw-{suffix}"


def kw_hit(eea_kw: float, candidates: list[float]) -> bool:
    return any(abs(eea_kw - float(c)) <= KW_TOL for c in candidates)


def range_hit(official_range: float | None, zr_min: int, zr_max: int) -> bool:
    if official_range is None:
        return False
    lo = zr_min * (1 - RANGE_TOL)
    hi = zr_max * (1 + RANGE_TOL)
    return lo <= float(official_range) <= hi


def match_trim(group: dict, trims: list[dict]) -> dict | None:
    """1:1 official match. Prefer kW (±5); else unique WLTP (±3%). Never mix both
    into one candidate set — wide EEA Zr bands would false-match sibling trims.
    """
    eea_kw = float(group["kw"])
    zr_min = int(group["wltpRangeKmMin"])
    zr_max = int(group["wltpRangeKmMax"])
    kw_hits: list[dict] = []
    rng_hits: list[dict] = []
    for t in trims:
        match_vals = list(t.get("match_kw") or [t["power_kw_max"]])
        if kw_hit(eea_kw, match_vals):
            kw_hits.append(t)
        elif range_hit(t.get("wltp_range_km"), zr_min, zr_max):
            rng_hits.append(t)
    if len(kw_hits) == 1:
        return kw_hits[0]
    if len(kw_hits) > 1:
        return None
    if len(rng_hits) == 1:
        return rng_hits[0]
    return None


def merge_groups(groups: list[dict]) -> dict:
    records = []
    for g in groups:
        records.extend(g.get("eea_records") or [])
    zrs = [int(r["wltpRangeKm"]) for r in records]
    whs = [float(r["wh_per_km"]) for r in records]
    n = sum(float(g.get("registrations") or 0) for g in groups)
    # representative kw = registration-weighted of old groups
    tw = n or 1.0
    mean_kw = sum(float(g["kw"]) * float(g.get("registrations") or 0) for g in groups) / tw
    awd = any(bool(g.get("awd")) for g in groups)
    statuses = {str(g.get("status")) for g in groups}
    status = "F" if "F" in statuses else "P"
    base = dict(groups[0])
    base.update(
        {
            "kw": mean_kw,
            "awd": awd,
            "wltpRangeKm": min(zrs),
            "wltpRangeKmMin": min(zrs),
            "wltpRangeKmMax": max(zrs),
            "wh_per_km": max(whs),
            "wh_per_km_min": min(whs),
            "wh_per_km_max": max(whs),
            "registrations": round(n, 1),
            "status": status,
            "eea_records": records,
            "prudent": {"wltpRangeKm": min(zrs), "wh_per_km": round(max(whs), 1)},
        }
    )
    return base


def bump_cdn(rows: list[dict]) -> None:
    meta_path = eea.REPO / "EVforME?" / "Data" / "catalog_cdn.json"
    meta = {
        "url": "",
        "publishedUrl": "",
        "rows": len(rows),
        "bytes": 0,
        "source": "vehicles.seed.quality.json",
        "host": "bundled-offline-first",
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        "policy": "offline-first",
        "seedVersion": NEW_SEED_VERSION,
        "note": (
            f"seedVersion {NEW_SEED_VERSION}: EV version labels from official OEM sheets "
            "(matched name·kW; unmatched Versione n; drop EEA kW > official max+5)."
        ),
    }
    payload = json.dumps(
        [{k: v for k, v in r.items() if v is not None} for r in rows],
        separators=(",", ":"),
        ensure_ascii=False,
    )
    meta["bytes"] = len(payload.encode("utf-8"))
    meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    official_doc = json.loads(OFFICIAL_PATH.read_text(encoding="utf-8"))
    by_official = official_doc.get("byParentId") or {}
    audit = json.loads(AUDIT_SET_PATH.read_text(encoding="utf-8"))
    top40_ids = [x["parentId"] for x in audit["top40ByRegistrations"]]
    audit_ids = set(audit["auditParentIds"])

    for pid, entry in by_official.items():
        url = str(entry.get("url") or "")
        if not url or is_forbidden_url(url):
            raise SystemExit(f"forbidden or missing URL for {pid}: {url!r}")

    refs = json.loads(REFS_PATH.read_text(encoding="utf-8"))
    old_variants = list(refs.get("variants") or [])
    before_groups = len(old_variants)
    by_parent: dict[str, list[dict]] = defaultdict(list)
    for v in old_variants:
        by_parent[str(v["parentId"])].append(v)

    # Before range count from current seed (parents + children)
    seed_rows: list[dict] = json.loads(eea.SEED_PATH.read_text(encoding="utf-8"))
    parents = [r for r in seed_rows if r.get("powertrain") == "ev" and not r.get("parentId")]
    children_old = [r for r in seed_rows if r.get("parentId") and r.get("powertrain") == "ev"]
    child_parents = {str(c["parentId"]) for c in children_old if c.get("wltpRangeKm")}
    before_with_range = len(
        {
            str(r["id"])
            for r in parents
            if r.get("wltpRangeKm") or str(r["id"]) in child_parents
        }
    )

    new_variants: list[dict] = []
    discarded: list[dict] = []
    matched_n = unmatched_n = dropped_n = 0
    table_rows: list[dict] = []
    id_aliases: dict[str, str] = {}  # old child id → new child id when merge subset
    parent_by_id = {str(p["id"]): p for p in parents}

    for pid in sorted(by_parent.keys()):
        groups = sorted(
            by_parent[pid],
            key=lambda g: (-float(g.get("registrations") or 0), float(g["kw"])),
        )
        entry = by_official.get(pid) if pid in audit_ids else None
        model_max = float(entry["model_max_kw"]) if entry else None
        trims = list(entry.get("trims") or []) if entry else []
        url = entry.get("url") if entry else None

        # Drop over-max
        kept: list[dict] = []
        for g in groups:
            if model_max is not None and float(g["kw"]) > model_max + KW_TOL:
                discarded.append(
                    {
                        "parentId": pid,
                        "oldId": g["id"],
                        "kw": g["kw"],
                        "reason": "eea_kw_above_official_max",
                        "model_max_kw": model_max,
                        "url": url,
                    }
                )
                dropped_n += 1
            else:
                kept.append(g)

        # Match: group → exactly one official trim; multiple groups → same trim = MERGE
        by_trim: dict[str, list[dict]] = defaultdict(list)
        unmatched: list[dict] = []
        if entry and trims:
            for g in kept:
                t = match_trim(g, trims)
                if t is None:
                    unmatched.append(g)
                else:
                    by_trim[t["name"]].append(g)
        else:
            unmatched = list(kept)

        final_groups: list[tuple[dict, dict, list[str]]] = []
        for name, gs in by_trim.items():
            t = next(x for x in trims if x["name"] == name)
            merged = merge_groups(gs) if len(gs) > 1 else gs[0]
            old_ids = [g["id"] for g in gs]
            final_groups.append((merged, t, old_ids))

        uniq_unmatched = unmatched

        version_n = 1
        for g, t, old_ids in final_groups:
            matched_n += 1
            off_kw = float(t["power_kw_max"])
            label = f"{t['name']} · {int(round(off_kw))} kW"
            zr_min = int(g["wltpRangeKmMin"])
            zr_max = int(g["wltpRangeKmMax"])
            caption = range_caption(zr_min, zr_max)
            new_id = version_id(
                pid, off_kw, bool(t.get("awd") or g.get("awd")), matched=True, slug=t["name"]
            )
            # Migration: each old group’s records ⊆ merged union → alias OK
            for oid in old_ids:
                if oid != new_id:
                    id_aliases[oid] = new_id
            ref = dict(g)
            ref.update(
                {
                    "id": new_id,
                    "label": label,
                    "kw": off_kw,
                    "eea_kw": round(float(g["kw"]), 1),
                    "rangeCaption": caption,
                    "official_matched": True,
                    "official_name": t["name"],
                    "official_power_kw": off_kw,
                    "official_url": url,
                    "batteryKWh": t.get("battery_kwh"),
                    "battery_source": (
                        "oem_official_same_year" if t.get("battery_kwh") is not None else None
                    ),
                    "commercial_name": t["name"],
                    "commercial_url": url,
                    "variantVersionIndex": None,
                    "mergedFromIds": old_ids if len(old_ids) > 1 else None,
                }
            )
            new_variants.append(ref)
            table_rows.append(
                {
                    "parentId": pid,
                    "oldIds": old_ids,
                    "newId": new_id,
                    "official": t["name"],
                    "official_kw": off_kw,
                    "url": url,
                    "status": "matched" + ("_merged" if len(old_ids) > 1 else ""),
                }
            )

        for g in uniq_unmatched:
            unmatched_n += 1
            idx = version_n
            version_n += 1
            eea_kw = float(g["kw"])
            zr_min = int(g["wltpRangeKmMin"])
            zr_max = int(g["wltpRangeKmMax"])
            caption = range_caption(zr_min, zr_max)
            label = f"Versione {idx}"
            note = homologation_note(eea_kw)
            new_id = version_id(
                pid, eea_kw, bool(g.get("awd")), matched=False, slug=f"ver{idx}"
            )
            if g["id"] != new_id:
                # only alias if same EEA fingerprint set (renamed id) — keep alias for rename
                id_aliases[g["id"]] = new_id
            ref = dict(g)
            ref.update(
                {
                    "id": new_id,
                    "label": label,
                    "kw": round(eea_kw, 1),
                    "eea_kw": round(eea_kw, 1),
                    "rangeCaption": caption,
                    "eeaHomologationNote": note,
                    "official_matched": False,
                    "official_name": None,
                    "official_power_kw": None,
                    "official_url": url if entry else None,
                    "batteryKWh": None,
                    "battery_source": None,
                    "commercial_name": None,
                    "commercial_url": None,
                    "variantVersionIndex": idx,
                }
            )
            new_variants.append(ref)
            table_rows.append(
                {
                    "parentId": pid,
                    "oldIds": [g["id"]],
                    "newId": new_id,
                    "official": None,
                    "official_kw": None,
                    "url": url if entry else None,
                    "status": "unmatched",
                }
            )

    # Rebuild seed rows
    child_ids_new = {v["id"] for v in new_variants}
    out_rows: list[dict] = []
    cleared: set[str] = set()
    single_alias: dict[str, str] = {}
    children_by_parent: dict[str, list[dict]] = defaultdict(list)

    # Map new variant → child seed row
    for v in new_variants:
        pid = str(v["parentId"])
        parent = parent_by_id.get(pid)
        if not parent:
            continue
        child = dict(parent)
        child["id"] = v["id"]
        child["trim"] = v["label"]
        child["parentId"] = pid
        child["powerKw"] = float(v["kw"])
        child["energyConsumptionKWhPerKm"] = round(float(v["wh_per_km"]) / 1000.0, 6)
        child["wltpConsumptionKWh100km"] = round(float(v["wh_per_km"]) / 10.0, 2)
        child["wltpRangeKm"] = int(v["wltpRangeKmMin"])
        child["wltpRangeKmMax"] = int(v["wltpRangeKmMax"])
        child["energyConsumptionKWhPerKmMin"] = round(
            float(v["wh_per_km_min"]) / 1000.0, 6
        )
        child["variantRangeCaption"] = v["rangeCaption"]
        child["usesPrudentVariantBounds"] = True
        child["officialMatched"] = bool(v.get("official_matched"))
        child["eeaHomologationNote"] = v.get("eeaHomologationNote")
        child["batteryKWh"] = v.get("batteryKWh")
        child["sourceName"] = (
            "EEA co2cars EU Zr + official OEM label"
            if v.get("official_matched")
            else "EEA co2cars EU Zr (unmatched version)"
        )
        child["sourceUpdatedAt"] = datetime.now(timezone.utc).date().isoformat()
        children_by_parent[pid].append(child)

    for r in seed_rows:
        if r.get("parentId"):
            continue
        if str(r.get("id") or "") in TESLA_M3_2026_IDS:
            out_rows.append(dict(r))
            continue
        row = dict(r)
        kids = children_by_parent.get(str(r["id"]), [])
        if kids:
            row["wltpRangeKm"] = None
            cleared.add(str(r["id"]))
            if len(kids) == 1:
                single_alias[str(r["id"])] = kids[0]["id"]
        out_rows.append(row)
    for kids in children_by_parent.values():
        out_rows.extend(kids)

    after_parents = [
        r for r in out_rows if r.get("powertrain") == "ev" and not r.get("parentId")
    ]
    after_children = [r for r in out_rows if r.get("parentId")]
    after_child_parents = {
        str(c["parentId"]) for c in after_children if c.get("wltpRangeKm")
    }
    after_with_range = len(
        {
            str(r["id"])
            for r in after_parents
            if r.get("wltpRangeKm") or str(r["id"]) in after_child_parents
        }
    )

    top40_with_source = sum(1 for p in top40_ids if p in by_official)
    dist = Counter(len(v) for v in children_by_parent.values())

    refs_out = {
        "seedVersion": NEW_SEED_VERSION,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "source": "EEA Zr groups + official OEM trim labels",
        "rules": [
            "Official sources: manufacturer / press kit / tech PDF only",
            "Match 1:1 via WLTP ±3% or kW ±5 (+ traction when known)",
            "Matched label: '<name> · <official kW> kW'",
            "Unmatched / outside audit: 'Versione n' + EEA homologation note",
            "Drop EEA kW > official model max +5",
            "Tesla labels use system power (rule A)",
        ],
        "minShareOfParent": refs.get("minShareOfParent"),
        "minAbsoluteRegistrations": refs.get("minAbsoluteRegistrations"),
        "kwToleranceAbs": KW_TOL,
        "rangeTolerance": RANGE_TOL,
        "auditSet": audit,
        "stats": {
            "bev_model_years_with_range_before": before_with_range,
            "bev_model_years_with_range_after": after_with_range,
            "variant_groups_before": before_groups,
            "variant_groups_after": len(new_variants),
            "matched_groups": matched_n,
            "unmatched_groups": unmatched_n,
            "dropped_groups": dropped_n,
            "top40_with_official_source": top40_with_source,
            "top40_total": 40,
            "catalog_rows_after": len(out_rows),
            "groups_per_parent_distribution": {
                str(k): int(dist[k]) for k in sorted(dist)
            },
        },
        "singleVersionAliases": single_alias,
        "versionIdMigrationAliases": id_aliases,
        "clearedParentRangeIds": sorted(cleared),
        "variants": new_variants,
        "discardedGroups": discarded,
        "labelTable": table_rows,
        "noVariantParents": refs.get("noVariantParents") or [],
    }

    report = {
        "seedVersion": NEW_SEED_VERSION,
        "stats": refs_out["stats"],
        "top40WithSource": top40_with_source,
        "discardedCount": dropped_n,
        "matched": matched_n,
        "unmatched": unmatched_n,
    }

    print(json.dumps(refs_out["stats"], indent=2))
    print(f"top40_with_source={top40_with_source}/40")

    if args.dry_run:
        return 0

    eea.SEED_PATH.write_text(
        json.dumps(out_rows, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    # Merge single aliases with migration aliases (migration only for subset renames)
    # Do NOT put multi→single silent maps for removed ids into single_alias beyond singles.
    merged_aliases = dict(single_alias)
    # versionIdMigrationAliases stored separately in refs; CatalogVehicleIdResolver reads
    # ev_variant_single_aliases for parent→single and optional migration file.
    ALIAS_PATH.write_text(
        json.dumps(merged_aliases, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    mig_path = eea.REPO / "EVforME?" / "Data" / "ev_variant_migration_aliases.json"
    # Only keep aliases where old group's records ⊆ new (here: 1:1 renames)
    mig_path.write_text(
        json.dumps(id_aliases, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    bump_cdn(out_rows)
    REFS_PATH.write_text(json.dumps(refs_out, indent=2) + "\n", encoding="utf-8")
    REPORT_PATH.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    # Slim fixture
    slim_vars = new_variants[:25]
    focus = [
        v
        for v in new_variants
        if v.get("parentId")
        in {
            "hyundai-ioniq-5-2021",
            "ford-mustang-mach-e-2025",
            "dacia-spring-2023",
            "bmw-i4-2024",
        }
    ]
    seen: set[str] = set()
    slim: list[dict] = []
    for v in slim_vars + focus:
        if v["id"] in seen:
            continue
        seen.add(v["id"])
        slim.append(v)
    FIXTURE_REFS.write_text(
        json.dumps(
            {
                "seedVersion": NEW_SEED_VERSION,
                "generatedAt": refs_out["generatedAt"],
                "rules": refs_out["rules"],
                "stats": refs_out["stats"],
                "variants": slim,
                "note": "Slim fixture; full refs in scripts/cache/eea/",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"wrote seed v{NEW_SEED_VERSION} groups={len(new_variants)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
