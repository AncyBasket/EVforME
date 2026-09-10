#!/usr/bin/env python3
"""
Scarica dati reali da fonti pubbliche citate:
- NHTSA vPIC (gratis, no key)
- VCA UK fuel/CO2 dataset (CSV pubblico)
- EEA CO2 cars landing metadata (pubblico)

Output:
- EVforME?/Data/external/*.json|csv|html
- EVforME?/Data/external/fetch_manifest.json
"""

from __future__ import annotations

import csv
import json
import re
import ssl
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class FetchResult:
    name: str
    ok: bool
    detail: str
    output: str | None = None


def http_get(url: str, timeout: int = 60) -> bytes:
    ctx = ssl.create_default_context()
    req = urllib.request.Request(url, headers={"User-Agent": "EVforME-data-fetch/1.0"})
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
        return resp.read()


def fetch_vpic_makes_models(out_dir: Path) -> FetchResult:
    try:
        makes_url = "https://vpic.nhtsa.dot.gov/api/vehicles/GetMakesForVehicleType/car?format=json"
        makes_data = json.loads(http_get(makes_url).decode("utf-8", errors="replace"))
        makes = makes_data.get("Results", [])
        out_makes = out_dir / "nhtsa_getallmakes.json"
        out_makes.write_text(json.dumps(makes_data, ensure_ascii=False, indent=2), encoding="utf-8")

        # Per velocità, scarica modelli per tutte le marche auto (dataset già filtrato vehicleType=car)
        top_makes = sorted({m.get("MakeName", "") for m in makes if m.get("MakeName")})
        models_payload: dict[str, list[dict]] = {}
        model_errors: dict[str, str] = {}
        for make in top_makes:
            try:
                safe_make = urllib.parse.quote(make, safe="")
                models_url = f"https://vpic.nhtsa.dot.gov/api/vehicles/GetModelsForMake/{safe_make}?format=json"
                model_data = json.loads(http_get(models_url).decode("utf-8", errors="replace"))
                models_payload[make] = model_data.get("Results", [])
            except Exception as make_exc:  # noqa: BLE001
                model_errors[make] = str(make_exc)

        out_models = out_dir / "nhtsa_models_top120_makes.json"
        out_models.write_text(
            json.dumps(
                {
                    "source": "NHTSA vPIC",
                    "total_makes": len(makes),
                    "sampled_makes": len(top_makes),
                    "models_by_make": models_payload,
                    "model_fetch_errors": model_errors,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        return FetchResult(
            name="nhtsa_vpic",
            ok=True,
            detail=(
                f"Fetched {len(makes)} makes; models ok for {len(models_payload)} makes, "
                f"errors for {len(model_errors)} makes."
            ),
            output=f"{out_makes.name}, {out_models.name}",
        )
    except Exception as exc:  # noqa: BLE001
        return FetchResult(name="nhtsa_vpic", ok=False, detail=str(exc))


def fetch_vca_latest_csv(out_dir: Path) -> FetchResult:
    try:
        # 1) Apri pagina download e trova link CSV reali
        listing_url = "https://carfueldata.vehicle-certification-agency.gov.uk/downloads/default.aspx"
        listing_html = http_get(listing_url, timeout=120).decode("utf-8", errors="replace")
        listing_path = out_dir / "vca_downloads_listing.html"
        listing_path.write_text(listing_html, encoding="utf-8")

        candidates: list[str] = []
        for token in listing_html.split("href="):
            if not token.startswith("\""):
                continue
            href = token[1:].split("\"", 1)[0]
            href_l = href.lower()
            if ".csv" in href_l or "download.aspx" in href_l:
                candidates.append(urllib.parse.urljoin(listing_url, href))

        # de-dup mantenendo ordine
        seen: set[str] = set()
        links = [u for u in candidates if not (u in seen or seen.add(u))]

        # 2) Prova i candidati finché troviamo un CSV
        attempts: list[str] = []
        for url in links[:20]:
            attempts.append(url)
            raw = http_get(url, timeout=120)
            text = raw.decode("utf-8", errors="replace")
            if "," in text and "\n" in text and ("make" in text[:1000].lower() or "manufacturer" in text[:1000].lower()):
                csv_path = out_dir / "vca_latest.csv"
                csv_path.write_text(text, encoding="utf-8")
                rows = list(csv.reader(text.splitlines()))
                row_count = max(0, len(rows) - 1)
                attempts_path = out_dir / "vca_attempted_links.json"
                attempts_path.write_text(json.dumps({"attempted": attempts}, indent=2), encoding="utf-8")
                return FetchResult(
                    name="vca_fuel_data",
                    ok=True,
                    detail=f"Fetched CSV with ~{row_count} rows.",
                    output=f"{csv_path.name}, {attempts_path.name}",
                )

        attempts_path = out_dir / "vca_attempted_links.json"
        attempts_path.write_text(json.dumps({"attempted": attempts}, indent=2), encoding="utf-8")
        return FetchResult(
            name="vca_fuel_data",
            ok=False,
            detail="Could not resolve direct CSV from download listing; saved listing and attempts.",
            output=f"{listing_path.name}, {attempts_path.name}",
        )
    except Exception as exc:  # noqa: BLE001
        return FetchResult(name="vca_fuel_data", ok=False, detail=str(exc))


def fetch_eea_metadata(out_dir: Path) -> FetchResult:
    try:
        # Landing dataset page (pubblica) per monitoring CO2 cars
        url = "https://www.eea.europa.eu/data-and-maps/data/co2-cars-emission-22"
        page = http_get(url, timeout=120).decode("utf-8", errors="replace")
        html_path = out_dir / "eea_co2_cars_landing.html"
        html_path.write_text(page, encoding="utf-8")

        # Estrarre link DOI presenti nella pagina (indicazione download ufficiale)
        dois: list[str] = []
        for m in re.findall(r"https?://doi\.org/[^\s\"'<>]+", page):
            if m not in dois:
                dois.append(m)

        dataset_table_tags = re.findall(r"co2cars_[0-9A-Za-z_]+", page)
        dataset_table_tags = sorted(set(dataset_table_tags))

        meta = {
            "source": "EEA co2 cars",
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "dois_found": dois,
            "dataset_table_tags": dataset_table_tags,
        }
        meta_path = out_dir / "eea_co2_cars_metadata.json"
        meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        return FetchResult(
            name="eea_co2",
            ok=True,
            detail=f"Fetched landing page, found {len(dois)} DOI links.",
            output=f"{html_path.name}, {meta_path.name}",
        )
    except Exception as exc:  # noqa: BLE001
        return FetchResult(name="eea_co2", ok=False, detail=str(exc))


def main() -> None:
    repo = Path(__file__).resolve().parents[1]
    out_dir = repo / "EVforME?" / "Data" / "external"
    out_dir.mkdir(parents=True, exist_ok=True)

    results = [
        fetch_vpic_makes_models(out_dir),
        fetch_vca_latest_csv(out_dir),
        fetch_eea_metadata(out_dir),
    ]

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "results": [
            {
                "name": r.name,
                "ok": r.ok,
                "detail": r.detail,
                "output": r.output,
            }
            for r in results
        ],
    }

    manifest_path = out_dir / "fetch_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

