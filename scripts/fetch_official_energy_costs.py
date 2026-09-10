#!/usr/bin/env python3
"""
Fetch costi ufficiali iniziali (Italia) da fonti pubbliche:
- Carburante: MIMIT Osservaprezzi (prezzo_alle_8.csv)
- Elettricita': Eurostat nrg_pc_204 (prezzi household)

Output:
- EVforME?/Data/official_energy_costs.json
- EVforME?/Data/external/official_energy_costs_manifest.json
"""

from __future__ import annotations

import csv
import json
import ssl
import statistics
import urllib.request
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path


def http_get_text(url: str, timeout: int = 60) -> str:
    ctx = ssl.create_default_context()
    req = urllib.request.Request(url, headers={"User-Agent": "EVforME-official-costs/1.0"})
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
        return resp.read().decode("utf-8", errors="replace")


def http_get_json(url: str, timeout: int = 60) -> dict:
    return json.loads(http_get_text(url, timeout=timeout))


def fetch_mimit_benzina_price() -> tuple[float, dict]:
    """
    Restituisce una stima robusta del prezzo benzina (EUR/L) da MIMIT.
    Usa mediana prezzi "self" per ridurre outlier.
    """
    url = "https://www.mimit.gov.it/images/exportCSV/prezzo_alle_8.csv"
    text = http_get_text(url)
    lines = text.splitlines()
    extraction = lines[0].strip() if lines else ""

    reader = csv.DictReader(StringIO("\n".join(lines[1:])), delimiter="|")
    vals: list[float] = []
    for row in reader:
        if str(row.get("descCarburante", "")).strip().lower() != "benzina":
            continue
        if str(row.get("isSelf", "")).strip() != "1":
            continue
        raw = str(row.get("prezzo", "")).replace(",", ".").strip()
        try:
            v = float(raw)
        except ValueError:
            continue
        # guardrail antirumore
        if 0.8 <= v <= 3.5:
            vals.append(v)

    if not vals:
        raise RuntimeError("No benzina self prices parsed from MIMIT CSV")

    median_price = float(statistics.median(vals))
    return median_price, {
        "source": "MIMIT prezzo_alle_8.csv",
        "rows_used": len(vals),
        "extraction": extraction,
        "url": url,
    }


def jsonstat_index(pos: list[int], sizes: list[int]) -> int:
    idx = 0
    stride = 1
    for p, s in zip(reversed(pos), reversed(sizes)):
        idx += p * stride
        stride *= s
    return idx


def fetch_eurostat_electricity_price_it() -> tuple[float, dict]:
    """
    Prezzo elettricita' household Italia da Eurostat (EUR/kWh, incl. tax).
    Dataset: nrg_pc_204
    """
    url = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/nrg_pc_204?geo=IT"
    data = http_get_json(url)

    dims = data["id"]
    sizes = data["size"]
    dim_meta = data["dimension"]

    idx_maps = {d: dim_meta[d]["category"]["index"] for d in dims}
    rev_time = {v: k for k, v in idx_maps["time"].items()}
    time_order = sorted(rev_time.keys())
    values = data.get("value", {})

    # Segmento domestico rappresentativo: 1000-2499 kWh (classe standard household)
    target = {
        "freq": "S",
        "siec": "E7000",
        "nrg_cons": "KWH1000-2499",
        "unit": "KWH",
        "tax": "I_TAX",
        "currency": "EUR",
        "geo": "IT",
    }

    latest_val = None
    latest_time = None
    for t_pos in reversed(time_order):
        pos = []
        ok = True
        for d in dims:
            if d == "time":
                pos.append(t_pos)
                continue
            key = target.get(d)
            if key is None or key not in idx_maps[d]:
                ok = False
                break
            pos.append(idx_maps[d][key])
        if not ok:
            continue
        flat = jsonstat_index(pos, sizes)
        v = values.get(str(flat))
        if v is None:
            continue
        latest_val = float(v)
        latest_time = rev_time[t_pos]
        break

    if latest_val is None:
        raise RuntimeError("No Eurostat electricity value found for IT target slice")

    return latest_val, {
        "source": "Eurostat nrg_pc_204",
        "series": target,
        "latest_period": latest_time,
        "url": url,
    }


def main() -> None:
    repo = Path(__file__).resolve().parents[1]
    data_dir = repo / "EVforME?" / "Data"
    ext_dir = data_dir / "external"
    ext_dir.mkdir(parents=True, exist_ok=True)

    fuel, fuel_meta = fetch_mimit_benzina_price()
    elec, elec_meta = fetch_eurostat_electricity_price_it()

    out = {
        "country": "IT",
        "currency": "EUR",
        "fuelPricePerLiter": round(fuel, 3),
        "electricityPricePerKWh": round(elec, 3),
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        "sources": {
            "fuel": fuel_meta,
            "electricity": elec_meta,
        },
    }

    out_path = data_dir / "official_energy_costs.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    manifest = {
        "ok": True,
        "output": out_path.name,
        "fuelPricePerLiter": out["fuelPricePerLiter"],
        "electricityPricePerKWh": out["electricityPricePerKWh"],
        "updatedAt": out["updatedAt"],
    }
    (ext_dir / "official_energy_costs_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

