from __future__ import annotations

import os
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent))
import main  # noqa: E402
import database  # noqa: E402


ADMIN_TOKEN = "test-token-with-at-least-thirty-two-characters"


class APIProtectionTests(unittest.TestCase):
    def setUp(self) -> None:
        with main._rate_lock:
            main._rate_buckets.clear()
        self.client = TestClient(main.app)

    def test_catalog_export_includes_versioned_confidence_evidence(self) -> None:
        evidence = {"policyVersion": 1, "reasonCode": "unmatched_eu_version", "scoreKind": "ordinal_data_quality"}
        with tempfile.TemporaryDirectory(prefix="evforme-confidence-api-") as temp_dir:
            root = Path(temp_dir)
            seed = root / "vehicles.seed.quality.json"
            seed.write_text(json.dumps([{
                "id": "test-car", "brand": "Test", "model": "Car", "year": 2025,
                "powertrain": "ev", "confidenceScore": 0.4,
                "confidenceScoreLegacy": 0.95, "confidencePolicyVersion": 1,
                "confidenceEvidence": evidence,
            }]), encoding="utf-8")
            (root / "catalog_cdn.json").write_text(json.dumps({"seedVersion": 77, "rows": 1}), encoding="utf-8")
            with (
                patch.object(database, "DB_PATH", root / "catalog.sqlite3"),
                patch.object(database, "STATE_PATH", root / "catalog_state.json"),
                patch.object(database, "SEED_PREFERRED", [seed]),
            ):
                database.refresh_from_seed()
                response = self.client.get("/catalog/export")
        self.assertEqual(response.status_code, 200)
        row = response.json()[0]
        self.assertEqual(row["confidenceScore"], 0.4)
        self.assertEqual(row["confidenceScoreLegacy"], 0.95)
        self.assertEqual(row["confidencePolicyVersion"], 1)
        self.assertEqual(row["confidenceEvidence"], evidence)

    def test_private_reads_are_disabled_without_admin_token(self) -> None:
        with patch.dict(os.environ, {"EVFORME_ADMIN_TOKEN": ""}, clear=False):
            self.assertEqual(self.client.get("/leads").status_code, 503)
            self.assertEqual(self.client.get("/events").status_code, 503)
            self.assertEqual(self.client.post("/catalog/sync").status_code, 503)
            self.assertEqual(self.client.post("/energy/sync").status_code, 503)

    def test_private_reads_require_valid_bearer_token(self) -> None:
        with patch.dict(os.environ, {"EVFORME_ADMIN_TOKEN": ADMIN_TOKEN}, clear=False):
            self.assertEqual(self.client.get("/leads").status_code, 401)
            with patch.object(main, "purge_expired_data"), patch.object(main, "list_leads", return_value=[]):
                response = self.client.get("/leads", headers={"Authorization": f"Bearer {ADMIN_TOKEN}"})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), {"items": []})

    def test_lead_requires_explicit_consent_and_valid_email(self) -> None:
        with patch.object(main, "purge_expired_data"), patch.object(main, "insert_lead") as insert:
            denied = self.client.post("/leads", json={"email": "a@example.com", "consent": False})
            invalid = self.client.post("/leads", json={"email": "not-an-email", "consent": True})
            accepted = self.client.post("/leads", json={"name": " Ada ", "email": "ada@example.com", "city": "Roma", "consent": True})
        self.assertEqual(denied.status_code, 422)
        self.assertEqual(invalid.status_code, 422)
        self.assertEqual(accepted.status_code, 200)
        insert.assert_called_once_with({"name": "Ada", "email": "ada@example.com", "city": "Roma", "consent": True})

    def test_analytics_rejects_personal_fields_and_accepts_bounded_scalars(self) -> None:
        with patch.object(main, "purge_expired_data"), patch.object(main, "insert_event") as insert:
            rejected = self.client.post("/events", json={"event": "open", "params": {"email": "private@example.com"}})
            accepted = self.client.post("/events", json={"event": "simulation", "params": {"scenario": "realistic"}, "timestamp": 123.0})
        self.assertEqual(rejected.status_code, 422)
        self.assertEqual(accepted.status_code, 200)
        insert.assert_called_once_with("simulation", {"scenario": "realistic"}, 123.0)

    def test_lead_rate_limit_is_applied(self) -> None:
        body = {"email": "ada@example.com", "consent": True}
        with patch.object(main, "purge_expired_data"), patch.object(main, "insert_lead"):
            statuses = [self.client.post("/leads", json=body).status_code for _ in range(6)]
        self.assertEqual(statuses[:5], [200] * 5)
        self.assertEqual(statuses[5], 429)

    def test_oversized_lead_body_is_rejected(self) -> None:
        body = {"email": "ada@example.com", "consent": True, "extra": "x" * 17_000}
        response = self.client.post("/leads", json=body)
        self.assertEqual(response.status_code, 413)


if __name__ == "__main__":
    unittest.main()
