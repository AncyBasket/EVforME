from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = REPO_ROOT / "api" / "vehicle_catalog.db"
SEED_PREFERRED = [
    REPO_ROOT / "EVforME?" / "Data" / "vehicles.seed.quality.json",
    REPO_ROOT / "EVforME?" / "Data" / "vehicles.seed.wltp_enriched.json",
    REPO_ROOT / "EVforME?" / "Data" / "vehicles.seed.nhtsa_enriched.with_images.json",
    REPO_ROOT / "EVforME?" / "Data" / "vehicles.seed.nhtsa_enriched.json",
    REPO_ROOT / "EVforME?" / "Data" / "vehicles.seed.json",
]
STATE_PATH = REPO_ROOT / "api" / "catalog_state.json"


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_column(conn: sqlite3.Connection, name: str, ddl: str) -> None:
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(vehicles)").fetchall()}
    if name not in cols:
        conn.execute(f"ALTER TABLE vehicles ADD COLUMN {ddl}")


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS vehicles (
                id TEXT PRIMARY KEY,
                brand TEXT NOT NULL,
                model TEXT NOT NULL,
                year INTEGER NOT NULL,
                powertrain TEXT NOT NULL,
                length_m REAL,
                width_m REAL,
                height_m REAL,
                fuel_consumption_l_per_km REAL,
                energy_consumption_kwh_per_km REAL,
                maintenance_per_year REAL,
                taxes_per_year REAL,
                image_url TEXT
            )
            """
        )
        for name, ddl in [
            ("trim", "trim TEXT"),
            ("battery_kwh", "battery_kwh REAL"),
            ("wltp_range_km", "wltp_range_km INTEGER"),
            ("wltp_consumption_kwh_100km", "wltp_consumption_kwh_100km REAL"),
            ("co2_g_km", "co2_g_km REAL"),
            ("market", "market TEXT"),
            ("source_name", "source_name TEXT"),
            ("source_updated_at", "source_updated_at TEXT"),
            ("confidence_score", "confidence_score REAL"),
        ]:
            _ensure_column(conn, name, ddl)

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS growth_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event TEXT NOT NULL,
                params_json TEXT,
                timestamp REAL,
                received_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS leads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                email TEXT,
                city TEXT,
                consent INTEGER,
                payload_json TEXT,
                received_at TEXT NOT NULL
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_vehicles_brand_model ON vehicles(brand, model)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_vehicles_year ON vehicles(year)")


def load_seed_path() -> Path:
    return next((p for p in SEED_PREFERRED if p.exists()), SEED_PREFERRED[-1])


def refresh_from_seed() -> dict:
    init_db()
    seed_path = load_seed_path()
    records = json.loads(seed_path.read_text(encoding="utf-8"))

    with get_conn() as conn:
        conn.execute("DELETE FROM vehicles")
        conn.executemany(
            """
            INSERT INTO vehicles (
                id, brand, model, year, powertrain, length_m, width_m, height_m,
                fuel_consumption_l_per_km, energy_consumption_kwh_per_km,
                maintenance_per_year, taxes_per_year, image_url,
                trim, battery_kwh, wltp_range_km, wltp_consumption_kwh_100km,
                co2_g_km, market, source_name, source_updated_at, confidence_score
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    r["id"],
                    r["brand"],
                    r["model"],
                    int(r["year"]),
                    r["powertrain"],
                    r.get("lengthM"),
                    r.get("widthM"),
                    r.get("heightM"),
                    r.get("fuelConsumptionLPerKm"),
                    r.get("energyConsumptionKWhPerKm"),
                    r.get("maintenancePerYear"),
                    r.get("taxesPerYear"),
                    r.get("imageURL"),
                    r.get("trim"),
                    r.get("batteryKWh"),
                    r.get("wltpRangeKm"),
                    r.get("wltpConsumptionKWh100km"),
                    r.get("co2gKm"),
                    r.get("market", "IT"),
                    r.get("sourceName"),
                    r.get("sourceUpdatedAt"),
                    r.get("confidenceScore"),
                )
                for r in records
            ],
        )

    state = {
        "source": str(seed_path.name),
        "rows": len(records),
        "syncedAt": datetime.now(timezone.utc).isoformat(),
    }
    STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")
    return state


def insert_event(event: str, params: dict | None, timestamp: float | None) -> None:
    init_db()
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO growth_events (event, params_json, timestamp, received_at)
            VALUES (?, ?, ?, ?)
            """,
            (
                event,
                json.dumps(params or {}, ensure_ascii=False),
                timestamp,
                datetime.now(timezone.utc).isoformat(),
            ),
        )


def list_events(limit: int = 100) -> list[dict]:
    init_db()
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT id, event, params_json, timestamp, received_at
            FROM growth_events
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    out = []
    for r in rows:
        out.append(
            {
                "id": r["id"],
                "event": r["event"],
                "params": json.loads(r["params_json"] or "{}"),
                "timestamp": r["timestamp"],
                "receivedAt": r["received_at"],
            }
        )
    return out


def insert_lead(payload: dict) -> None:
    init_db()
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO leads (name, email, city, consent, payload_json, received_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                payload.get("name"),
                payload.get("email"),
                payload.get("city"),
                1 if payload.get("consent") else 0,
                json.dumps(payload, ensure_ascii=False),
                datetime.now(timezone.utc).isoformat(),
            ),
        )


def list_leads(limit: int = 100) -> list[dict]:
    init_db()
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT id, name, email, city, consent, payload_json, received_at
            FROM leads
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [
        {
            "id": r["id"],
            "name": r["name"],
            "email": r["email"],
            "city": r["city"],
            "consent": bool(r["consent"]),
            "payload": json.loads(r["payload_json"] or "{}"),
            "receivedAt": r["received_at"],
        }
        for r in rows
    ]
