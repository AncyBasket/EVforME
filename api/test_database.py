from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import database  # noqa: E402


class DatabaseStateTests(unittest.TestCase):
    def test_seed_refresh_tracks_manifest_and_retention_purges_old_data(self) -> None:
        with tempfile.TemporaryDirectory(prefix="evforme-api-test-") as temp_dir:
            root = Path(temp_dir)
            seed_path = root / "vehicles.seed.quality.json"
            manifest_path = root / "catalog_cdn.json"
            state_path = root / "catalog_state.json"
            db_path = root / "catalog.sqlite3"
            seed_path.write_text(
                json.dumps([{
                    "id": "test-car", "brand": "Test", "model": "Car", "year": 2026,
                    "powertrain": "ev", "confidenceScore": 0.4,
                    "confidenceScoreLegacy": 0.95, "confidencePolicyVersion": 1,
                    "confidenceEvidence": {"policyVersion": 1, "reasonCode": "unmatched_eu_version"},
                }]),
                encoding="utf-8",
            )
            manifest_path.write_text(json.dumps({"seedVersion": 75, "rows": 1}), encoding="utf-8")

            with (
                patch.object(database, "DB_PATH", db_path),
                patch.object(database, "STATE_PATH", state_path),
                patch.object(database, "SEED_PREFERRED", [seed_path]),
            ):
                self.assertFalse(database.seed_is_current())
                state = database.refresh_from_seed()
                self.assertEqual(state["seedVersion"], 75)
                self.assertTrue(database.seed_is_current())
                with database.get_conn() as conn:
                    stored = conn.execute("SELECT * FROM vehicles WHERE id = ?", ("test-car",)).fetchone()
                self.assertEqual(stored["confidence_score"], 0.4)
                self.assertEqual(stored["confidence_score_legacy"], 0.95)
                self.assertEqual(stored["confidence_policy_version"], 1)
                self.assertEqual(
                    json.loads(stored["confidence_evidence_json"]),
                    {"policyVersion": 1, "reasonCode": "unmatched_eu_version"},
                )

                manifest_path.write_text(json.dumps({"seedVersion": 76, "rows": 1}), encoding="utf-8")
                self.assertFalse(database.seed_is_current())

                database.insert_event("simulation", {"scenario": "test"}, None)
                database.insert_lead({"name": "Test", "email": "test@example.com", "consent": True})
                old = "2000-01-01T00:00:00+00:00"
                with database.get_conn() as conn:
                    conn.execute("UPDATE growth_events SET received_at = ?", (old,))
                    conn.execute("UPDATE leads SET received_at = ?", (old,))

                removed = database.purge_expired_data(180)
                self.assertEqual(removed, {"events": 1, "leads": 1})
                self.assertEqual(database.list_events(), [])
                self.assertEqual(database.list_leads(), [])


if __name__ == "__main__":
    unittest.main()
