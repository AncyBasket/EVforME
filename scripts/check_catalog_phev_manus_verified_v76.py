#!/usr/bin/env python3
"""Verify selective Manus PHEV recovery (seed v76) with real negative + determinism tests.

Parent: PYTHONHASHSEED 0..5 → 6 child processes, each running the *same* full verification
on a temporary artifact tree (--no-determinism). No recursive determinism nesting.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(os.environ.get("PHEV_V76_REPO_ROOT") or Path(__file__).resolve().parents[1])
sys.path.insert(0, str(REPO / "scripts"))
from lib.phev_manus_v76_validate import (  # noqa: E402
    inspect_download,
    missing_calc_fields,
    validate_completeness_flag,
    validate_cs_interval_pick,
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
PREV = 75
CHILD_FLAG = "--no-determinism"


def seed_fp(path: Path = SEED) -> str:
    rows = json.loads(path.read_text(encoding="utf-8"))
    blob = json.dumps(rows, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(blob.encode()).hexdigest()


def must_fail_fixtures() -> list[str]:
    """Fixtures go through the same validators used on real imports/downloads."""
    cases: list[tuple[str, bool, str, object]] = []

    v = validate_energy_cite("Consommations d'énergie électrique 16,8 (no CD label)", 0.168)
    cases.append(("energy_without_pure_label", False, "energy_without_pure_label", v))

    v_ok = validate_energy_cite("consumo elettrico puro (CD) 16,8 kWh/100 km", 0.168)
    cases.append(("energy_with_pure_label", True, "ok_energy", v_ok))

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

    fake = OEM / "bmw_2at_press_652064.html"
    if not fake.exists():
        fake = Path(tempfile.mkstemp(suffix=".pdf")[1])
        fake.write_text("<!DOCTYPE html><html><title>Listino 2026</title></html>", encoding="utf-8")
    v = inspect_download(fake, claimed_ext=".pdf")
    cases.append(("fake_pdf_html", False, "fake_pdf_html", v))

    for name in ("toyota_rav4_my23.pdf", "cupra_ie_jan2024.pdf"):
        p = OEM / name
        if not p.exists():
            raise SystemExit(f"missing OEM artifact required for check: {p}")
        v = inspect_download(p)
        cases.append((f"ok_pdf_{name}", True, "ok_format", v))

    v = validate_range_label("EAER City 55 km", 55)
    cases.append(("eaer_city_only", False, "eaer_city_only", v))

    v = validate_range_label("autonomia elettrica 83–92 km secondo WLTP combinato", 92)
    cases.append(("non_prudent_range_max", False, "non_prudent_range_extremum", v))
    v = validate_range_label("autonomia elettrica 83–92 km secondo WLTP combinato", 83)
    cases.append(("prudent_range_min", True, "ok_range", v))

    v = validate_cs_interval_pick(5.2, 6.1, 5.2)
    cases.append(("non_prudent_cs_min", False, "non_prudent_cs_extremum", v))
    v = validate_cs_interval_pick(5.2, 6.1, 6.1)
    cases.append(("prudent_cs_max", True, "ok_cs_max", v))

    press = OEM / "bmw_225e_press_T0390613DE.html"
    if not press.exists():
        raise SystemExit(f"missing press HTML evidence: {press}")
    v = validate_field_import(
        row_year=2022,
        field="wltpRangeKm",
        value=83,
        url="https://www.press.bmwgroup.com/deutschland/article/detail/T0390613DE/bmw-modellpflege-massnahmen-zum-sommer-2022?language=de",
        source_date="2022-05-18",
        label="83–92 km WLTP",
        download_path=press,
    )
    cases.append(("live_page_past_year", False, "live_page_past_year", v))

    toy_pdf = OEM / "toyota_rav4_my23.pdf"
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

    lines: list[str] = []
    failed: list[str] = []
    for label, expect_ok, expect_reason, verdict in cases:
        ok = verdict.ok == expect_ok and (expect_reason in verdict.reason)
        status = "OK" if ok else "FAIL"
        line = f"must-fail {status}: {label} → {verdict.reason}"
        lines.append(line)
        print(line)
        if not ok:
            failed.append(
                f"{label}: expect ok={expect_ok}/{expect_reason} got {verdict.ok}/{verdict.reason}"
            )
    if failed:
        raise SystemExit("must-fail failures:\n" + "\n".join(failed))
    summary = f"must-fail fixtures: {len(cases)}/{len(cases)} via shared validators"
    print(summary)
    lines.append(summary)
    return lines


def run_core_checks() -> dict:
    """Full shared verification: fixtures, OEM docs, imports, completeness, rejects, integrity."""
    fixture_lines = must_fail_fixtures()

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
    v = validate_field_import(
        row_year=2024,
        field="batteryKWh",
        value=cup.get("batteryKWh"),
        url="https://www.cupra.com/content/dam/countries/ie/cupra-website/product-guide/formentor/cars-models-info-KM7-product-guide-Jan-2024.pdf",
        source_date=(cup.get("fieldSourceDates") or {}).get("batteryKWh"),
        label=(cup.get("fieldSources") or {}).get("batteryKWh") or "",
        download_path=OEM / "cupra_ie_jan2024.pdf",
    )
    if not v.ok:
        raise SystemExit(f"cupra real-row validation failed: {v.reason}")

    b22 = by_id["bmw-serie-2-active-tourer-225e-xdrive-2022"]
    if b22.get("wltpRangeKm") is not None:
        raise SystemExit("225e 2022 range must be nil (no admissible 2022 proof)")
    if b22.get("batteryKWh") is not None:
        raise SystemExit("225e 2022 battery must stay nil")
    if (b22.get("fieldSourceDates") or {}).get("wltpRangeKm"):
        raise SystemExit("225e 2022 range provenance must be removed")
    if "manus-verified v76: wltpRangeKm" in (b22.get("sourceName") or ""):
        raise SystemExit("225e 2022 range sourceName note must be removed")
    bmw_miss = missing_calc_fields(b22)
    if "wltpRangeKm" not in bmw_miss or "batteryKWh" not in bmw_miss:
        raise SystemExit(f"225e 2022 missingCalcFields incomplete: {bmw_miss}")

    fake_html = OEM / "bmw_2at_press_652064.html"
    if not fake_html.exists():
        raise SystemExit("missing renamed HTML listino artifact")
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
        if rid.startswith("bmw") and r.get("wltpRangeKm") is not None:
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

    m3 = sorted(
        r["id"] for r in seed if r["id"].startswith("tesla-model-3") and r.get("year") == 2026
    )
    if len(m3) < 4:
        raise SystemExit(f"M3 2026 count {len(m3)}")

    if len(man.get("fields_changed") or []) != 2:
        raise SystemExit(f"expected 2 accepted fields, got {len(man.get('fields_changed') or [])}")
    if man.get("bmw_225e_2022_range") != "reverted_to_main_nil":
        raise SystemExit("manifest missing bmw revert marker")

    parents = [r for r in seed if r.get("powertrain") == "phev" and not r.get("parentId")]
    c = k = m = 0
    for r in parents:
        miss = missing_calc_fields(r)
        if not miss:
            c += 1
        elif miss == ["energyConsumptionKWhPerKm"]:
            k += 1
        else:
            m += 1

    report = {
        "seedVersion": ver,
        "fingerprint": seed_fp(),
        "rows": len(seed),
        "phev_counts": [c, k, m],
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
        "accepted": sorted(
            (x["id"], x["field"], x["after"]) for x in (man.get("fields_changed") or [])
        ),
        "rejected": sorted((x["id"], x["field"]) for x in (man.get("rejected") or [])),
        "bmw_225e_2022_range": man.get("bmw_225e_2022_range"),
        "toyota_battery": toy.get("batteryKWh"),
        "cupra_battery": cup.get("batteryKWh"),
        "bmw_range": b22.get("wltpRangeKm"),
        "bmw_missing": bmw_miss,
        "m3": m3,
        "fixture_count": len(fixture_lines),
        "status": "OK",
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    print("OK")
    # machine-readable single line for determinism compare
    print("REPORT " + json.dumps(report, sort_keys=True, separators=(",", ":"), ensure_ascii=False))
    return report


def normalize_child_output(text: str, tmp_roots: list[str]) -> str:
    """Drop temp paths only; keep verification content."""
    out = text
    for root in sorted(tmp_roots, key=len, reverse=True):
        out = out.replace(root, "$TMP")
        out = out.replace(root.replace("\\", "/"), "$TMP")
    # strip absolute user paths that may appear in tracebacks
    out = re.sub(r"/var/folders/[^\s]+", "$TMP", out)
    out = re.sub(r"/tmp/phev_v76_hs[^\s/]*", "$TMP", out)
    # drop pure timing if any sneaks in
    out = re.sub(r"\b\d+\.\d{3,}s\b", "$TIME", out)
    return out.strip()


def _stage_temp_tree(tdir: Path) -> Path:
    """Copy artifacts needed for full verification; never touches the real seed."""
    data = tdir / "EVforME?" / "Data"
    data.mkdir(parents=True)
    shutil.copy2(SEED, data / "vehicles.seed.quality.json")
    shutil.copy2(CDN, data / "catalog_cdn.json")

    scripts = tdir / "scripts"
    (scripts / "cache" / "eea").mkdir(parents=True)
    (scripts / "lib").mkdir(parents=True)
    (scripts / "cache" / "oem" / "manus_verify").mkdir(parents=True)

    shutil.copy2(Path(__file__).resolve(), scripts / Path(__file__).name)
    for name in ("phev_manus_v76_validate.py", "__init__.py"):
        shutil.copy2(REPO / "scripts" / "lib" / name, scripts / "lib" / name)
    shutil.copy2(MANIFEST, scripts / "cache" / "eea" / MANIFEST.name)
    for p in OEM.iterdir():
        if p.is_file():
            shutil.copy2(p, scripts / "cache" / "oem" / "manus_verify" / p.name)
    return scripts / Path(__file__).name


def determinism_pipeline() -> None:
    """Run the same full check in 6 processes (PYTHONHASHSEED 0..5) on temp trees."""
    results: list[tuple[int, str]] = []
    tmp_roots: list[str] = []
    for seed_val in range(6):
        tdir = Path(tempfile.mkdtemp(prefix=f"phev_v76_hs{seed_val}_"))
        tmp_roots.append(str(tdir))
        try:
            child_script = _stage_temp_tree(tdir)
            env = os.environ.copy()
            env["PYTHONHASHSEED"] = str(seed_val)
            env["PHEV_V76_REPO_ROOT"] = str(tdir)
            # Ensure child cannot re-enter determinism
            r = subprocess.run(
                [sys.executable, str(child_script), CHILD_FLAG],
                capture_output=True,
                text=True,
                env=env,
                cwd=str(tdir),
                check=False,
            )
            combined = (r.stdout or "") + (("\n" + r.stderr) if r.stderr else "")
            results.append((r.returncode, combined))
            if r.returncode != 0:
                raise SystemExit(
                    f"determinism PYTHONHASHSEED={seed_val} exit={r.returncode}\n{combined[-4000:]}"
                )
        finally:
            shutil.rmtree(tdir, ignore_errors=True)

    normalized = [normalize_child_output(out, tmp_roots) for _, out in results]
    codes = [c for c, _ in results]
    if len(set(codes)) != 1 or codes[0] != 0:
        raise SystemExit(f"PYTHONHASHSEED exit codes drift: {codes}")
    if len(set(normalized)) != 1:
        # show compact diff keys
        reports = []
        for n in normalized:
            m = re.search(r"^REPORT (.+)$", n, re.M)
            reports.append(m.group(1) if m else n[-500:])
        if len(set(reports)) != 1:
            raise SystemExit(
                "PYTHONHASHSEED report drift:\n" + "\n---\n".join(reports)
            )
        raise SystemExit("PYTHONHASHSEED normalized stdout drift (non-REPORT lines)")

    report_line = re.search(r"^REPORT (.+)$", normalized[0], re.M)
    print(f"PYTHONHASHSEED 0..5 full-check identical ({len(results)} child processes)")
    if report_line:
        blob = report_line.group(1)
        print("SHA", hashlib.sha256(blob.encode()).hexdigest())
        print(blob[:200] + ("…" if len(blob) > 200 else ""))
    print("OK")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        CHILD_FLAG,
        action="store_true",
        help="Child mode: run full core checks only (no nested determinism).",
    )
    args = parser.parse_args()
    if args.no_determinism:
        run_core_checks()
        return
    determinism_pipeline()


if __name__ == "__main__":
    main()
