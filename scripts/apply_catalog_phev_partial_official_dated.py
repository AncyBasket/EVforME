#!/usr/bin/env python3
"""
Seed +1: fix PHEV partial official sources to dated docs / archive.org snapshots.

Rules for year X:
  (a) document dated in year X or year in filename (e.g. PL_07_24, MY24)
  (b) web.archive.org/web/YYYYMMDD.../ with YYYY == X
  (c) X == current model year 2026

Live OEM pages and generic model-list URLs are rejected for years ≠ 2026.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

REPO = Path(__file__).resolve().parents[1]
SEED = REPO / "EVforME?" / "Data" / "vehicles.seed.quality.json"
CDN = REPO / "EVforME?" / "Data" / "catalog_cdn.json"
CACHE = REPO / "scripts" / "cache" / "eea"
HOMOLOG = CACHE / "catalog_phev_homologation_map.json"
RANK = CACHE / "catalog_phev_it_incomplete_rank.json"
MANIFEST = CACHE / "catalog_phev_partial_official_dated_manifest.json"
SOURCE_DAY = "2026-10-27"
CURRENT_MY = 2026

CALC_FIELDS = (
    "fuelConsumptionLPerKm",
    "energyConsumptionKWhPerKm",
    "wltpRangeKm",
    "batteryKWh",
)

# Rows previously filled that must be scrubbed/rebuilt this wave.
TOUCH_IDS = [
    "bmw-x1-phev-xdrive25e-2024",
    "bmw-x1-phev-xdrive25e-2023",
    "volvo-xc60-phev-recharge-2024",
    "volvo-xc60-phev-recharge-2023",
    "toyota-c-hr-phev-2024",
    "jeep-renegade-phev-4xe-2024",
    "jeep-renegade-phev-4xe-2023",
    "jeep-compass-phev-4xe-2024",
    "jeep-compass-phev-4xe-2023",
    "cupra-formentor-phev-e-hybrid-2024",
    "audi-q3-sportback-phev-45-tfsi-e-2024",
    "audi-q3-sportback-phev-45-tfsi-e-2023",
    "bmw-serie-2-active-tourer-225e-xdrive-2023",
]


def archive_url(ts: str, original: str) -> str:
    return f"https://web.archive.org/web/{ts}/{original}"


def missing_calc_fields(r: dict) -> list[str]:
    miss: list[str] = []
    cs = r.get("fuelConsumptionLPerKm")
    if cs is None or float(cs) * 100 < 3.0:
        miss.append("fuelConsumptionLPerKm")
    e = r.get("energyConsumptionKWhPerKm")
    if e is None or r.get("energyIsWeighted") is True:
        miss.append("energyConsumptionKWhPerKm")
    if r.get("wltpRangeKm") is None:
        miss.append("wltpRangeKm")
    if r.get("batteryKWh") is None:
        miss.append("batteryKWh")
    return miss


def clear_partial(row: dict) -> list[str]:
    """Remove prior partial calc fields + provenance; return removed field names."""
    removed = []
    for k in CALC_FIELDS:
        if row.get(k) is not None:
            removed.append(k)
        row[k] = None
    row.pop("fieldSources", None)
    row.pop("fieldSourceDates", None)
    row.pop("dataDerivedFromSameHomologationYear", None)
    row.pop("missingCalcFields", None)
    # keep weighted* informational if present
    row["catalogDataIncomplete"] = True
    row["energyIsWeighted"] = True if row.get("weightedEnergyConsumptionKWhPerKm") is not None else None
    return removed


GENERIC_URL_HINTS = (
    "/neuwagen.html",
    "/brand/de/neuwagen",
    "/models.html",
    "/modelle",
)


def is_generic_url(url: str) -> bool:
    u = url.lower()
    path = urlparse(u).path.rstrip("/")
    if path in ("", "/", "/de", "/de/neuwagen", "/neuwagen"):
        return True
    return any(h in u for h in GENERIC_URL_HINTS)


def source_year_ok(url: str, source_date: str, vehicle_year: int) -> bool:
    """Return True if source is valid for vehicle_year."""
    if vehicle_year == CURRENT_MY:
        return True
    # (b) archive snapshot
    m = re.search(r"web\.archive\.org/web/(\d{8})", url)
    if m:
        return int(m.group(1)[:4]) == int(vehicle_year)
    # (a) explicit sourceDate year
    if source_date and len(source_date) >= 4 and source_date[:4].isdigit():
        if int(source_date[:4]) == int(vehicle_year):
            return True
    # (a) year token in filename / URL
    fname = urlparse(url).path.split("/")[-1].lower()
    tokens = [
        f"_{str(vehicle_year)[2:]}",  # _24
        f"pl_{str(vehicle_year)[2:]}",
        f"my{str(vehicle_year)[2:]}",
        f"my{vehicle_year}",
        str(vehicle_year),
        f"0{str(vehicle_year)[2:]}_",  # 07_24 style already covered
    ]
    blob = fname + " " + url.lower()
    if f"pl_{str(vehicle_year)[2:]}" in blob or f"_{str(vehicle_year)[2:]}_" in blob:
        return True
    if f"my{str(vehicle_year)[2:]}" in blob or f"my{vehicle_year}" in blob:
        return True
    if re.search(rf"(^|[^0-9]){vehicle_year}([^0-9]|$)", blob):
        return True
    return False


def apply_field(
    row: dict,
    field: str,
    value: Any,
    host: str,
    url: str,
    source_date: str,
    note: str,
) -> None:
    year = int(row["year"])
    if is_generic_url(url):
        raise SystemExit(f"generic URL rejected for {row['id']}.{field}: {url}")
    if not source_year_ok(url, source_date, year):
        raise SystemExit(
            f"source year invalid for {row['id']}.{field} year={year} date={source_date} url={url}"
        )
    if field == "fuelConsumptionLPerKm" and float(value) * 100 < 3.0:
        raise SystemExit(f"CS<3 {row['id']}")
    if field == "energyConsumptionKWhPerKm":
        raise SystemExit("never set unweighted CD from this wave without rein-elektrisch doc")
    row[field] = value
    fs = dict(row.get("fieldSources") or {})
    fd = dict(row.get("fieldSourceDates") or {})
    fs[field] = f"{host} {year} {url}"
    fd[field] = source_date
    row["fieldSources"] = fs
    row["fieldSourceDates"] = fd
    sn = row.get("sourceName") or ""
    bit = f"{note} — {url} ({source_date})"
    if bit not in sn:
        row["sourceName"] = f"{sn}; {bit}".strip("; ").strip()
    row["sourceUpdatedAt"] = SOURCE_DAY
    row["market"] = row.get("market") or "IT"


def finalize(row: dict) -> None:
    if row.get("energyConsumptionKWhPerKm") is None and row.get(
        "weightedEnergyConsumptionKWhPerKm"
    ) is not None:
        row["energyIsWeighted"] = True
    miss = missing_calc_fields(row)
    row["missingCalcFields"] = miss
    row["catalogDataIncomplete"] = bool(miss)
    if miss and row.get("confidenceScore") is None:
        row["confidenceScore"] = 0.7


def best_shared(
    family: str, src_year: int, dst_year: int, dst_power: float, shared: dict, ep_tol: float
) -> dict | None:
    cands = []
    for sh in shared.get(family) or []:
        years = {int(y): n for y, n in (sh.get("years") or {}).items()}
        if src_year not in years or dst_year not in years:
            continue
        if not (sh.get("TAN") or "").strip():
            continue
        ep = sh.get("ep")
        if ep is None:
            continue
        if abs(float(ep) - float(dst_power)) > ep_tol:
            continue
        score = float(years[src_year]) + float(years[dst_year])
        cands.append((score, sh))
    if not cands:
        return None
    cands.sort(key=lambda x: -x[0])
    return cands[0][1]


def main() -> None:
    seed = json.loads(SEED.read_text(encoding="utf-8"))
    by_id = {r["id"]: r for r in seed}
    ids_before = [r["id"] for r in seed]
    m3_before = {
        r["id"]: json.dumps(r, sort_keys=True)
        for r in seed
        if r["id"].startswith("tesla-model-3") and r.get("year") == 2026
    }

    parents = [r for r in seed if r.get("powertrain") == "phev" and not r.get("parentId")]

    def counts():
        complete = sum(1 for r in parents if not r.get("catalogDataIncomplete"))
        only_kwh = multi = 0
        for r in parents:
            if not r.get("catalogDataIncomplete"):
                continue
            miss = missing_calc_fields(r)
            if miss == ["energyConsumptionKWhPerKm"]:
                only_kwh += 1
            else:
                multi += 1
        return complete, only_kwh, multi

    before_c, before_kwh, before_multi = counts()

    removed_log: list[dict] = []
    for rid in TOUCH_IDS:
        row = by_id[rid]
        removed = clear_partial(row)
        if removed:
            removed_log.append({"id": rid, "removedFields": removed, "reason": "rebuild_dated_sources"})

    fields_saved: list[dict] = []

    def save(rid: str, field: str, host: str, url: str, date: str, via: str, tan: str | None = None):
        fields_saved.append(
            {
                "id": rid,
                "field": field,
                "host": host,
                "year": int(by_id[rid]["year"]),
                "url": url,
                "sourceDate": date,
                "value": by_id[rid][field],
                "via": via,
                **({"TAN": tan} if tan else {}),
            }
        )

    # --- Same-MY dated fills ---
    # Volvo XC60 2024 — press 01.06.2024 (dated document)
    volvo_url = "https://www.volvocars.com/de/media/press-releases/8C5F873BBE0D5162/"
    volvo_date = "2024-06-01"
    r = by_id["volvo-xc60-phev-recharge-2024"]
    apply_field(r, "fuelConsumptionLPerKm", 0.082, "volvocars.com", volvo_url, volvo_date, "Volvo XC60 PHEV press 01.06.2024 CS bei entladener Batterie 8,2–7,0")
    apply_field(r, "wltpRangeKm", 80, "volvocars.com", volvo_url, volvo_date, "Volvo XC60 PHEV press bis 80 km")
    apply_field(r, "batteryKWh", 18.8, "volvocars.com", volvo_url, volvo_date, "Volvo XC60 PHEV press 18,8 kWh")
    r["weightedEnergyConsumptionKWhPerKm"] = 0.209
    r["weightedFuelConsumptionLPerKm"] = 0.014
    finalize(r)
    for f in ("fuelConsumptionLPerKm", "wltpRangeKm", "batteryKWh"):
        save(r["id"], f, "volvocars.com", volvo_url, volvo_date, "same_my")

    # Toyota C-HR 2024 — filename PL_07_24
    toy_url = "https://www.toyota.de/content/dam/toyota/nmsc/germany/downloads/toyota-c-hr/Toyota_C-HR_PL_07_24_j.pdf"
    toy_date = "2024-07-01"
    r = by_id["toyota-c-hr-phev-2024"]
    apply_field(r, "fuelConsumptionLPerKm", 0.049, "toyota.de", toy_url, toy_date, "Toyota C-HR PHEV Preisliste 07/2024 CS 4,9")
    apply_field(r, "wltpRangeKm", 66, "toyota.de", toy_url, toy_date, "Toyota C-HR PHEV Preisliste EAER 66–67 → 66")
    r["weightedEnergyConsumptionKWhPerKm"] = 0.153
    r["weightedFuelConsumptionLPerKm"] = 0.009
    finalize(r)
    for f in ("fuelConsumptionLPerKm", "wltpRangeKm"):
        save(r["id"], f, "toyota.de", toy_url, toy_date, "same_my")

    # Jeep Renegade 2024 — archive June 2024 hybrid-suv
    jeep_hyb = archive_url("20240620055110", "https://www.jeep.de/hybrid-suv")
    jeep_hyb_date = "2024-06-20"
    r = by_id["jeep-renegade-phev-4xe-2024"]
    apply_field(
        r,
        "fuelConsumptionLPerKm",
        0.075,  # 6,9–7,5 archive → max (prudente CS)
        "jeep.de",
        jeep_hyb,
        jeep_hyb_date,
        "Jeep Renegade 4xe archive.org 20240620 hybrid-suv CS bei entladener Batterie 6,9–7,5",
    )
    r["weightedEnergyConsumptionKWhPerKm"] = 0.22
    r["weightedFuelConsumptionLPerKm"] = 0.02
    finalize(r)
    save(r["id"], "fuelConsumptionLPerKm", "jeep.de", jeep_hyb, jeep_hyb_date, "same_my")

    # Jeep Compass 2024 — CS from same June 2024 archive; range/bat from MY24 listino (my24 in filename)
    stellantis_url = (
        "https://www.media.stellantis.com/uploads/fr/attachment/7783/"
        "tarifpublicjeeprcompassmy242023e19decembre2023-65820ebe62db4.pdf"
    )
    stellantis_date = "2023-12-19"  # MY24 in filename → valid for vehicle year 2024
    r = by_id["jeep-compass-phev-4xe-2024"]
    apply_field(
        r,
        "fuelConsumptionLPerKm",
        0.076,  # 7,0–7,6 archive
        "jeep.de",
        jeep_hyb,
        jeep_hyb_date,
        "Jeep Compass 4xe archive.org 20240620 hybrid-suv CS 7,0–7,6",
    )
    apply_field(
        r,
        "wltpRangeKm",
        48,  # prudent low of 48–52 MY24 listino
        "media.stellantis.com",
        stellantis_url,
        stellantis_date,
        "Jeep Compass MY24 listino FR 19/12/2023 EAER 48–52 → 48",
    )
    apply_field(
        r,
        "batteryKWh",
        11.4,
        "media.stellantis.com",
        stellantis_url,
        stellantis_date,
        "Jeep Compass MY24 listino FR battery 11,4 kWh",
    )
    r["weightedEnergyConsumptionKWhPerKm"] = 0.167
    r["weightedFuelConsumptionLPerKm"] = 0.021
    finalize(r)
    save(r["id"], "fuelConsumptionLPerKm", "jeep.de", jeep_hyb, jeep_hyb_date, "same_my")
    save(r["id"], "wltpRangeKm", "media.stellantis.com", stellantis_url, stellantis_date, "same_my")
    save(r["id"], "batteryKWh", "media.stellantis.com", stellantis_url, stellantis_date, "same_my")

    # BMW X1 2024 — EnVKV 05/2024 dated PDF (also archived June 2024); CS only
    bmw_envkv = (
        "https://www.bmw.de/content/dam/bmw/marketDE/bmw_de/mybmw/bmw-efficientdynamics/"
        "SP-1619_CO2_A4_Vergleich_Emissionswerte_05_2024_X4_05.pdf.coredownload.inline.pdf"
    )
    # Prefer archive snapshot of the same dated file
    bmw_envkv_arch = archive_url(
        "20240604155829",
        "https://www.bmw.de/content/dam/bmw/marketDE/bmw_de/mybmw/bmw-efficientdynamics/"
        "SP-1619_CO2_A4_Vergleich_Emissionswerte_05_2024_X4_05.pdf.coredownload.inline.pdf",
    )
    bmw_date = "2024-05-01"
    r = by_id["bmw-x1-phev-xdrive25e-2024"]
    apply_field(
        r,
        "fuelConsumptionLPerKm",
        0.068,  # EnVKV 6,8–6,3
        "bmw.de",
        bmw_envkv_arch,
        bmw_date,
        "BMW X1 xDrive25e EnVKV 05/2024 (archive 20240604) CS bei entladener Batterie 6,8–6,3",
    )
    # range/battery: live preisliste rejected → stay nil
    r["weightedEnergyConsumptionKWhPerKm"] = 0.193
    r["weightedFuelConsumptionLPerKm"] = 0.011
    finalize(r)
    save(r["id"], "fuelConsumptionLPerKm", "bmw.de", bmw_envkv_arch, bmw_date, "same_my")

    # Cupra / Audi / 225e: stay cleared (no valid dated source / no homologation)
    for rid, reason in [
        ("cupra-formentor-phev-e-hybrid-2024", "live_produktkatalog_no_2024_archive"),
        ("audi-q3-sportback-phev-45-tfsi-e-2024", "generic_model_list_url"),
        ("audi-q3-sportback-phev-45-tfsi-e-2023", "derived_from_invalid_2024"),
        (
            "bmw-serie-2-active-tourer-225e-xdrive-2023",
            "envkv_052024_without_identical_EEA_homologation_2023_2024",
        ),
    ]:
        finalize(by_id[rid])
        removed_log.append({"id": rid, "removedFields": CALC_FIELDS, "reason": reason})

    # --- Homologation copies (source must have dated fieldSources; no chain) ---
    homolog = json.loads(HOMOLOG.read_text(encoding="utf-8"))
    shared = homolog.get("shared") or {}
    derived: list[dict] = []
    HOMOLOG_DERIVE = [
        {
            "dst_id": "bmw-x1-phev-xdrive25e-2023",
            "src_id": "bmw-x1-phev-xdrive25e-2024",
            "family": "bmw-x1-25e",
            "ep_tol": 2.0,
        },
        {
            "dst_id": "volvo-xc60-phev-recharge-2023",
            "src_id": "volvo-xc60-phev-recharge-2024",
            "family": "volvo-xc60",
            "ep_tol": 8.0,
        },
        {
            "dst_id": "jeep-renegade-phev-4xe-2023",
            "src_id": "jeep-renegade-phev-4xe-2024",
            "family": "jeep-renegade",
            "ep_tol": 6.0,
        },
        {
            "dst_id": "jeep-compass-phev-4xe-2023",
            "src_id": "jeep-compass-phev-4xe-2024",
            "family": "jeep-compass",
            "ep_tol": 12.0,
        },
    ]

    for d in HOMOLOG_DERIVE:
        dst = by_id[d["dst_id"]]
        src = by_id[d["src_id"]]
        if src.get("dataDerivedFromSameHomologationYear") is not None:
            raise SystemExit(f"chain {d['src_id']}")
        sh = best_shared(
            d["family"],
            int(src["year"]),
            int(dst["year"]),
            float(dst.get("powerKw") or 0),
            shared,
            float(d.get("ep_tol") or 2.0),
        )
        if not sh:
            print(f"SKIP homolog {d['dst_id']}: no fingerprint")
            finalize(dst)
            continue
        src_fs = src.get("fieldSources") or {}
        src_fd = src.get("fieldSourceDates") or {}
        copied = []
        for k in CALC_FIELDS:
            if src.get(k) is None or k not in src_fs:
                continue
            if k == "energyConsumptionKWhPerKm":
                continue
            if k == "fuelConsumptionLPerKm" and float(src[k]) * 100 < 3.0:
                continue
            dst[k] = src[k]
            tan, va, ve = sh["TAN"], sh["Va"], sh["Ve"]
            fs = dict(dst.get("fieldSources") or {})
            fd = dict(dst.get("fieldSourceDates") or {})
            fs[k] = (
                f"{src_fs[k]}; stessa omologazione EEA {tan} {va}/{ve}, "
                f"anni {dst['year']} e {src['year']}"
            )
            fd[k] = src_fd.get(k) or ""
            dst["fieldSources"] = fs
            dst["fieldSourceDates"] = fd
            copied.append(k)
            save(
                d["dst_id"],
                k,
                "eea+oem",
                src_fs[k],
                fd[k],
                "homologation",
                tan=tan,
            )
        for wk in ("weightedFuelConsumptionLPerKm", "weightedEnergyConsumptionKWhPerKm"):
            if src.get(wk) is not None:
                dst[wk] = src[wk]
        if copied:
            dst["dataDerivedFromSameHomologationYear"] = int(src["year"])
            dst["sourceUpdatedAt"] = SOURCE_DAY
            note = (
                f"stessa omologazione EEA {sh['TAN']} {sh['Va']}/{sh['Ve']}, "
                f"anni {dst['year']} e {src['year']}"
            )
            sn = dst.get("sourceName") or ""
            if note not in sn:
                sn = f"{sn}; {note}".strip("; ").strip()
            # Hygiene tests require a precise doc URL in sourceName for rows with range/battery.
            for k in copied:
                cite = (src.get("fieldSources") or {}).get(k) or ""
                m = re.search(r"https?://\S+", cite)
                if m and m.group(0) not in sn:
                    sn = f"{sn}; {m.group(0)}".strip("; ").strip()
                    break
            dst["sourceName"] = sn
            derived.append(
                {
                    "id": d["dst_id"],
                    "sourceId": d["src_id"],
                    "TAN": sh["TAN"],
                    "Va": sh["Va"],
                    "Ve": sh["Ve"],
                    "ep": sh.get("ep"),
                    "fields": copied,
                    "derivedFromYear": int(src["year"]),
                }
            )
        finalize(dst)

    # Finalize remaining touched
    for rid in TOUCH_IDS:
        finalize(by_id[rid])

    for r in seed:
        if r["id"] in m3_before and json.dumps(r, sort_keys=True) != m3_before[r["id"]]:
            raise SystemExit(f"M3 2026 altered: {r['id']}")

    after_c, after_kwh, after_multi = counts()
    regs = {}
    rank = json.loads(RANK.read_text(encoding="utf-8"))
    for e in (rank.get("all_incomplete") or []) + (rank.get("top") or []):
        regs[e["id"]] = e.get("regs") or e.get("n") or 0
    top30 = sorted(parents, key=lambda r: -float(regs.get(r["id"]) or 0))[:30]

    def top_bucket(rows):
        c = sum(1 for r in rows if not r.get("catalogDataIncomplete"))
        kwh = sum(
            1
            for r in rows
            if r.get("catalogDataIncomplete")
            and missing_calc_fields(r) == ["energyConsumptionKWhPerKm"]
        )
        multi = len(rows) - c - kwh
        return c, kwh, multi

    t30 = top_bucket(top30)

    cdn = json.loads(CDN.read_text(encoding="utf-8"))
    new_ver = int(cdn.get("seedVersion") or 69) + 1
    cdn["seedVersion"] = new_ver
    cdn["rows"] = len(seed)
    payload = json.dumps(
        [{k: v for k, v in r.items() if v is not None} for r in seed],
        separators=(",", ":"),
        ensure_ascii=False,
    )
    cdn["bytes"] = len(payload.encode())
    cdn["updatedAt"] = datetime.now(timezone.utc).isoformat()
    SEED.write_text(json.dumps(seed, ensure_ascii=False, separators=(",", ":")) + "\n")
    CDN.write_text(json.dumps(cdn, indent=2) + "\n")

    man = {
        "seedVersion": new_ver,
        "ids_before": ids_before,
        "phev_complete_before": before_c,
        "phev_complete_after": after_c,
        "phev_only_kwh_before": before_kwh,
        "phev_only_kwh_after": after_kwh,
        "phev_multi_missing_before": before_multi,
        "phev_multi_missing_after": after_multi,
        "top30_complete_after": t30[0],
        "top30_only_kwh_after": t30[1],
        "top30_multi_missing_after": t30[2],
        "fields_saved": fields_saved,
        "derived": derived,
        "removed": removed_log,
        "uitest_partial_kwh_id": "volvo-xc60-phev-recharge-2024",
    }
    MANIFEST.write_text(json.dumps(man, indent=2) + "\n")
    print(json.dumps({k: v for k, v in man.items() if k not in ("ids_before", "fields_saved", "removed")}, indent=2))
    print("fields_saved", len(fields_saved), "removed_entries", len(removed_log))


if __name__ == "__main__":
    main()
