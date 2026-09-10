from __future__ import annotations

from fastapi import FastAPI, Query, Request
from fastapi.staticfiles import StaticFiles
from typing import Optional
import json
import subprocess
import sys
from pathlib import Path

from database import (
    STATE_PATH,
    get_conn,
    init_db,
    insert_event,
    insert_lead,
    list_events,
    list_leads,
    refresh_from_seed,
)


app = FastAPI(title="EVforME Vehicle Catalog API", version="1.1.0")
REPO_ROOT = Path(__file__).resolve().parents[1]
OFFICIAL_COSTS_PATH = REPO_ROOT / "EVforME?" / "Data" / "official_energy_costs.json"
OFFICIAL_COSTS_SCRIPT = REPO_ROOT / "scripts" / "fetch_official_energy_costs.py"
STATIC_DIR = Path(__file__).resolve().parent / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


def refresh_official_costs_if_possible() -> bool:
    if not OFFICIAL_COSTS_SCRIPT.exists():
        return False
    try:
        subprocess.run(
            [sys.executable, str(OFFICIAL_COSTS_SCRIPT)],
            cwd=str(REPO_ROOT),
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except Exception:
        return False


@app.on_event("startup")
def startup() -> None:
    init_db()
    refresh_official_costs_if_possible()
    with get_conn() as conn:
        count = conn.execute("SELECT COUNT(*) AS c FROM vehicles").fetchone()["c"]
    if count == 0:
        refresh_from_seed()


@app.get("/health")
def health() -> dict:
    return {"ok": True, "free": True}


@app.get("/catalog/state")
def catalog_state() -> dict:
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    return {"source": None, "rows": 0}


@app.get("/energy/default-costs")
def energy_default_costs() -> dict:
    if OFFICIAL_COSTS_PATH.exists():
        return json.loads(OFFICIAL_COSTS_PATH.read_text(encoding="utf-8"))
    return {
        "country": "IT",
        "currency": "EUR",
        "fuelPricePerLiter": 1.7,
        "electricityPricePerKWh": 0.25,
        "updatedAt": None,
        "sources": {},
    }


@app.post("/energy/sync")
def energy_sync() -> dict:
    refreshed = refresh_official_costs_if_possible()
    payload = energy_default_costs()
    return {"ok": True, "refreshed": refreshed, **payload}


@app.post("/catalog/sync")
def catalog_sync() -> dict:
    state = refresh_from_seed()
    return {"ok": True, **state}


@app.get("/catalog/export")
def catalog_export() -> list[dict]:
    """Export in app-native schema (VehicleCatalogItem JSON shape + quality fields)."""
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT
                id, brand, model, year, powertrain,
                length_m, width_m, height_m,
                fuel_consumption_l_per_km, energy_consumption_kwh_per_km,
                maintenance_per_year, taxes_per_year, image_url,
                trim, battery_kwh, wltp_range_km, wltp_consumption_kwh_100km,
                co2_g_km, market, source_name, source_updated_at, confidence_score
            FROM vehicles
            ORDER BY brand, model, year
            """
        ).fetchall()

    return [
        {
            "id": r["id"],
            "brand": r["brand"],
            "model": r["model"],
            "year": r["year"],
            "powertrain": r["powertrain"],
            "lengthM": r["length_m"],
            "widthM": r["width_m"],
            "heightM": r["height_m"],
            "fuelConsumptionLPerKm": r["fuel_consumption_l_per_km"],
            "energyConsumptionKWhPerKm": r["energy_consumption_kwh_per_km"],
            "maintenancePerYear": r["maintenance_per_year"],
            "taxesPerYear": r["taxes_per_year"],
            "imageURL": r["image_url"],
            "trim": r["trim"],
            "batteryKWh": r["battery_kwh"],
            "wltpRangeKm": r["wltp_range_km"],
            "wltpConsumptionKWh100km": r["wltp_consumption_kwh_100km"],
            "co2gKm": r["co2_g_km"],
            "market": r["market"],
            "sourceName": r["source_name"],
            "sourceUpdatedAt": r["source_updated_at"],
            "confidenceScore": r["confidence_score"],
        }
        for r in rows
    ]


@app.post("/events")
async def post_event(request: Request) -> dict:
    body = await request.json()
    event = str(body.get("event") or body.get("name") or "unknown")
    params = body.get("params") if isinstance(body.get("params"), dict) else {}
    timestamp = body.get("timestamp")
    insert_event(event, params, float(timestamp) if timestamp is not None else None)
    return {"ok": True}


@app.get("/events")
def get_events(limit: int = Query(100, ge=1, le=1000)) -> dict:
    return {"items": list_events(limit)}


@app.post("/leads")
async def post_lead(request: Request) -> dict:
    body = await request.json()
    insert_lead(body if isinstance(body, dict) else {})
    return {"ok": True}


@app.get("/leads")
def get_leads(limit: int = Query(100, ge=1, le=1000)) -> dict:
    return {"items": list_leads(limit)}


@app.get("/brands")
def brands() -> dict:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT brand, COUNT(*) AS rows FROM vehicles GROUP BY brand ORDER BY brand ASC"
        ).fetchall()
    return {"items": [dict(r) for r in rows]}


@app.get("/models")
def models(brand: str = Query(...)) -> dict:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT model, MIN(year) AS first_year, MAX(year) AS last_year, COUNT(*) AS rows
            FROM vehicles
            WHERE brand = ?
            GROUP BY model
            ORDER BY model ASC
            """,
            (brand,),
        ).fetchall()
    return {"brand": brand, "items": [dict(r) for r in rows]}


@app.get("/vehicles")
def vehicles(
    brand: Optional[str] = None,
    model: Optional[str] = None,
    powertrain: Optional[str] = None,
    year_from: Optional[int] = None,
    year_to: Optional[int] = None,
    limit: int = Query(200, ge=1, le=2000),
    offset: int = Query(0, ge=0),
) -> dict:
    where = []
    args: list = []
    if brand:
        where.append("brand = ?")
        args.append(brand)
    if model:
        where.append("model = ?")
        args.append(model)
    if powertrain:
        where.append("powertrain = ?")
        args.append(powertrain)
    if year_from is not None:
        where.append("year >= ?")
        args.append(year_from)
    if year_to is not None:
        where.append("year <= ?")
        args.append(year_to)

    where_sql = f"WHERE {' AND '.join(where)}" if where else ""
    sql = f"""
        SELECT *
        FROM vehicles
        {where_sql}
        ORDER BY brand, model, year
        LIMIT ? OFFSET ?
    """
    args.extend([limit, offset])

    with get_conn() as conn:
        rows = conn.execute(sql, tuple(args)).fetchall()
    return {"items": [dict(r) for r in rows], "limit": limit, "offset": offset}
