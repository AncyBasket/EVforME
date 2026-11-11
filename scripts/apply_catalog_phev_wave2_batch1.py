#!/usr/bin/env python3
"""
PHEV wave2 batch1 (seed 77→78) — review-corrected.

Only official OEM fills with valid dating. Homolog reuse requires IDENTICAL
TAN/Va/Ve/ep AND identical power + weighted WLTP between seed rows; donor
source must itself be dated for the donor year (no continuous live PDFs).
No ±kW tolerance, no frequency ranking, no chain derivation.
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
from check_catalog_phev_wave2_batch1 import (  # noqa: E402
    PROVENANCE_REQUIRED_FIELDS,
    _looks_continuous_unversioned_oem_pdf,
    best_shared_exact,
    cite_dating_ok,
    exact_homolog_ok,
    extract_document_date,
    is_generic_url,
    source_year_ok,
    urls_in,
)
from lib.phev_manus_v76_validate import missing_calc_fields  # noqa: E402

SEED = REPO / "EVforME?" / "Data" / "vehicles.seed.quality.json"
CDN = REPO / "EVforME?" / "Data" / "catalog_cdn.json"
CACHE = REPO / "scripts" / "cache" / "eea"
INVENTORY = CACHE / "catalog_phev_wave2_batch1_inventory.json"
MANIFEST = CACHE / "catalog_phev_wave2_batch1_manifest.json"
BASE_MAIN = "0f0919245dbd68bb10da67ca1f21fe18192c38c5"
SOURCE_DAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")

BMW_330E_PRESS = "https://www.press.bmwgroup.com/global/article/attachment/T0442333EN/620071"


def finalize(row: dict) -> None:
    miss = missing_calc_fields(row)
    row["missingCalcFields"] = miss
    row["catalogDataIncomplete"] = bool(miss)
    score, ev = assess_confidence(row)
    row["confidenceScore"] = score
    row["confidenceEvidence"] = ev
    row["confidencePolicyVersion"] = POLICY_VERSION


def set_field_source(row: dict, field: str, cite: str, date: str) -> None:
    urls = urls_in(cite) or [cite]
    if any(is_generic_url(u) for u in urls):
        raise SystemExit(f"generic URL rejected: {cite}")
    year = int(row["year"])
    homolog = row.get("dataDerivedFromSameHomologationYear")
    hy = int(homolog) if homolog is not None else None
    if not cite_dating_ok(cite, date, year, homolog_year=hy):
        raise SystemExit(f"dating rejected {row['id']}.{field}: {date} {cite}")
    fs = dict(row.get("fieldSources") or {})
    fd = dict(row.get("fieldSourceDates") or {})
    fs[field] = cite
    fd[field] = date
    row["fieldSources"] = fs
    row["fieldSourceDates"] = fd


CLEARABLE_FIELDS = (
    "fuelConsumptionLPerKm",
    "energyConsumptionKWhPerKm",
    "batteryKWh",
    "wltpRangeKm",
)


def scrub_invalid_field_provenance(row: dict) -> list[str]:
    """Drop field values whose cites fail generic/dating on real PHEV rows."""
    cleared: list[str] = []
    fs = dict(row.get("fieldSources") or {})
    fd = dict(row.get("fieldSourceDates") or {})
    hy_raw = row.get("dataDerivedFromSameHomologationYear")
    hy = int(hy_raw) if hy_raw is not None else None
    year = int(row.get("year") or 0)
    for field in list(fs.keys()):
        cite = fs.get(field) or ""
        if not cite:
            continue
        date = fd.get(field) or ""
        urls = urls_in(cite)
        bad_generic = any(is_generic_url(u) for u in urls)
        bad_continuous = any(_looks_continuous_unversioned_oem_pdf(u) for u in urls)
        bad_dating = bool(urls) and not cite_dating_ok(cite, date, year, homolog_year=hy)
        if not (bad_generic or bad_continuous or bad_dating):
            continue
        cleared.append(field)
        fs.pop(field, None)
        fd.pop(field, None)
        if field in CLEARABLE_FIELDS:
            row[field] = None
            if field == "energyConsumptionKWhPerKm":
                row["energyIsWeighted"] = None
    row["fieldSources"] = fs or None
    row["fieldSourceDates"] = fd or None
    # If no field cites remain that mention homolog, drop derivation flag.
    remaining = " ".join((row.get("fieldSources") or {}).values())
    if hy is not None and "stessa omologazione" not in remaining.lower() and "homolog" not in remaining.lower():
        row.pop("dataDerivedFromSameHomologationYear", None)
    return cleared


def scrub_rejected_urls_from_source_name(row: dict) -> bool:
    """Remove generic landings / continuous typenblatt URLs from sourceName text."""
    sn = row.get("sourceName") or ""
    if not sn:
        return False
    changed = False
    for url in urls_in(sn):
        if is_generic_url(url) or _looks_continuous_unversioned_oem_pdf(url):
            sn2 = sn.replace(url, "").replace("—  ;", "—").replace("  ", " ")
            # Drop clauses that only pointed at the rejected URL.
            parts = [p.strip(" ;,—") for p in sn2.split(";") if p.strip(" ;,—")]
            kept = []
            for p in parts:
                low = p.lower()
                if "hybrid-suv" in low or "technische_daten_des_ford_kuga" in low:
                    changed = True
                    continue
                if "hybrid-elektrisch" in low and "http" not in low:
                    changed = True
                    continue
                kept.append(p)
            sn = "; ".join(kept)
            changed = True
    # Also strip leftover rejected path tokens even without a remaining URL match.
    low = sn.lower()
    if "hybrid-suv" in low or "technische_daten_des_ford_kuga" in low or "hybrid-elektrisch/energie" in low:
        parts = [p.strip(" ;,—") for p in sn.split(";") if p.strip(" ;,—")]
        kept = []
        for p in parts:
            pl = p.lower()
            if (
                "hybrid-suv" in pl
                or "technische_daten_des_ford_kuga" in pl
                or "hybrid-elektrisch" in pl
            ):
                changed = True
                continue
            kept.append(p)
        sn = "; ".join(kept)
        changed = True
    if changed:
        row["sourceName"] = sn.strip(" ;") or "EEA / OEM provenance scrubbed (wave2 review)"
    return changed


def clear_kuga_continuous_oem_orphans(row: dict) -> list[str]:
    """Nil CS/CD/range/battery/weighted that were justified only by live Ford typenblatt."""
    cleared: list[str] = []
    for field in (
        "fuelConsumptionLPerKm",
        "energyConsumptionKWhPerKm",
        "batteryKWh",
        "wltpRangeKm",
        "weightedFuelConsumptionLPerKm",
        "weightedEnergyConsumptionKWhPerKm",
    ):
        if row.get(field) is not None:
            row[field] = None
            cleared.append(field)
    row["energyIsWeighted"] = None
    row["fieldSources"] = None
    row["fieldSourceDates"] = None
    row.pop("dataDerivedFromSameHomologationYear", None)
    year = int(row.get("year") or 0)
    n = {2023: 6176, 2024: 2577}.get(year)
    n_bit = f" n={n}" if n else ""
    row["sourceName"] = (
        f"EEA co2cars IT {year} KUGA PETROL/ELECTRIC{n_bit}; "
        "OEM same-MY CS/CD/range/battery not attached — continuous live Ford typenblatt "
        "and hybrid-electric landing page rejected → catalogDataIncomplete"
    )
    return cleared


def ensure_calc_field_provenance(row: dict) -> list[str]:
    """Attach fieldSources only with a real document date; else nil the value.

    Never invents YYYY-01-01 placeholders. EPA shells may keep a non-URL cite
    without fieldSourceDates.
    """
    changed: list[str] = []
    fs = dict(row.get("fieldSources") or {})
    fd = dict(row.get("fieldSourceDates") or {})
    year = int(row.get("year") or 0)
    hy_raw = row.get("dataDerivedFromSameHomologationYear")
    hy = int(hy_raw) if hy_raw is not None else None
    sn = row.get("sourceName") or ""
    sn_urls = [
        u for u in urls_in(sn) if not is_generic_url(u) and not _looks_continuous_unversioned_oem_pdf(u)
    ]
    for field in PROVENANCE_REQUIRED_FIELDS:
        if row.get(field) is None:
            continue
        # Drop previously invented New-Year placeholders and re-evaluate.
        existing_date = fd.get(field) or ""
        if existing_date.endswith("-01-01") and existing_date[:4].isdigit():
            # Keep only if the cite itself encodes that month (e.g. "June 2025" → 2025-06-01).
            cite_now = fs.get(field) or sn
            real = extract_document_date(cite_now)
            if real != existing_date:
                fs.pop(field, None)
                fd.pop(field, None)
                changed.append(f"{field}:drop_invented_date")

        if fs.get(field):
            # Re-validate dating; nil value if cite cannot be dated honestly.
            cite = fs[field]
            date = fd.get(field) or ""
            urls = urls_in(cite)
            if urls:
                if not date:
                    date = extract_document_date(cite) or ""
                    if date:
                        fd[field] = date
                        changed.append(f"{field}:date_from_cite")
                if not date or not cite_dating_ok(cite, date, year, homolog_year=hy):
                    fs.pop(field, None)
                    fd.pop(field, None)
                    row[field] = None
                    if field == "energyConsumptionKWhPerKm":
                        row["energyIsWeighted"] = None
                    changed.append(f"{field}:nil_bad_cite")
            continue

        attached = False
        if sn_urls:
            for url in sn_urls:
                blob = f"{sn} {url}"
                date = extract_document_date(blob)
                if not date:
                    continue
                cite = f"{sn.split('—')[0].strip()} {url}" if "—" in sn else f"{sn} {url}"
                if cite_dating_ok(cite, date, year, homolog_year=hy):
                    fs[field] = cite[:500]
                    fd[field] = date
                    attached = True
                    changed.append(f"{field}:attached:{date}")
                    break
        if not attached and (
            sn.strip() == "EPA-FuelEconomy" or sn.strip().startswith("EPA-FuelEconomy")
        ):
            fs[field] = "EPA-FuelEconomy"
            fd.pop(field, None)  # no invented calendar date
            attached = True
            changed.append(f"{field}:epa")
        if not attached:
            row[field] = None
            if field == "energyConsumptionKWhPerKm":
                row["energyIsWeighted"] = None
            changed.append(f"{field}:nil")
    row["fieldSources"] = fs or None
    row["fieldSourceDates"] = fd or None
    return changed


def tech_blob(rows: list[dict]) -> str:
    conf = {
        "confidenceScore",
        "confidenceScoreLegacy",
        "confidencePolicyVersion",
        "confidenceEvidence",
    }
    cleaned = [{k: v for k, v in r.items() if k not in conf} for r in rows]
    return json.dumps(cleaned, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def load_main_seed() -> dict[str, dict]:
    import subprocess

    raw = subprocess.check_output(["git", "show", f"{BASE_MAIN}:EVforME?/Data/vehicles.seed.quality.json"])
    return {r["id"]: r for r in json.loads(raw)}


def main() -> None:
    seed = json.loads(SEED.read_text(encoding="utf-8"))
    by_id = {r["id"]: r for r in seed}
    ids_before = [r["id"] for r in seed]
    assert len(seed) == 6977

    main_by = load_main_seed()
    m3_before = {
        r["id"]: json.dumps(r, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        for r in seed
        if r["id"].startswith("tesla-model-3") and r.get("year") == 2026
    }
    assert len(m3_before) == 4
    non_phev_before = tech_blob([r for r in seed if r.get("powertrain") != "phev"])
    non_phev_sha_before = hashlib.sha256(non_phev_before.encode()).hexdigest()

    inv = json.loads(INVENTORY.read_text(encoding="utf-8"))
    batch1_ids = [x["id"] for x in inv["batch1_candidates"]]
    assert len(batch1_ids) == 40

    completed: list[dict] = []
    partial: list[dict] = []
    homolog_reuse: list[dict] = []
    left_nil: list[dict] = []
    extras: list[dict] = []

    # --- Restore previously invalid fills from main (Kuga 2022, Jeep CS) ---
    for rid in (
        "ford-kuga-phev-2022",
        "jeep-compass-phev-4xe-2022",
        "jeep-renegade-phev-4xe-2022",
    ):
        by_id[rid].clear()
        by_id[rid].update(json.loads(json.dumps(main_by[rid])))  # deep copy via JSON
        finalize(by_id[rid])

    # Sanity: kuga weighted fuel restored
    kuga = by_id["ford-kuga-phev-2022"]
    if abs(float(kuga.get("weightedFuelConsumptionLPerKm") or 0) - 0.01007) > 1e-9:
        raise SystemExit("kuga weightedFuel restore failed")
    if kuga.get("catalogDataIncomplete") is not True:
        raise SystemExit("kuga must be incomplete after restore")
    if kuga.get("dataDerivedFromSameHomologationYear") is not None:
        raise SystemExit("kuga homolog flag must be cleared")

    # Scrub invalid generic/dating cites on EVERY real PHEV row (honesty under
    # strengthened checker). Prefer nil over hybrid-suv / continuous undated PDFs.
    scrubbed_rows: list[dict] = []
    for r in seed:
        if r.get("powertrain") != "phev":
            continue
        cleared = scrub_invalid_field_provenance(r)
        sn_changed = scrub_rejected_urls_from_source_name(r)
        if cleared or sn_changed:
            finalize(r)
            scrubbed_rows.append({"id": r["id"], "cleared": cleared, "sourceNameScrubbed": sn_changed})

    # Kuga 2023/2024: orphan CS/battery/range/weighted left after CD wipe — nil all
    # continuous-typenblatt-justified fields and rewrite sourceName to EEA shell.
    for kid in ("ford-kuga-phev-2023", "ford-kuga-phev-2024"):
        cleared = clear_kuga_continuous_oem_orphans(by_id[kid])
        finalize(by_id[kid])
        scrubbed_rows.append({"id": kid, "cleared": cleared, "kugaContinuousOemCleared": True})

    # Ensure every filled CS/kWh/range/battery has fieldSources (attach or nil).
    provenance_fixes: list[dict] = []
    for r in seed:
        if r.get("powertrain") != "phev":
            continue
        # Skip kuga 23/24 — already EEA shells with nils.
        if r["id"] in ("ford-kuga-phev-2023", "ford-kuga-phev-2024"):
            continue
        fixes = ensure_calc_field_provenance(r)
        if fixes:
            finalize(r)
            provenance_fixes.append({"id": r["id"], "fixes": fixes})

    # --- Extra (outside strict lotto completion): BMW 330e 2024 battery ONLY ---
    # Review: keep usable battery 19.5 from May 2024 press; do NOT claim EAER/range
    # from that attachment without an explicit verified figure. Pure CD stays nil.
    b330 = by_id["bmw-330e-phev-2024"]
    b330["batteryKWh"] = 19.5
    b330["wltpRangeKm"] = None  # autonomia not verified on the battery press cite
    fs330 = dict(b330.get("fieldSources") or {})
    fd330 = dict(b330.get("fieldSourceDates") or {})
    fs330.pop("wltpRangeKm", None)
    fd330.pop("wltpRangeKm", None)
    # CS may remain if already present with a dated press cite; otherwise leave/nil via provenance.
    b330["fieldSources"] = fs330 or None
    b330["fieldSourceDates"] = fd330 or None
    cite = (
        "press.bmwgroup.com new BMW 330e: high-voltage battery with 19.5 kWh of usable energy "
        f"(datePublished 2024-05-29) {BMW_330E_PRESS}"
    )
    b330.pop("dataDerivedFromSameHomologationYear", None)
    set_field_source(b330, "batteryKWh", cite, "2024-05-29")
    if b330.get("fuelConsumptionLPerKm") is not None:
        set_field_source(
            b330,
            "fuelConsumptionLPerKm",
            f"press.bmwgroup.com 330e Kraftstoff bei entladener Batterie 7.9-7.1 L/100 {BMW_330E_PRESS}",
            "2024-05-29",
        )
    b330["sourceUpdatedAt"] = SOURCE_DAY
    prev = b330.get("sourceName") or ""
    # Strip any prior claim that the press filled EAER/range.
    parts = [p.strip(" ;") for p in prev.split(";") if p.strip(" ;")]
    kept = []
    for p in parts:
        pl = p.lower()
        if "electric range" in pl or "wltprange" in pl or "autonomia" in pl:
            continue
        kept.append(p)
    prev = "; ".join(kept)
    if "wave2-batch1 extra: batteryKWh=19.5" not in prev:
        prev = f"{prev}; wave2-batch1 extra: batteryKWh=19.5 usable — {BMW_330E_PRESS}".strip("; ")
    b330["sourceName"] = prev
    scrub_rejected_urls_from_source_name(b330)
    finalize(b330)
    extras.append(
        {
            "id": b330["id"],
            "note": "extra vs lotto — BMW press May 2024 usable battery only; EAER/range not claimed; pure CD nil",
            "filled": {"batteryKWh": 19.5},
            "stillMissing": b330["missingCalcFields"],
            "sources": {"batteryKWh": cite},
            "sourceDates": {"batteryKWh": "2024-05-29"},
        }
    )
    partial.append(extras[-1])

    # --- Batch1: restore/controls only — no new OEM research claimed ---
    inv_by = {x["id"]: x for x in inv.get("batch1_candidates") or []}
    # Specific per-row reasons (not one repeated boilerplate).
    nil_reasons = {
        "ford-kuga-phev-2022": (
            "no MY2022-dated OEM typenblatt / 2022 archive; continuous Technische_Daten PDF "
            "(archive only 2026) invalid for MY22; weightedFuel 0.01007 kept from EEA IT n=1923"
        ),
        "jeep-compass-phev-4xe-2022": (
            "CS still nil: jeep.de/hybrid-suv archive rejected as generic range page; "
            "2022↔2024 homolog reuse blocked (weighted WLTP/power not identical)"
        ),
        "jeep-renegade-phev-4xe-2022": (
            "CS still nil: jeep.de/hybrid-suv generic landing rejected; "
            "2022↔2024 donor weighted WLTP not identical"
        ),
        "cupra-formentor-phev-e-hybrid-2024": (
            "missing CS+CD+EAER combined; no dated CUPRA OEM sheet verified in this restore PR"
        ),
        "jeep-renegade-phev-4xe-2023": (
            "CD puro nil; CS was hybrid-suv-only and scrubbed; no dated MY23 pure-electric OEM cite"
        ),
        "mini-countryman-cooper-se-all4-2023": (
            "CS/CD/range/battery all nil; no dated MINI OEM PHEV sheet attached in this PR"
        ),
        "volvo-xc40-phev-recharge-2022": (
            "CS/CD/range/battery nil; no MY2022-dated Volvo OEM PHEV document in this restore pass"
        ),
        "cupra-formentor-phev-e-hybrid-2023": (
            "CS/CD/range/battery nil; no dated CUPRA Formentor MY23 OEM sheet in this PR"
        ),
        "volvo-xc40-phev-recharge-2023": (
            "CS/CD/range/battery nil; no MY2023-dated Volvo XC40 PHEV OEM document verified here"
        ),
        "volvo-xc60-phev-recharge-2024": (
            "CD puro nil (CS present from prior wave); no dated pure-electric kWh label for MY24"
        ),
        "bmw-x1-phev-xdrive25e-2024": (
            "CD puro nil; weighted-only Strom on EnVKV; no charge-depleting label for MY24"
        ),
        "bmw-x1-phev-xdrive25e-2022": (
            "CS+CD nil; no MY2022-dated BMW X1 PHEV OEM sheet verified in this restore PR"
        ),
        "jeep-renegade-phev-4xe-2024": (
            "CD puro nil; CS from hybrid-suv scrubbed; no dated MY24 pure-electric OEM cite"
        ),
        "alfa-romeo-tonale-phev-2023": (
            "CS/CD/range/battery nil; no dated Stellantis Tonale MY23 PHEV sheet in this PR"
        ),
        "mercedes-benz-glc-phev-300-de-2024": (
            "CS/CD/range/battery nil; no dated Mercedes GLC 300 de MY24 OEM sheet here"
        ),
        "volvo-xc60-phev-recharge-2023": (
            "CD puro nil after provenance scrub of undated live press reuse; no MY23 pure-CD cite"
        ),
        "toyota-c-hr-phev-2024": (
            "CD puro nil; no dated Toyota C-HR PHEV charge-depleting label verified in this PR"
        ),
        "peugeot-3008-phev-2022": (
            "CS/CD/range/battery nil; no MY2022-dated Peugeot 3008 PHEV OEM document here"
        ),
        "renault-captur-phev-e-tech-phev-2022": (
            "CS/CD/range/battery nil; no MY2022-dated Renault Captur E-Tech OEM sheet here"
        ),
        "bmw-x1-phev-xdrive25e-2023": (
            "CD puro nil; no dated pure-electric kWh label for X1 MY23 in this restore PR"
        ),
        "mercedes-benz-gle-phev-350-de-2022": (
            "CS/CD/range/battery nil; no MY2022-dated Mercedes GLE 350 de OEM sheet here"
        ),
        "peugeot-3008-phev-2023": (
            "CS+CD nil; no dated Peugeot 3008 MY23 PHEV OEM sheet verified in this PR"
        ),
        "mini-countryman-cooper-se-all4-2022": (
            "CS/CD/range/battery nil; no MY2022-dated MINI Countryman SE ALL4 OEM sheet here"
        ),
        "audi-q3-sportback-phev-45-tfsi-e-2024": (
            "CS/CD/range/battery nil; no dated Audi Q3 Sportback TFSI e MY24 sheet in this PR"
        ),
        "audi-q3-sportback-phev-45-tfsi-e-2023": (
            "CS/CD/range/battery nil; no dated Audi Q3 Sportback TFSI e MY23 sheet in this PR"
        ),
        "mercedes-benz-gla-phev-250-e-2023": (
            "CS/CD/range/battery nil; no MY2023-dated Mercedes GLA 250 e OEM sheet here"
        ),
        "mercedes-benz-gle-coupe-phev-350-de-2022": (
            "CS/CD/range/battery nil; no MY2022-dated Mercedes GLE Coupé 350 de OEM sheet here"
        ),
        "mercedes-benz-gla-phev-250-e-2022": (
            "CS/CD/range/battery nil; no MY2022-dated Mercedes GLA 250 e OEM sheet here"
        ),
        "alfa-romeo-tonale-phev-2024": (
            "CS/CD/range/battery nil; no dated Tonale MY24 PHEV OEM sheet in this restore PR"
        ),
        "audi-a3-phev-40-tfsi-e-2024": (
            "CS/CD/range/battery nil; no dated Audi A3 40 TFSI e MY24 OEM sheet here"
        ),
        "audi-a3-phev-45-tfsi-e-2024": (
            "CS/CD/range/battery nil; no dated Audi A3 45 TFSI e MY24 OEM sheet here"
        ),
        "audi-a3-phev-40-tfsi-e-2023": (
            "CS/CD/range/battery nil; no dated Audi A3 40 TFSI e MY23 OEM sheet here"
        ),
        "audi-a3-phev-40-tfsi-e-2022": (
            "CS/CD/range/battery nil; no dated Audi A3 40 TFSI e MY22 OEM sheet here"
        ),
        "audi-a3-e-tron-ultra-phev-2016": (
            "US/EPA shell; battery nil; no EU WLTP pure-CD package — not researched in this PR"
        ),
        "audi-q3-phev-45-tfsi-e-2024": (
            "CS/CD/range/battery nil; no dated Audi Q3 TFSI e MY24 OEM sheet here"
        ),
        "audi-q3-phev-45-tfsi-e-2023": (
            "CS/CD/range/battery nil; no dated Audi Q3 TFSI e MY23 OEM sheet here"
        ),
        "audi-q3-phev-45-tfsi-e-2022": (
            "CS/CD/range/battery nil; no dated Audi Q3 TFSI e MY22 OEM sheet here"
        ),
        "audi-q3-sportback-phev-45-tfsi-e-2022": (
            "CS/CD/range/battery nil; no dated Audi Q3 Sportback TFSI e MY22 OEM sheet here"
        ),
        "audi-q5-phev-50-tfsi-e-2024": (
            "CS/CD/range/battery nil; no dated Audi Q5 50 TFSI e MY24 OEM sheet here"
        ),
        "audi-q5-phev-50-tfsi-e-2023": (
            "CS/CD/range/battery nil; no dated Audi Q5 50 TFSI e MY23 OEM sheet here"
        ),
    }

    touched = {p["id"] for p in partial}
    for rid in batch1_ids:
        row = by_id[rid]
        miss = missing_calc_fields(row)
        if rid in touched:
            # BMW extra already recorded as partial (may still be incomplete on CD)
            continue
        inv_row = inv_by.get(rid) or {}
        left_nil.append(
            {
                "id": rid,
                "brand": row.get("brand"),
                "model": row.get("model"),
                "year": row.get("year"),
                "market": row.get("market"),
                "n": inv_row.get("n"),
                "missing": miss,
                "reason": nil_reasons.get(
                    rid,
                    f"restore/controls PR — no new dated OEM research for {rid}; fields remain nil",
                ),
            }
        )

    # Export helpers used by unit tests / checkers
    _ = best_shared_exact
    _ = exact_homolog_ok

    if [r["id"] for r in seed] != ids_before:
        raise SystemExit("id list changed")
    for mid, blob in m3_before.items():
        now = json.dumps(by_id[mid], sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        if now != blob:
            raise SystemExit(f"M3 altered {mid}")
    non_phev_after = tech_blob([r for r in seed if r.get("powertrain") != "phev"])
    non_phev_sha_after = hashlib.sha256(non_phev_after.encode()).hexdigest()
    if non_phev_sha_after != non_phev_sha_before:
        raise SystemExit("non-PHEV tech blob changed")

    cdn = json.loads(CDN.read_text(encoding="utf-8"))
    # Allow re-run on already-bumped seed 78
    if int(cdn.get("seedVersion") or 0) not in (77, 78):
        raise SystemExit(f"unexpected seedVersion {cdn.get('seedVersion')}")
    new_ver = 78
    cdn["seedVersion"] = new_ver
    cdn["rows"] = len(seed)
    payload = json.dumps(seed, separators=(",", ":"), ensure_ascii=False)
    cdn["bytes"] = len(payload.encode())
    cdn["updatedAt"] = datetime.now(timezone.utc).isoformat()
    cdn["note"] = (
        "seedVersion 78: PHEV wave2 batch1 restore/controls — BMW 330e battery extra; "
        "invalid Kuga/Jeep fills reverted; continuous Ford typenblatt orphans cleared; "
        "confidence policy v2 unchanged; api/static sync deferred at seed 77"
    )

    SEED.write_text(payload)
    CDN.write_text(json.dumps(cdn, indent=2) + "\n")

    man = {
        "seedVersion": new_ver,
        "prevSeedVersion": 77,
        "ids_before": ids_before,
        "batch1_ids": batch1_ids,
        "completed": completed,
        "partial": partial,
        "extras": extras,
        "homolog_reuse": homolog_reuse,
        "left_nil": left_nil,
        "non_phev_tech_sha": non_phev_sha_after,
        "m3_ids": sorted(m3_before),
        "sourceDay": SOURCE_DAY,
        "reviewNotes": [
            "RESTORE/CONTROLS PR — not a researched fill of the 37 remaining lotto rows.",
            "Reverted ford-kuga-2022 completion (continuous undated Ford PDF / no 2022 archive).",
            "Reverted Jeep Compass/Renegade 2022 CS from generic /hybrid-suv archive.",
            "Cleared ford-kuga-2023/2024 CS/battery/range/weighted orphans from continuous typenblatt.",
            "Restored homolog shared map to main (no unverified 2022 year injection).",
            "BMW 330e 2024 battery 19.5 kept as extra vs lotto; pure CD nil.",
            "Scrubbed generic/dating-invalid fieldSources + rejected URLs from sourceName.",
        ],
        "scrubbed_invalid_provenance": scrubbed_rows,
        "provenance_fixes": provenance_fixes,
        "prKind": "restore_controls",
    }
    MANIFEST.write_text(json.dumps(man, indent=2, ensure_ascii=False) + "\n")
    print(
        json.dumps(
            {
                "seedVersion": new_ver,
                "completed": len(completed),
                "partial": len(partial),
                "extras": len(extras),
                "left_nil": len(left_nil),
                "homolog_reuse": len(homolog_reuse),
                "scrubbed": len(scrubbed_rows),
                "provenance_fixes": len(provenance_fixes),
                "non_phev_tech_sha": non_phev_sha_after,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
