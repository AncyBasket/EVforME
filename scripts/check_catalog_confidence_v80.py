#!/usr/bin/env python3
"""Determinism + integrity checks for confidence policy v2 (seed v83).

Runs full unit tests + recalc preview in 6 PYTHONHASHSEED child processes on
temporary copies (no writes to the real seed).
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

REPO = Path(os.environ.get("CONF_V80_REPO_ROOT") or Path(__file__).resolve().parents[1])
CHILD = "--no-determinism"


def normalize(text: str, roots: list[str]) -> str:
    out = text
    for root in sorted(roots, key=len, reverse=True):
        out = out.replace(root, "$TMP")
    out = re.sub(r"/var/folders/[^\s]+", "$TMP", out)
    out = re.sub(r"/tmp/conf_v80_hs[^\s/]*", "$TMP", out)
    out = re.sub(r"\b\d+\.\d{3,}s\b", "$TIME", out)
    return out.strip()


def run_core() -> dict:
    sys.path.insert(0, str(REPO / "scripts"))
    from catalog_confidence import POLICY_VERSION, assess_confidence

    seed = json.loads((REPO / "EVforME?" / "Data" / "vehicles.seed.quality.json").read_text())
    cdn = json.loads((REPO / "EVforME?" / "Data" / "catalog_cdn.json").read_text())
    if int(cdn.get("seedVersion") or 0) != 83:
        raise SystemExit(f"seedVersion expected 83, got {cdn.get('seedVersion')}")
    if len(seed) != 6977:
        raise SystemExit(f"rows {len(seed)}")
    m3 = [r for r in seed if r["id"].startswith("tesla-model-3") and r.get("year") == 2026]
    if len(m3) != 4:
        raise SystemExit(f"m3 {len(m3)}")

    # reproducibility
    for row in seed:
        score, ev = assess_confidence(row)
        if row.get("confidenceScore") != score or row.get("confidenceEvidence") != ev:
            raise SystemExit(f"drift {row['id']}")
        if row.get("confidencePolicyVersion") != POLICY_VERSION:
            raise SystemExit(f"policy {row['id']}")

    # unit tests
    r = subprocess.run(
        [sys.executable, "-m", "unittest", "scripts.test_catalog_confidence", "-v"],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        check=False,
    )
    if r.returncode != 0:
        raise SystemExit(r.stdout + "\n" + r.stderr)

    # preview recalc (no write) — must report technical_drift not applicable / same distribution
    prev = subprocess.run(
        [sys.executable, "scripts/recalculate_catalog_confidence.py"],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        check=False,
    )
    if prev.returncode != 0:
        raise SystemExit(prev.stdout + "\n" + prev.stderr)

    conf = {
        "confidenceScore",
        "confidenceScoreLegacy",
        "confidencePolicyVersion",
        "confidenceEvidence",
    }

    def tech(r: dict) -> dict:
        return {k: v for k, v in r.items() if k not in conf}

    tech_blob = json.dumps([tech(r) for r in seed], sort_keys=True, separators=(",", ":"))
    report = {
        "seedVersion": cdn["seedVersion"],
        "rows": len(seed),
        "m3": sorted(r["id"] for r in m3),
        "policyVersion": POLICY_VERSION,
        "techSha": hashlib.sha256(tech_blob.encode()).hexdigest(),
        "unittest_ok": True,
        "preview_tail": [
            ln for ln in prev.stdout.strip().splitlines() if ln and not ln.startswith("policy=")
        ],
        "status": "OK",
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    print("OK")
    print("REPORT " + json.dumps(report, sort_keys=True, separators=(",", ":"), ensure_ascii=False))
    return report


def stage(tdir: Path) -> Path:
    data = tdir / "EVforME?" / "Data"
    data.mkdir(parents=True)
    shutil.copy2(REPO / "EVforME?" / "Data" / "vehicles.seed.quality.json", data / "vehicles.seed.quality.json")
    shutil.copy2(REPO / "EVforME?" / "Data" / "catalog_cdn.json", data / "catalog_cdn.json")
    api = tdir / "api" / "static"
    api.mkdir(parents=True)
    for name in ("vehicles.catalog.json", "vehicles.catalog.min.json", "catalog_cdn.json"):
        shutil.copy2(REPO / "api" / "static" / name, api / name)
    scripts = tdir / "scripts"
    scripts.mkdir(parents=True)
    (scripts / "lib").mkdir(parents=True)
    for name in (
        "catalog_confidence.py",
        "recalculate_catalog_confidence.py",
        "test_catalog_confidence.py",
        "check_catalog_confidence_v79.py",
    ):
        shutil.copy2(REPO / "scripts" / name, scripts / name)
    for name in ("__init__.py", "phev_manus_v76_validate.py"):
        shutil.copy2(REPO / "scripts" / "lib" / name, scripts / "lib" / name)
    return scripts / "check_catalog_confidence_v79.py"


def determinism() -> None:
    results: list[tuple[int, str]] = []
    roots: list[str] = []
    for hs in range(6):
        tdir = Path(tempfile.mkdtemp(prefix=f"conf_v80_hs{hs}_"))
        roots.append(str(tdir))
        try:
            script = stage(tdir)
            env = os.environ.copy()
            env["PYTHONHASHSEED"] = str(hs)
            env["CONF_V80_REPO_ROOT"] = str(tdir)
            r = subprocess.run(
                [sys.executable, str(script), CHILD],
                capture_output=True,
                text=True,
                env=env,
                cwd=str(tdir),
                check=False,
            )
            out = (r.stdout or "") + (("\n" + r.stderr) if r.stderr else "")
            results.append((r.returncode, out))
            if r.returncode != 0:
                raise SystemExit(f"hashseed={hs} failed\n{out[-4000:]}")
        finally:
            shutil.rmtree(tdir, ignore_errors=True)
    norms = [normalize(o, roots) for _, o in results]
    if len({c for c, _ in results}) != 1 or results[0][0] != 0:
        raise SystemExit(f"exit drift {[c for c,_ in results]}")
    reports = []
    for n in norms:
        m = re.search(r"^REPORT (.+)$", n, re.M)
        reports.append(m.group(1) if m else n[-500:])
    if len(set(reports)) != 1:
        raise SystemExit("REPORT drift:\n" + "\n---\n".join(reports))
    print(f"PYTHONHASHSEED 0..5 full-check identical ({len(results)} children)")
    print("SHA", hashlib.sha256(reports[0].encode()).hexdigest())
    print("OK")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument(CHILD, action="store_true")
    args = p.parse_args()
    if args.no_determinism:
        run_core()
    else:
        determinism()


if __name__ == "__main__":
    main()
