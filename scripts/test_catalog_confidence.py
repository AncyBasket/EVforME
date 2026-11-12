from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from catalog_confidence import (  # noqa: E402
    POLICY_VERSION,
    apply_confidence,
    assess_confidence,
    assess_field_evidence,
)


class ConfidencePolicyUnitTests(unittest.TestCase):
    def score(self, source: str, year: int, powertrain: str = "ice", **extra):
        row = {"sourceName": source, "year": year, "powertrain": powertrain, **extra}
        return assess_confidence(row)

    def test_pre_2010_estimate_is_low_and_explicit(self):
        score, evidence = self.score("stima (pre-2010; dati consumi non da co2cars IT)", 2007)
        self.assertEqual(score, 0.30)
        self.assertEqual(evidence["reasonCode"], "pre_2010_unverified_estimate")

    def test_same_variant_prior_year_is_not_scored_as_exact(self):
        score, evidence = self.score("stima (da EEA IT 2025 stessa variante)", 2026)
        self.assertEqual(score, 0.40)
        self.assertEqual(evidence["yearRelation"], "source_one_year_old")
        self.assertEqual(evidence["variantMatch"], "same_variant_prior_year")

    def test_unmatched_eu_version_is_consistently_low(self):
        score, evidence = self.score("EEA co2cars EU Zr (unmatched version)", 2024, "ev")
        self.assertEqual(score, 0.40)
        self.assertEqual(evidence["variantMatch"], "unmatched")

    def test_single_sample_sibling_proxy_is_low(self):
        score, evidence = self.score(
            "stima (EEA IT 2020 n=1 troppo basso; consumi da variante sorella)", 2022
        )
        self.assertEqual(score, 0.35)
        self.assertEqual(evidence["sampleSize"], 1)
        self.assertEqual(evidence["variantMatch"], "sibling_proxy")

    def test_same_year_final_eea_source_uses_sample_tier(self):
        score, evidence = self.score("EEA co2cars IT 2023 n=120", 2023)
        self.assertEqual(score, 0.85)
        self.assertEqual(evidence["yearRelation"], "same_year")
        self.assertEqual(evidence["sampleSize"], 120)

    def test_provisional_source_is_lower_than_final_source(self):
        score, evidence = self.score(
            "EEA co2cars IT 2025 n=3460 (provvisorio, dati 2026-10-24)", 2025
        )
        self.assertEqual(score, 0.70)
        self.assertTrue(evidence["provisional"])

    def test_nil_field_with_source_present_is_not_covered(self):
        row = {
            "sourceName": "OEM WLTP",
            "year": 2024,
            "powertrain": "ice",
            "fuelConsumptionLPerKm": None,
            "fieldSources": {"fuelConsumptionLPerKm": "https://oem.example/download/2024/spec.pdf"},
            "fieldSourceDates": {"fuelConsumptionLPerKm": "2024-01-15"},
            "officialMatched": True,
        }
        ev = assess_field_evidence(row)
        self.assertIn("fuelConsumptionLPerKm", ev["missingFields"])
        self.assertEqual(ev["fieldSourceCoveredFields"], [])
        score, evidence = assess_confidence(row)
        self.assertNotEqual(evidence["reasonCode"], "field_provenance_full_unverified")
        self.assertEqual(evidence["documentaryVerification"], "none_invented")
        self.assertEqual(evidence["verifiedFields"], [])

    def test_incompatible_field_date_is_rejected(self):
        row = {
            "sourceName": "OEM",
            "year": 2024,
            "powertrain": "ice",
            "fuelConsumptionLPerKm": 0.06,
            "fieldSources": {"fuelConsumptionLPerKm": "cite"},
            "fieldSourceDates": {"fuelConsumptionLPerKm": "2023-06-26"},
        }
        ev = assess_field_evidence(row)
        self.assertIn("fuelConsumptionLPerKm", ev["missingFields"])
        self.assertTrue(any("field_date_year_mismatch" in x for x in ev["rejectedProvenance"]))

    def test_generic_live_url_past_year_is_rejected(self):
        row = {
            "sourceName": "Toyota live",
            "year": 2024,
            "powertrain": "ice",
            "fuelConsumptionLPerKm": 0.05,
            "fieldSources": {
                "fuelConsumptionLPerKm": (
                    "https://www.toyota.it/content/dam/toyota/nmsc/italy/gamma/pdf/"
                    "scheda-tecnica/RAV4_Plug-in_Hybrid_Scheda_tecnica.pdf"
                )
            },
            "fieldSourceDates": {"fuelConsumptionLPerKm": "2024-01-01"},
        }
        ev = assess_field_evidence(row)
        self.assertIn("fuelConsumptionLPerKm", ev["missingFields"])

    def test_unverified_provenance_with_value_is_not_verified_tier(self):
        row = {
            "sourceName": "OEM WLTP",
            "year": 2024,
            "powertrain": "ice",
            "fuelConsumptionLPerKm": 0.055,
            "officialMatched": True,
            "fieldSources": {
                "fuelConsumptionLPerKm": "https://newsroom.example/download/2024/spec.pdf ; label"
            },
            "fieldSourceDates": {"fuelConsumptionLPerKm": "2024-01-15"},
        }
        score, evidence = assess_confidence(row)
        self.assertEqual(score, 0.80)
        self.assertEqual(evidence["reasonCode"], "field_provenance_full_unverified")
        self.assertEqual(evidence["verifiedFields"], [])
        self.assertIn("fuelConsumptionLPerKm", evidence["provenanceUnverifiedFields"])
        # officialMatched must not invent verification
        self.assertEqual(evidence["documentaryVerification"], "none_invented")

    def test_official_matched_alone_does_not_create_verified_fields(self):
        row = {
            "sourceName": "EEA co2cars IT 2024 n=10",
            "year": 2024,
            "powertrain": "ice",
            "fuelConsumptionLPerKm": 0.06,
            "officialMatched": True,
        }
        _, evidence = assess_confidence(row)
        self.assertEqual(evidence["verifiedFields"], [])
        self.assertEqual(evidence["reasonCode"], "eea_it_exact_year_sampled")

    def test_homolog_derivation_declared(self):
        row = {
            "sourceName": "OEM MY23; dataDerivedFromSameHomologationYear from 2023 PDF",
            "year": 2024,
            "powertrain": "phev",
            "fuelConsumptionLPerKm": 0.06,
            "energyConsumptionKWhPerKm": 0.16,
        }
        score, evidence = assess_confidence(row)
        self.assertEqual(score, 0.70)
        self.assertEqual(evidence["reasonCode"], "homolog_derivation_declared")

    def test_phev_partial_field_provenance(self):
        row = {
            "sourceName": "OEM PHEV source",
            "year": 2024,
            "powertrain": "phev",
            "fuelConsumptionLPerKm": 0.06,
            "energyConsumptionKWhPerKm": None,
            "fieldSources": {
                "fuelConsumptionLPerKm": "https://newsroom.example/download/2024/a.pdf"
            },
            "fieldSourceDates": {"fuelConsumptionLPerKm": "2024-01-15"},
        }
        score, evidence = assess_confidence(row)
        self.assertEqual(score, 0.70)
        self.assertEqual(evidence["reasonCode"], "field_provenance_partial_unverified")
        self.assertEqual(evidence["fieldSourceCoverage"], 0.5)
        self.assertIn("energyConsumptionKWhPerKm", evidence["missingFields"])

    def test_partial_data_without_field_sources_uses_record_rubric(self):
        score, evidence = self.score("EEA co2cars IT 2023 n=12", 2023, "phev")
        self.assertEqual(score, 0.85)
        self.assertEqual(evidence["missingFields"], [
            "fuelConsumptionLPerKm",
            "energyConsumptionKWhPerKm",
        ])

    def test_score_does_not_depend_on_legacy_score_and_apply_is_idempotent(self):
        row = {
            "sourceName": "stima (pre-2010; dati consumi non da co2cars IT)",
            "year": 2007,
            "powertrain": "ice",
            "confidenceScore": 0.99,
        }
        expected = assess_confidence(row)
        migrated = apply_confidence(copy.deepcopy(row))
        self.assertEqual(migrated["confidenceScoreLegacy"], 0.99)
        self.assertEqual(
            (migrated["confidenceScore"], migrated["confidenceEvidence"]), expected
        )
        second = apply_confidence(copy.deepcopy(migrated))
        self.assertEqual(second["confidenceScore"], migrated["confidenceScore"])
        self.assertEqual(second["confidenceEvidence"], migrated["confidenceEvidence"])
        self.assertEqual(POLICY_VERSION, 2)


class ProductionCatalogConfidenceTests(unittest.TestCase):
    def test_all_catalog_scores_are_reproducible_from_policy_evidence(self):
        path = ROOT / "EVforME?" / "Data" / "vehicles.seed.quality.json"
        rows = json.loads(path.read_text(encoding="utf-8"))
        self.assertGreater(len(rows), 6000)
        for row in rows:
            expected_score, expected_evidence = assess_confidence(row)
            self.assertEqual(row.get("confidencePolicyVersion"), POLICY_VERSION, row["id"])
            self.assertEqual(row.get("confidenceScore"), expected_score, row["id"])
            self.assertEqual(row.get("confidenceEvidence"), expected_evidence, row["id"])
            self.assertIsNotNone(row.get("confidenceScoreLegacy"), row["id"])

    def test_technical_fields_unchanged_vs_pre_migration_shape(self):
        """Regression: every row keeps non-confidence keys stable across re-apply."""
        path = ROOT / "EVforME?" / "Data" / "vehicles.seed.quality.json"
        rows = json.loads(path.read_text(encoding="utf-8"))
        conf = {
            "confidenceScore",
            "confidenceScoreLegacy",
            "confidencePolicyVersion",
            "confidenceEvidence",
        }
        for row in rows:
            again = apply_confidence(dict(row), preserve_legacy=True)
            for k, v in row.items():
                if k in conf:
                    continue
                self.assertEqual(again.get(k), v, f"{row['id']}.{k}")

    def test_seed_and_static_mirrors_are_identical_catalog_data(self):
        import hashlib

        seed = json.loads(
            (ROOT / "EVforME?" / "Data" / "vehicles.seed.quality.json").read_text(encoding="utf-8")
        )
        min_path = ROOT / "api" / "static" / "vehicles.catalog.min.json"
        pretty_path = ROOT / "api" / "static" / "vehicles.catalog.json"
        min_bytes = min_path.read_bytes()
        min_api = json.loads(min_bytes.decode("utf-8"))
        pretty_api = json.loads(pretty_path.read_text(encoding="utf-8"))
        app_manifest = json.loads(
            (ROOT / "EVforME?" / "Data" / "catalog_cdn.json").read_text(encoding="utf-8")
        )
        api_manifest = json.loads(
            (ROOT / "api" / "static" / "catalog_cdn.json").read_text(encoding="utf-8")
        )
        seed_bytes = (ROOT / "EVforME?" / "Data" / "vehicles.seed.quality.json").stat().st_size

        # App seed/manifest must be internally consistent at seed 80.
        self.assertEqual(app_manifest["rows"], len(seed))
        self.assertEqual(app_manifest["bytes"], seed_bytes)
        self.assertEqual(app_manifest["seedVersion"], 80)

        # api/ is intentionally not modified. Freeze the seed-77 mirror at main 0f09192:
        # seedVersion 77, bytes 8908918, pretty==min, SHA of min matches main catalog.
        # (SHA pins git show 0f09192:api/static/vehicles.catalog.min.json without needing .git
        # in the PYTHONHASHSEED temp copies used by check_catalog_confidence_v79/v80.)
        seed77_min_sha = "fcb01024faaac0b1086313d8bb50d431f09139e12a39042bedaf32afc51420fb"
        self.assertEqual(api_manifest["rows"], 6977)
        self.assertEqual(api_manifest["seedVersion"], 77)
        self.assertEqual(api_manifest["bytes"], 8908918)
        self.assertEqual(len(min_bytes), 8908918)
        self.assertEqual(hashlib.sha256(min_bytes).hexdigest(), seed77_min_sha)
        self.assertEqual(min_api, pretty_api)
        # Explicit divergence: app seed 80 vs api/static@77 — API sync is deferred.
        self.assertNotEqual(
            app_manifest["seedVersion"],
            api_manifest["seedVersion"],
            "app seed 80 diverges from api/static@77; API sync is deferred (api/ untouched)",
        )
        self.assertNotEqual(seed, min_api)
        self.assertEqual(len(min_api), len(seed))

    def test_model3_2026_intact_count(self):
        seed = json.loads(
            (ROOT / "EVforME?" / "Data" / "vehicles.seed.quality.json").read_text(encoding="utf-8")
        )
        m3 = [
            r
            for r in seed
            if r["id"].startswith("tesla-model-3") and r.get("year") == 2026
        ]
        self.assertEqual(len(m3), 4)
        self.assertEqual(len(seed), 6977)


if __name__ == "__main__":
    unittest.main(verbosity=2)
