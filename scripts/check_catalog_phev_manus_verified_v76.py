#!/usr/bin/env python3
"""Verify selective Manus PHEV recovery (seed v76) with real negative + determinism tests."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
from lib.phev_manus_v76_validate import (  # noqa: E402
    inspect_download,
    missing_calc_fields,
    validate_completeness_flag,
    validate_energy_cite,
    validate_field_import,
    validate_inherited_date,
    validate_range_label,
    validate_source_dating,
)

SEED = REPO / "EVforME?" / "Data" / "vehicles.seed.quality.json"
CDN = REPO / "EVforME?" / "Data" / "catalog_cdn.json"
MANIFEST = REPO / "scripts" / "cache" / "eea" / "catalog_phev_manus_verified_v76_manifest.json"
OEM = REPO / "scripts" / "cache" / "oem" / "manus_verify"
APPLY = REPO / "scripts" / "apply_catalog_phev_manus_verified_v76.py"
PREV = 75


def seed_fp(path: Path = SEED) -> str:
    rows = json.loads(path.read_text(encoding="utf-8"))
    blob = json.dumps(rows, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(blob.encode()).hexdigest()


def must_fail_fixtures() -> None:
    """Fixtures go through the same validators used on real imports/downloads."""
    cases: list[tuple[str, bool, str, object]] = []

    # 1) pure kWh without explicit CD/pure label
    v = validate_energy_cite("Consommations d'énergie électrique 16,8 (no CD label)", 0.168)
    cases.append(("energy_without_pure_label", False, "energy_without_pure_label", v))

    # valid pure label
    v_ok = validate_energy_cite("consumo elettrico puro (CD) 16,8 kWh/100 km", 0.168)
    cases.append(("energy_with_pure_label", True, "ok_energy", v_ok))

    # 2) complete with nil calc
    bad_row = {
        "catalogDataIncomplete": False,
        "fuelConsumptionLPerKm": 0.06,
        "energyConsumptionKWhPerKm": 0.2,
        "energyIsWeighted": False,
        "wltpRangeKm": 40,
        "batteryKWh": None,
    }
    v = validate_completeness_flag(bad_row)
    cases.append(("complete_with_nil_calc", False, "complete_with_nil_calc", v))

    good_row = {
        "catalogDataIncomplete": True,
        "fuelConsumptionLPerKm": None,
        "energyConsumptionKWhPerKm": None,
        "wltpRangeKm": None,
        "batteryKWh": None,
    }
    v = validate_completeness_flag(good_row)
    cases.append(("incomplete_nil_ok", True, "ok_completeness", v))

    # 3) live URL for past year / incompatible date
    v = validate_source_dating(
        row_year=2024,
        source_date="2023-06-26",
        url="https://www.toyota.it/content/dam/toyota/nmsc/italy/gamma/pdf/scheda-tecnica/RAV4_Plug-in_Hybrid_Scheda_tecnica.pdf",
    )
    cases.append(("source_date_incompatible", False, "source_date_incompatible", v))

    v = validate_inherited_date(
        field_source_date="2023-06-26",
        document_date="2024-01-01",
        row_year=2024,
    )
    cases.append(("inherited_incompatible_date", False, "inherited_incompatible_date", v))

    # 4) fake PDF (HTML bytes with .pdf claim) — use real cache artifact if present
    fake = OEM / "bmw_2at_press_652064.html"
    if not fake.exists():
        # fallback: create temp html claimed as pdf
        fake = Path(tempfile.mkstemp(suffix=".pdf")[1])
        fake.write_text("<!DOCTYPE html><html><title>Listino 2026</title></html>", encoding="utf-8")
    v = inspect_download(fake, claimed_ext=".pdf")
    cases.append(("fake_pdf_html", False, "fake_pdf_html", v))

    # real PDFs must pass
    for name in ("toyota_rav4_my23.pdf", "cupra_ie_jan2024.pdf"):
        p = OEM / name
        if p.exists():
            v = inspect_download(p)
            cases.append((f"ok_pdf_{name}", True, "ok_format", v))

    # 5) EAER City only
    v = validate_range_label("EAER City 55 km", 55)
    cases.append(("eaer_city_only", False, "eaer_city_only", v))

    # 6) non-prudent extremes
    v = validate_range_label("autonomia elettrica 83–92 km secondo WLTP combinato", 92)
    cases.append(("non_prudent_range_max", False, "non_prudent_range_extremum", v))
    v = validate_range_label("autonomia elettrica 83–92 km secondo WLTP combinato", 83)
    cases.append(("prudent_range_min", True, "ok_range", v))

    from lib.phev_manus_v76_validate import validate_cs_interval_pick

    v = validate_cs_interval_pick(5.2, 6.1, 5.2)
    cases.append(("non_prudent_cs_min", False, "non_prudent_cs_extremum", v))
    v = validate_cs_interval_pick(5.2, 6.1, 6.1)
    cases.append(("prudent_cs_max", True, "ok_cs_max", v))

    # 7) live press page past year rejected by import validator
    v = validate_field_import(
        row_year=2022,
        field="wltpRangeKm",
        value=83,
        url="https://www.press.bmwgroup.com/deutschland/article/detail/T0390613DE/bmw-modellpflege-massnahmen-zum-sommer-2022?language=de",
        source_date="2022-05-18",
        label="83–92 km WLTP",
        download_path=OEM / "bmw_225e_press_T0390613DE.html" if (OEM / "bmw_225e_press_T0390613DE.html").exists() else None,
    )
    cases.append(("live_page_past_year", False, "live_page_past_year", v))

    # accepted-style Toyota import must pass when PDF present
    toy_pdf = OEM / "toyota_rav4_my23.pdf"
    if toy_pdf.exists():
        v = validate_field_import(
            row_year=2023,
            field="batteryKWh",
            value=18.1,
            url="https://newsroom.toyota.it/download/1316286/20230101rav4plug-inhybridmy23schedatecnica.pdf",
            source_date="2023-01-03",
            label="BATTERIE HV / Litio - Capacità (kWh) = 18.1; scheda p.1",
            download_path=toy_pdf,
        )
        cases.append(("toyota_import_ok", True, "ok_", v))

    failed = []
    for label, expect_ok, expect_reason, verdict in cases:
        ok = verdict.ok == expect_ok and (
            expect_reason in verdict.reason if expect_reason else True
        )
        status = "OK" if ok else "FAIL"
        print(f"must-fail {status}: {label} → {verdict.reason}")
        if not ok:
            failed.append(f"{label}: expect ok={expect_ok}/{expect_reason} got {verdict.ok}/{verdict.reason}")
    if failed:
        raise SystemExit("must-fail failures:\n" + "\n".join(failed))
    print(f"must-fail fixtures: {len(cases)}/{len(cases)} via shared validators")


def determinism_pipeline() -> None:
    """PYTHONHASHSEED 0..5: run deterministic check/report on temp copies (no seed writes)."""
    reports: list[str] = []
    for seed_val in range(6):
        with tempfile.TemporaryDirectory(prefix=f"phev_v76_hs{seed_val}_") as tmp:
            tdir = Path(tmp)
            # copy seed+cdn+oem artifacts needed for validation paths
            data = tdir / "EVforME?" / "Data"
            data.mkdir(parents=True)
            shutil.copy2(SEED, data / "vehicles.seed.quality.json")
            shutil.copy2(CDN, data / "catalog_cdn.json")
            scripts = tdir / "scripts"
            (scripts / "cache" / "eea").mkdir(parents=True)
            (scripts / "lib").mkdir(parents=True)
            shutil.copy2(MANIFEST, scripts / "cache" / "eea" / MANIFEST.name)
            for name in ("phev_manus_v76_validate.py", "__init__.py"):
                shutil.copy2(REPO / "scripts" / "lib" / name, scripts / "lib" / name)
            # lightweight deterministic reporter (does not mutate)
            reporter = r'''
import hashlib, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[0]))
from lib.phev_manus_v76_validate import missing_calc_fields, inspect_download, validate_field_import

repo = Path(__file__).resolve().parents[1]
seed = json.loads((repo/"EVforME?"/"Data"/"vehicles.seed.quality.json").read_text())
cdn = json.loads((repo/"EVforME?"/"Data"/"catalog_cdn.json").read_text())
man = json.loads((repo/"scripts"/"cache"/"eea"/"catalog_phev_manus_verified_v76_manifest.json").read_text())
by = {r["id"]: r for r in seed}
parents = [r for r in seed if r.get("powertrain")=="phev" and not r.get("parentId")]
c=k=m=0
for r in parents:
    miss=missing_calc_fields(r)
    if not miss: c+=1
    elif miss==["energyConsumptionKWhPerKm"]: k+=1
    else: m+=1
m3=sorted(r["id"] for r in seed if r["id"].startswith("tesla-model-3") and r.get("year")==2026)
accepted=sorted((x["id"], x["field"], x["after"]) for x in man.get("fields_changed") or [])
rejected=sorted((x["id"], x["field"]) for x in man.get("rejected") or [])
toy=by["toyota-rav4-phev-2023"]
cup=by["cupra-formentor-phev-e-hybrid-2024"]
bmw=by["bmw-serie-2-active-tourer-225e-xdrive-2022"]
blob={
  "seedVersion": cdn.get("seedVersion"),
  "rows": len(seed),
  "phev":[c,k,m],
  "m3": m3,
  "accepted": accepted,
  "rejected": rejected,
  "toyota_battery": toy.get("batteryKWh"),
  "cupra_battery": cup.get("batteryKWh"),
  "bmw_range": bmw.get("wltpRangeKm"),
  "bmw_missing": missing_calc_fields(bmw),
}
print(json.dumps(blob, sort_keys=True, separators=(",",":"), ensure_ascii=False))
print("SHA", hashlib.sha256(json.dumps(blob, sort_keys=True, separators=(",",":"), ensure_ascii=False).encode()).hexdigest())
'''
            rep_path = scripts / "_determinism_report.py"
            rep_path.write_text(reporter, encoding="utf-8")
            env = os.environ.copy()
            env["PYTHONHASHSEED"] = str(seed_val)
            # also import-check validators under that hash seed
            r = subprocess.run(
                [sys.executable, str(rep_path)],
                capture_output=True,
                text=True,
                env=env,
                cwd=str(tdir),
                check=False,
            )
            if r.returncode != 0:
                raise SystemExit(f"determinism seed={seed_val} failed: {r.stderr}")
            reports.append(r.stdout.strip())
    if len(set(reports)) != 1:
        raise SystemExit(f"PYTHONHASHSEED drift across pipeline reports:\n{reports}")
    print(f"PYTHONHASHSEED 0..5 pipeline identical ({len(reports)} runs)")
    print(reports[0].splitlines()[-1])


def main() -> None:
    must_fail_fixtures()
    determinism_pipeline()

    seed = json.loads(SEED.read_text(encoding="utf-8"))
    cdn = json.loads(CDN.read_text(encoding="utf-8"))
    man = json.loads(MANIFEST.read_text(encoding="utf-8"))
    by_id = {r["id"]: r for r in seed}
    ver = int(cdn.get("seedVersion") or 0)
    if ver != PREV + 1:
        raise SystemExit(f"seedVersion expected {PREV+1}, got {ver}")
    removed = set(man.get("ids_before") or []) - set(by_id)
    if removed:
        raise SystemExit(f"removals: {removed}")

    toy = by_id["toyota-rav4-phev-2023"]
    if abs(float(toy.get("batteryKWh")) - 18.1) > 1e-9:
        raise SystemExit("rav4 2023 battery")
    if abs(float(toy.get("weightedFuelConsumptionLPerKm")) - 0.00948) > 1e-9:
        raise SystemExit("rav4 2023 weighted fuel must stay main 0.00948")
    if (toy.get("fieldSourceDates") or {}).get("batteryKWh") != "2023-01-03":
        raise SystemExit("rav4 2023 battery date")
    v = validate_field_import(
        row_year=2023,
        field="batteryKWh",
        value=toy.get("batteryKWh"),
        url="https://newsroom.toyota.it/download/1316286/20230101rav4plug-inhybridmy23schedatecnica.pdf",
        source_date=(toy.get("fieldSourceDates") or {}).get("batteryKWh"),
        label=(toy.get("fieldSources") or {}).get("batteryKWh") or "",
        download_path=OEM / "toyota_rav4_my23.pdf",
    )
    if not v.ok:
        raise SystemExit(f"toyota real-row validation failed: {v.reason}")

    cup = by_id["cupra-formentor-phev-e-hybrid-2024"]
    if abs(float(cup.get("batteryKWh")) - 12.8) > 1e-9:
        raise SystemExit("formentor battery")
    if (cup.get("fieldSourceDates") or {}).get("batteryKWh") != "2024-01-01":
        raise SystemExit("formentor date")
    if abs(float(cup.get("powerKw") or 0) - 110.6) > 0.05:
        raise SystemExit("formentor powerKw must stay 110.6")

    b22 = by_id["bmw-serie-2-active-tourer-225e-xdrive-2022"]
    if b22.get("wltpRangeKm") is not None:
        raise SystemExit("225e 2022 range must be nil (no admissible 2022 proof)")
    if b22.get("batteryKWh") is not None:
        raise SystemExit("225e 2022 battery must stay nil")
    if (b22.get("fieldSourceDates") or {}).get("wltpRangeKm"):
        raise SystemExit("225e 2022 range provenance must be removed")
    if "manus-verified v76: wltpRangeKm" in (b22.get("sourceName") or ""):
        raise SystemExit("225e 2022 range sourceName note must be removed")
    miss = missing_calc_fields(b22)
    if "wltpRangeKm" not in miss or "batteryKWh" not in miss:
        raise SystemExit(f"225e 2022 missingCalcFields incomplete: {miss}")

    # fake artifact must still fail format check
    fake_html = OEM / "bmw_2at_press_652064.html"
    if fake_html.exists():
        v = inspect_download(fake_html, claimed_ext=".pdf")
        if v.ok or v.reason != "fake_pdf_html":
            raise SystemExit(f"expected fake_pdf_html for renamed HTML, got {v}")

    for rid in (
        "bmw-serie-2-active-tourer-225e-xdrive-2023",
        "bmw-serie-2-active-tourer-225e-xdrive-2024",
        "bmw-x3-phev-xdrive30e-2022",
        "bmw-x3-phev-xdrive30e-2023",
        "bmw-x3-phev-xdrive30e-2024",
        "hyundai-tucson-phev-2023",
        "toyota-rav4-phev-2024",
        "volkswagen-tiguan-phev-ehybrid-2024",
    ):
        r = by_id[rid]
        if r.get("batteryKWh") is not None:
            raise SystemExit(f"rejected battery leaked: {rid}")
        if rid != "toyota-rav4-phev-2024" and r.get("wltpRangeKm") is not None and rid.startswith("bmw"):
            raise SystemExit(f"rejected range leaked: {rid}")
        if rid == "hyundai-tucson-phev-2023" and r.get("wltpRangeKm") is not None:
            raise SystemExit("tucson range leaked")
        if rid == "volkswagen-tiguan-phev-ehybrid-2024" and r.get("batteryKWh") is not None:
            raise SystemExit("tiguan battery leaked")

    for r in seed:
        if r.get("powertrain") != "phev" or r.get("parentId"):
            continue
        e = r.get("energyConsumptionKWhPerKm")
        if e is None:
            continue
        fs = r.get("fieldSources") or {}
        if "energyConsumptionKWhPerKm" in fs:
            cite = fs.get("energyConsumptionKWhPerKm") or ""
            v = validate_energy_cite(cite, e)
            if not v.ok:
                raise SystemExit(f"energy without pure label: {r['id']}")

    for r in seed:
        if r.get("powertrain") != "phev" or r.get("parentId"):
            continue
        v = validate_completeness_flag(r)
        if not v.ok:
            raise SystemExit(f"{v.reason}: {r['id']}")

    m3 = [r for r in seed if r["id"].startswith("tesla-model-3") and r.get("year") == 2026]
    if len(m3) < 4:
        raise SystemExit(f"M3 2026 count {len(m3)}")

    if len(man.get("fields_changed") or []) != 2:
        raise SystemExit(f"expected 2 accepted fields, got {len(man.get('fields_changed') or [])}")
    if man.get("bmw_225e_2022_range") != "reverted_to_main_nil":
        raise SystemExit("manifest missing bmw revert marker")

    print(
        json.dumps(
            {
                "seedVersion": ver,
                "fingerprint": seed_fp(),
                "phev_before": [
                    man["phev_complete_before"],
                    man["phev_only_kwh_before"],
                    man["phev_multi_missing_before"],
                ],
                "phev_after": [
                    man["phev_complete_after"],
                    man["phev_only_kwh_after"],
                    man["phev_multi_missing_after"],
                ],
                "accepted": len(man.get("fields_changed") or []),
                "rejected": len(man.get("rejected") or []),
                "bmw_225e_2022_range": man.get("bmw_225e_2022_range"),
            },
            indent=2,
        )
    )
    print("OK")


if __name__ == "__main__":
    main()
