from __future__ import annotations

from fastapi import FastAPI, Query, Request
from fastapi import HTTPException
from fastapi.staticfiles import StaticFiles
from typing import Optional
import json
import hmac
import math
import os
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

from database import (
    STATE_PATH,
    get_conn,
    init_db,
    insert_event,
    insert_lead,
    list_events,
    list_leads,
    purge_expired_data,
    refresh_from_seed,
    seed_is_current,
)


app = FastAPI(title="EVforME Vehicle Catalog API", version="1.1.0")
REPO_ROOT = Path(__file__).resolve().parents[1]
OFFICIAL_COSTS_PATH = REPO_ROOT / "EVforME?" / "Data" / "official_energy_costs.json"
OFFICIAL_COSTS_SCRIPT = REPO_ROOT / "scripts" / "fetch_official_energy_costs.py"
STATIC_DIR = Path(__file__).resolve().parent / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

MAX_BODY_BYTES = 16 * 1024
DEFAULT_RETENTION_DAYS = 180
EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s.]+(?:\.[^@\s.]+)+$")
EVENT_KEY_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,63}$")
_rate_buckets: dict[tuple[str, str], list[float]] = {}
_rate_lock = threading.Lock()


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


def _retention_days() -> int:
    try:
        configured = int(os.environ.get("EVFORME_RETENTION_DAYS", DEFAULT_RETENTION_DAYS))
        return min(3650, max(1, configured))
    except (TypeError, ValueError):
        return DEFAULT_RETENTION_DAYS


def _require_admin(request: Request) -> None:
    expected = os.environ.get("EVFORME_ADMIN_TOKEN", "").strip()
    if len(expected) < 32:
        raise HTTPException(status_code=503, detail="Admin read access is not configured")
    scheme, _, supplied = request.headers.get("authorization", "").partition(" ")
    if scheme.lower() != "bearer" or not hmac.compare_digest(supplied, expected):
        raise HTTPException(
            status_code=401,
            detail="Valid bearer token required",
            headers={"WWW-Authenticate": "Bearer"},
        )


def _enforce_rate_limit(request: Request, route: str, limit: int) -> None:
    host = request.client.host if request.client else "unknown"
    key = (route, host)
    now = time.monotonic()
    with _rate_lock:
        recent = [stamp for stamp in _rate_buckets.get(key, []) if now - stamp < 60]
        if len(recent) >= limit:
            raise HTTPException(status_code=429, detail="Too many requests; retry in a minute")
        recent.append(now)
        _rate_buckets[key] = recent


async def _read_json_object(request: Request) -> dict:
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > MAX_BODY_BYTES:
                raise HTTPException(status_code=413, detail="Request body too large")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid Content-Length")
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > MAX_BODY_BYTES:
            raise HTTPException(status_code=413, detail="Request body too large")
    try:
        payload = json.loads(bytes(body))
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise HTTPException(status_code=400, detail="Invalid JSON")
    if not isinstance(payload, dict):
        raise HTTPException(status_code=422, detail="JSON object required")
    return payload


def _clean_optional_text(value, field: str, max_length: int, required: bool = False) -> str | None:
    if value is None and not required:
        return None
    if not isinstance(value, str):
        raise HTTPException(status_code=422, detail=f"{field} must be text")
    cleaned = " ".join(value.split()).strip()
    if required and not cleaned:
        raise HTTPException(status_code=422, detail=f"{field} is required")
    if len(cleaned) > max_length:
        raise HTTPException(status_code=422, detail=f"{field} is too long")
    return cleaned or None


@app.on_event("startup")
def startup() -> None:
    init_db()
    purge_expired_data(_retention_days())
    refresh_official_costs_if_possible()
    if not seed_is_current():
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
def energy_sync(request: Request) -> dict:
    _require_admin(request)
    refreshed = refresh_official_costs_if_possible()
    payload = energy_default_costs()
    return {"ok": True, "refreshed": refreshed, **payload}


@app.post("/catalog/sync")
def catalog_sync(request: Request) -> dict:
    _require_admin(request)
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
                co2_g_km, market, source_name, source_updated_at, confidence_score,
                confidence_score_legacy, confidence_policy_version, confidence_evidence_json
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
            "confidenceScoreLegacy": r["confidence_score_legacy"],
            "confidencePolicyVersion": r["confidence_policy_version"],
            "confidenceEvidence": json.loads(r["confidence_evidence_json"])
            if r["confidence_evidence_json"]
            else None,
        }
        for r in rows
    ]


@app.post("/events")
async def post_event(request: Request) -> dict:
    _enforce_rate_limit(request, "events", 120)
    body = await _read_json_object(request)
    event = _clean_optional_text(body.get("event") or body.get("name") or "unknown", "event", 80, True)
    raw_params = body.get("params", {})
    if not isinstance(raw_params, dict) or len(raw_params) > 32:
        raise HTTPException(status_code=422, detail="params must be an object with at most 32 fields")
    params: dict[str, str] = {}
    forbidden_fields = {"name", "email", "phone", "address", "city", "latitude", "longitude"}
    for key, value in raw_params.items():
        if not isinstance(key, str) or not EVENT_KEY_RE.fullmatch(key):
            raise HTTPException(status_code=422, detail="Invalid event parameter name")
        if key.lower() in forbidden_fields:
            raise HTTPException(status_code=422, detail="Personal fields are not accepted in analytics")
        if isinstance(value, bool):
            normalized = str(value).lower()
        elif isinstance(value, (str, int, float)) and (not isinstance(value, float) or math.isfinite(value)):
            normalized = str(value)
        else:
            raise HTTPException(status_code=422, detail="Event values must be short scalar values")
        if len(normalized) > 256:
            raise HTTPException(status_code=422, detail="Event value is too long")
        params[key] = normalized
    raw_timestamp = body.get("timestamp")
    timestamp = None
    if raw_timestamp is not None:
        if isinstance(raw_timestamp, bool):
            raise HTTPException(status_code=422, detail="Invalid event timestamp")
        try:
            timestamp = float(raw_timestamp)
        except (TypeError, ValueError):
            raise HTTPException(status_code=422, detail="Invalid event timestamp")
        if not math.isfinite(timestamp):
            raise HTTPException(status_code=422, detail="Invalid event timestamp")
    purge_expired_data(_retention_days())
    insert_event(event, params, timestamp)
    return {"ok": True}


@app.get("/events")
def get_events(request: Request, limit: int = Query(100, ge=1, le=1000)) -> dict:
    _require_admin(request)
    purge_expired_data(_retention_days())
    return {"items": list_events(limit)}


@app.post("/leads")
async def post_lead(request: Request) -> dict:
    _enforce_rate_limit(request, "leads", 5)
    body = await _read_json_object(request)
    if body.get("consent") is not True:
        raise HTTPException(status_code=422, detail="Explicit consent is required")
    name = _clean_optional_text(body.get("name"), "name", 120)
    email = _clean_optional_text(body.get("email"), "email", 254, True)
    city = _clean_optional_text(body.get("city"), "city", 120)
    if not EMAIL_RE.fullmatch(email or ""):
        raise HTTPException(status_code=422, detail="A valid email address is required")
    purge_expired_data(_retention_days())
    insert_lead({"name": name, "email": email, "city": city, "consent": True})
    return {"ok": True}


@app.get("/leads")
def get_leads(request: Request, limit: int = Query(100, ge=1, le=1000)) -> dict:
    _require_admin(request)
    purge_expired_data(_retention_days())
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
