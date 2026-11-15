#!/usr/bin/env python3
"""
PHEV wave2 batch3 corr1 (seed 87→88).

- Fill Golf GTE 2024 CS MAX + net battery from OEM newsroom 18398 (align seed↔manifest).
- Put exact consulted URLs + reject reasons into sourceName for every left_nil row.
- Scrub RAV4 2023 stale manus-verified battery claim from sourceName.
- Align manifest.cdn_bytes to real seed file bytes; bump seedVersion 88.
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
from catalog_confidence import POLICY_VERSION, assess_confidence  # noqa: E402
from check_catalog_phev_wave2_batch1 import cite_dating_ok, is_generic_url, urls_in  # noqa: E402
from lib.phev_manus_v76_validate import missing_calc_fields  # noqa: E402

SEED = REPO / "EVforME?" / "Data" / "vehicles.seed.quality.json"
CDN = REPO / "EVforME?" / "Data" / "catalog_cdn.json"
CACHE = REPO / "scripts" / "cache" / "eea"
MANIFEST = CACHE / "catalog_phev_wave2_batch3_manifest.json"
SOURCE_DAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")

NON_PHEV_SHA = "6b9038232bc51daabc9e259fc0dab170f787984d4dfb8f597e309fe50155b4dc"
CALC_FIELDS = (
    "fuelConsumptionLPerKm",
    "energyConsumptionKWhPerKm",
    "wltpRangeKm",
    "batteryKWh",
)

GOLF_URL = (
    "https://www.volkswagen-newsroom.com/en/press-releases/"
    "dynamic-and-with-a-long-range-golf-gte-and-golf-ehybrid-now-available-to-order-18398"
)
GOLF_DATE = "2024-05-16"
RAV4_MY23 = (
    "https://newsroom.toyota.it/download/1316286/"
    "20230101rav4plug-inhybridmy23schedatecnica.pdf"
)

# Month-only stamps that previously used invented day-01 → store null.
NULLIFY_DAY01 = {
    ("land-rover-range-rover-evoque-phev-2022", "2021-06-01"),  # Juni 2021
    ("lexus-nx-phev-450h-2024", "2024-01-01"),
    ("peugeot-308-phev-2022", "2023-04-01"),  # April 2023 edition month
    ("volkswagen-tiguan-phev-ehybrid-2024", "2024-09-01"),  # Stand September 2024
    ("volkswagen-tiguan-phev-ehybrid-2023", "2024-09-01"),
    ("volkswagen-tiguan-phev-ehybrid-2022", "2024-09-01"),
}


def finalize(row: dict) -> None:
    miss = missing_calc_fields(row)
    row["missingCalcFields"] = miss
    row["catalogDataIncomplete"] = bool(miss)
    score, ev = assess_confidence(row)
    row["confidenceScore"] = score
    row["confidenceEvidence"] = ev
    row["confidencePolicyVersion"] = POLICY_VERSION


def set_field(row: dict, field: str, value, cite: str, date: str) -> None:
    urls = urls_in(cite) or [cite]
    if any(is_generic_url(u) for u in urls):
        raise SystemExit(f"generic URL rejected: {cite}")
    year = int(row["year"])
    homolog = row.get("dataDerivedFromSameHomologationYear")
    hy = int(homolog) if homolog is not None else None
    if not cite_dating_ok(cite, date, year, homolog_year=hy):
        raise SystemExit(f"dating rejected {row['id']}.{field}: {date}")
    row[field] = value
    fs = dict(row.get("fieldSources") or {})
    fd = dict(row.get("fieldSourceDates") or {})
    fs[field] = cite
    fd[field] = date
    row["fieldSources"] = fs
    row["fieldSourceDates"] = fd


def tech_blob(rows: list[dict]) -> str:
    conf = {
        "confidenceScore",
        "confidenceScoreLegacy",
        "confidencePolicyVersion",
        "confidenceEvidence",
    }
    cleaned = [{k: v for k, v in r.items() if k not in conf} for r in rows]
    return json.dumps(cleaned, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def nil_source_fragment(reason: str, consulted: list[dict]) -> str:
    parts = [f"wave2-batch3 left_nil: {reason}"]
    for c in consulted:
        url = c.get("url") or ""
        rej = c.get("reject_for") or "rejected"
        if not url:
            continue
        parts.append(f"consulted {url} — {rej}")
    return " | ".join(parts)


def scrub_and_set_nil_source(row: dict, reason: str, consulted: list[dict]) -> None:
    """Replace stale wave2-batch3 / manus battery claims; append left_nil cite."""
    sn = row.get("sourceName") or ""
    parts = [p.strip() for p in sn.split(";") if p.strip()]
    keep: list[str] = []
    for p in parts:
        low = p.lower()
        if "wave2-batch3 left_nil" in low:
            continue
        if "wave2-batch3 scrub" in low:
            continue
        if "manus-verified v76: batterykwh=18.1" in low:
            continue
        # Drop prior Golf cite that pointed at mismatched / wrong reject URL.
        if "golf-gte-and-golf-ehybrid-now-available-to-order-18398" in low and row["id"].startswith(
            "volkswagen-golf"
        ):
            continue
        if "golf-gte-and-golf-r-variant" in low:
            continue
        keep.append(p)
    frag = nil_source_fragment(reason, consulted)
    if frag not in keep:
        keep.append(frag)
    # de-dupe
    seen: set[str] = set()
    out: list[str] = []
    for p in keep:
        if p not in seen:
            seen.add(p)
            out.append(p)
    row["sourceName"] = "; ".join(out)


def sanitize_consulted(rid: str, consulted: list[dict]) -> list[dict]:
    out = []
    for c in consulted:
        cc = dict(c)
        sd = cc.get("sourceDate")
        if sd and (rid, sd) in NULLIFY_DAY01:
            cc["sourceDate"] = None
            rej = cc.get("reject_for") or ""
            if "day-01" not in rej.lower() and "month-only" not in rej.lower():
                cc["reject_for"] = (rej + "; sourceDate null — month-only (no invented day-01)").strip("; ")
        out.append(cc)
    return out


def append_source(row: dict, text: str) -> None:
    sn = row.get("sourceName") or ""
    parts = [p.strip() for p in sn.split(";") if p.strip()]
    # Drop mismatched Golf /r-variant and stale pure-nil golf cite when filling.
    keep = []
    for p in parts:
        low = p.lower()
        if "golf-gte-and-golf-r-variant" in low:
            continue
        if "wave2-batch3 left_nil" in low and "golf" in row["id"]:
            continue
        keep.append(p)
    if text not in keep:
        keep.append(text)
    seen: set[str] = set()
    out: list[str] = []
    for p in keep:
        if p not in seen:
            seen.add(p)
            out.append(p)
    row["sourceName"] = "; ".join(out)


def main() -> None:
    seed = json.loads(SEED.read_text(encoding="utf-8"))
    by_id = {r["id"]: r for r in seed}
    ids_before = [r["id"] for r in seed]
    assert len(seed) == 6977

    cdn = json.loads(CDN.read_text(encoding="utf-8"))
    if int(cdn.get("seedVersion") or 0) != 87:
        raise SystemExit(f"expected seed 87 baseline, got {cdn.get('seedVersion')}")

    man = json.loads(MANIFEST.read_text(encoding="utf-8"))
    batch3_ids = list(man["batch3_ids"])
    assert len(batch3_ids) == 36

    m3_before = {
        r["id"]: json.dumps(r, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        for r in seed
        if r["id"].startswith("tesla-model-3") and r.get("year") == 2026
    }
    assert len(m3_before) == 4
    non_phev_sha_before = hashlib.sha256(
        tech_blob([r for r in seed if r.get("powertrain") != "phev"]).encode()
    ).hexdigest()
    if non_phev_sha_before != NON_PHEV_SHA:
        raise SystemExit(f"non-PHEV SHA unexpected: {non_phev_sha_before}")

    # Freeze batch1+batch2 + non-lotto outside batch3.
    lotto = set(batch3_ids)
    # Load batch1/2 ids from their manifests so we can assert byte-identity.
    b1 = json.loads((CACHE / "catalog_phev_wave2_batch1_manifest.json").read_text())
    b2 = json.loads((CACHE / "catalog_phev_wave2_batch2_manifest.json").read_text())
    batch1_ids = set(b1.get("batch1_ids") or [])
    batch1_ids |= {e["id"] for e in (b1.get("extras") or []) if isinstance(e, dict) and e.get("id")}
    batch2_ids = set(b2.get("batch2_ids") or [])
    batch2_ids |= {e["id"] for e in (b2.get("extras") or []) if isinstance(e, dict) and e.get("id")}
    protected = (batch1_ids | batch2_ids) - lotto
    protected_before = {
        i: json.dumps(by_id[i], sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        for i in protected
        if i in by_id
    }
    outside_before = {
        r["id"]: json.dumps(r, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        for r in seed
        if r["id"] not in lotto
    }

    # Snapshot OK fills that must not change (except we may touch sourceName only on left_nil).
    ok_partial_ids = {
        "land-rover-range-rover-evoque-phev-2023",
        "mazda-cx-60-phev-2023",
        "mitsubishi-eclipse-cross-phev-2023",
        "peugeot-308-phev-2023",
    }
    ok_before = {
        i: {
            f: by_id[i].get(f)
            for f in CALC_FIELDS + ("fieldSources", "fieldSourceDates", "energyIsWeighted")
        }
        for i in ok_partial_ids
    }

    changed_fields = list(man.get("changed_fields") or [])
    partial = [e for e in (man.get("partial") or []) if e["id"] != "volkswagen-golf-gte-phev-2024"]
    completed = list(man.get("completed") or [])
    homolog_reuse = list(man.get("homolog_reuse") or [])
    battery_convention_pass = list((man.get("battery_convention") or {}).get("thisPass") or [])

    # --- Golf GTE 2024 fill from 18398 ----------------------------------------------------
    golf = by_id["volkswagen-golf-gte-phev-2024"]
    cite_cs = (
        "Volkswagen Newsroom press 05/16/24 (media info Golf GTE / eHybrid) — Golf GTE column: "
        "fuel consumption battery discharged combined 5.4-5.3 l/100km → MAX 5.4 → 0.054 L/km; "
        f"variant Golf GTE (not eHybrid 5.3-5.0) {GOLF_URL}"
    )
    cite_bat = (
        "Volkswagen Newsroom press 05/16/24 — new 19.7 kWh battery (net / predecessor: 10.6 kWh) "
        f"for Golf GTE / eHybrid plug-in hybrids; store net 19.7 {GOLF_URL}"
    )
    set_field(golf, "fuelConsumptionLPerKm", 0.054, cite_cs, GOLF_DATE)
    set_field(golf, "batteryKWh", 19.7, cite_bat, GOLF_DATE)
    # energy weighted-only → stay nil; range "up to 131" → stay nil
    append_source(
        golf,
        f"wave2-batch3 corr1 Golf GTE CS discharged MAX 0.054 + net battery 19.7 — {GOLF_URL}",
    )
    golf["sourceUpdatedAt"] = SOURCE_DAY
    finalize(golf)
    # refresh changed_fields: drop any prior golf nil/scrub notes; add fills
    changed_fields = [c for c in changed_fields if c.get("id") != golf["id"]]
    changed_fields.append(
        {
            "id": golf["id"],
            "field": "fuelConsumptionLPerKm",
            "value": 0.054,
            "url": GOLF_URL,
            "sourceDate": GOLF_DATE,
            "variant": "Golf GTE",
            "note": "battery discharged combined 5.4-5.3 → MAX 5.4",
        }
    )
    changed_fields.append(
        {
            "id": golf["id"],
            "field": "batteryKWh",
            "value": 19.7,
            "url": GOLF_URL,
            "sourceDate": GOLF_DATE,
            "variant": "Golf GTE",
            "note": "19.7 kWh battery (net)",
        }
    )
    partial.append(
        {
            "id": golf["id"],
            "filled": {"fuelConsumptionLPerKm": 0.054, "batteryKWh": 19.7},
            "left_nil": ["energyConsumptionKWhPerKm", "wltpRangeKm"],
            "note": "CS discharged MAX + net battery from 18398; energy weighted-only; range up-to 131 unused",
        }
    )
    battery_convention_pass = [
        e for e in battery_convention_pass if e.get("id") != golf["id"]
    ]
    battery_convention_pass.append(
        {
            "id": golf["id"],
            "batteryKWh": 19.7,
            "note": "19.7 kWh battery (net / predecessor: 10.6 kWh) on VW Newsroom 05/16/24",
        }
    )

    # --- Rebuild left_nil (all except golf) with sanitized consulted + seed sourceName ----
    left_nil: list[dict] = []
    for entry in man.get("left_nil") or []:
        rid = entry["id"]
        if rid == "volkswagen-golf-gte-phev-2024":
            continue
        row = by_id[rid]
        consulted = sanitize_consulted(rid, list(entry.get("consulted") or []))
        reason = entry.get("reason") or "OEM same-MY fields not attachable"
        # RAV4: keep scrub reason explicit; ensure MY23 URL present.
        if rid == "toyota-rav4-phev-2023":
            reason = (
                "MY23 IT scheda Litio Capacità 18.1 kWh without net/usable label → battery nil (scrubbed); "
                "WLTP fuel weighted; no EAER combined on sheet"
            )
            # Ensure MY23 URL is first consulted.
            if not any(RAV4_MY23 in (c.get("url") or "") for c in consulted):
                consulted.insert(
                    0,
                    {
                        "url": RAV4_MY23,
                        "sourceDate": "2023-01-03",
                        "reject_for": "Litio Capacità 18.1 unlabeled net/usable → scrubbed; weighted fuel; no EAER",
                    },
                )
        if not consulted:
            raise SystemExit(f"{rid}: missing consulted")
        if all(is_generic_url(c.get("url") or "") for c in consulted):
            raise SystemExit(f"{rid}: consulted only generic")
        scrub_and_set_nil_source(row, reason, consulted)
        # Guard: every consulted URL must appear in sourceName
        sn = row.get("sourceName") or ""
        for c in consulted:
            u = c.get("url") or ""
            if u and u not in sn:
                raise SystemExit(f"{rid}: consulted URL missing from sourceName: {u}")
        if rid == "toyota-rav4-phev-2023" and "manus-verified v76" in sn.lower():
            raise SystemExit("RAV4 still has manus-verified v76 battery claim")
        if not any(not is_generic_url(u) for u in urls_in(sn)):
            raise SystemExit(f"{rid}: sourceName has no non-generic consulted URL")
        row["sourceUpdatedAt"] = SOURCE_DAY
        finalize(row)
        already = {f: row.get(f) for f in CALC_FIELDS if row.get(f) is not None}
        nil_e = {
            "id": rid,
            "brand": row.get("brand"),
            "model": row.get("model"),
            "year": row.get("year"),
            "market": row.get("market"),
            "missing": missing_calc_fields(row),
            "reason": reason,
            "consulted": consulted,
        }
        if entry.get("fieldReasons"):
            nil_e["fieldReasons"] = entry["fieldReasons"]
        if already:
            nil_e["alreadyPresent"] = already
        left_nil.append(nil_e)

    # OK partial fields unchanged
    for i, before in ok_before.items():
        now = by_id[i]
        for f, v in before.items():
            if now.get(f) != v:
                raise SystemExit(f"OK fill mutated {i}.{f}: {before[f]!r} -> {now.get(f)!r}")

    # invariants
    if [r["id"] for r in seed] != ids_before:
        raise SystemExit("id order changed")
    for mid, blob in m3_before.items():
        now = json.dumps(by_id[mid], sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        if now != blob:
            raise SystemExit(f"Model 3 mutated: {mid}")
    for oid, blob in outside_before.items():
        # outside_before includes protected; but we only mutate lotto — re-check
        if oid in lotto:
            continue
        now = json.dumps(by_id[oid], sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        if now != blob:
            raise SystemExit(f"non-lotto mutated: {oid}")
    for pid, blob in protected_before.items():
        now = json.dumps(by_id[pid], sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        if now != blob:
            raise SystemExit(f"batch1/2 protected mutated: {pid}")
    non_phev_sha = hashlib.sha256(
        tech_blob([r for r in seed if r.get("powertrain") != "phev"]).encode()
    ).hexdigest()
    if non_phev_sha != NON_PHEV_SHA:
        raise SystemExit("non-PHEV SHA drift")

    covered = (
        {e["id"] for e in completed}
        | {e["id"] for e in partial}
        | {e["id"] for e in homolog_reuse}
        | {e["id"] for e in left_nil}
    )
    missing = [i for i in batch3_ids if i not in covered]
    if missing:
        raise SystemExit(f"batch3 uncovered: {missing}")
    if len(left_nil) != 31:
        raise SystemExit(f"expected 31 left_nil after Golf fill, got {len(left_nil)}")
    if len(partial) != 5:
        raise SystemExit(f"expected 5 partial, got {len(partial)}")

    # Write seed compact
    SEED.write_text(
        json.dumps(seed, separators=(",", ":"), ensure_ascii=False),
        encoding="utf-8",
    )
    seed_bytes = SEED.stat().st_size

    cdn_out = {
        **cdn,
        "rows": 6977,
        "bytes": seed_bytes,
        "seedVersion": 88,
        "prevSeedVersion": 87,
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        "note": (
            "seedVersion 88: PHEV wave2 batch3 corr1 — Golf GTE CS 0.054 + net 19.7 from 18398; "
            "left_nil sourceName consulted URLs; RAV4 manus-verified scrub; "
            "api/static sync deferred at seed 77"
        ),
    }
    CDN.write_text(json.dumps(cdn_out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    man_out = {
        **man,
        "seedVersion": 88,
        "prevSeedVersion": 87,
        "prevManifestSeed": 87,
        "cdn_bytes": seed_bytes,
        "sourceDay": SOURCE_DAY,
        "prKind": "phev-wave2-batch3-corr1",
        "completed": completed,
        "partial": partial,
        "homolog_reuse": homolog_reuse,
        "left_nil": left_nil,
        "changed_fields": changed_fields,
        "battery_convention": {
            "catalogConvention": "net/usable",
            "thisPass": battery_convention_pass,
        },
        "non_phev_tech_sha": NON_PHEV_SHA,
        "counts": {
            "completed": len(completed),
            "partial": len(partial),
            "homolog_reuse": len(homolog_reuse),
            "left_nil": len(left_nil),
        },
        "corr1": {
            "golf_fill": GOLF_URL,
            "left_nil_sourceName": "consulted URLs + reject reasons in seed sourceName",
            "rav4_scrub_sourceName": "removed manus-verified v76 batteryKWh=18.1",
            "cdn_bytes_aligned": seed_bytes,
        },
    }
    MANIFEST.write_text(json.dumps(man_out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "seedVersion": 88,
                "cdn_bytes": seed_bytes,
                "partial": len(partial),
                "left_nil": len(left_nil),
                "golf_cs": 0.054,
                "golf_bat": 19.7,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
