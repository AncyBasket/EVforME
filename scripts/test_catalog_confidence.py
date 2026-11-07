from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from catalog_confidence import POLICY_VERSION, apply_confidence, assess_confidence  # noqa: E402


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

    def test_dated_field_sources_and_exact_match_get_top_tier(self):
        row = {
            "sourceName": "OEM WLTP",
            "year": 2024,
            "powertrain": "ice",
            "officialMatched": True,
            "fieldSources": {"fuelConsumptionLPerKm": "https://oem.example/spec"},
            "fieldSourceDates": {"fuelConsumptionLPerKm": "2024-01-15"},
        }
        score, evidence = assess_confidence(row)
        self.assertEqual(score, 0.95)
        self.assertEqual(evidence["reasonCode"], "field_source_exact_match_and_dated")

    def test_phev_partial_field_provenance_does_not_get_full_coverage_score(self):
        row = {
            "sourceName": "OEM PHEV source",
            "year": 2024,
            "powertrain": "phev",
            "fieldSources": {"fuelConsumptionLPerKm": "https://oem.example/spec"},
            "fieldSourceDates": {"fuelConsumptionLPerKm": "2024-01-15"},
        }
        score, evidence = assess_confidence(row)
        self.assertEqual(score, 0.75)
        self.assertEqual(evidence["fieldSourceCoverage"], 0.5)
        self.assertEqual(evidence["reasonCode"], "field_source_partial")

    def test_official_consumption_source_is_not_penalized_by_maintenance_note(self):
        row = {
            "sourceName": "Tesla Italia model page + configurator (2026-10-26); WLTP/consumo/dims from https://www.tesla.com/it_it/model3; maintenancePerYear=stima catalogo (ultimo EEA IT non copre 2026)",
            "year": 2026,
            "powertrain": "ev",
        }
        score, evidence = assess_confidence(row)
        self.assertEqual(score, 0.90)
        self.assertEqual(evidence["reasonCode"], "oem_or_official_list_price_source")

    def test_score_does_not_depend_on_legacy_score_and_apply_is_idempotent(self):
        row = {"sourceName": "stima (pre-2010; dati consumi non da co2cars IT)", "year": 2007, "powertrain": "ice", "confidenceScore": 0.99}
        expected = assess_confidence(row)
        migrated = apply_confidence(copy.deepcopy(row))
        self.assertEqual(migrated["confidenceScoreLegacy"], 0.99)
        self.assertEqual((migrated["confidenceScore"], migrated["confidenceEvidence"]), expected)
        second = apply_confidence(copy.deepcopy(migrated))
        self.assertEqual(second["confidenceScore"], migrated["confidenceScore"])
        self.assertEqual(second["confidenceEvidence"], migrated["confidenceEvidence"])


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

    def test_seed_and_static_mirrors_are_identical_catalog_data(self):
        seed = json.loads((ROOT / "EVforME?" / "Data" / "vehicles.seed.quality.json").read_text(encoding="utf-8"))
        min_api = json.loads((ROOT / "api" / "static" / "vehicles.catalog.min.json").read_text(encoding="utf-8"))
        pretty_api = json.loads((ROOT / "api" / "static" / "vehicles.catalog.json").read_text(encoding="utf-8"))
        self.assertEqual(seed, min_api)
        self.assertEqual(seed, pretty_api)
        app_manifest = json.loads((ROOT / "EVforME?" / "Data" / "catalog_cdn.json").read_text(encoding="utf-8"))
        api_manifest = json.loads((ROOT / "api" / "static" / "catalog_cdn.json").read_text(encoding="utf-8"))
        seed_bytes = (ROOT / "EVforME?" / "Data" / "vehicles.seed.quality.json").stat().st_size
        self.assertEqual(app_manifest["seedVersion"], api_manifest["seedVersion"])
        self.assertEqual(app_manifest["rows"], len(seed))
        self.assertEqual(api_manifest["rows"], len(seed))
        self.assertEqual(app_manifest["bytes"], seed_bytes)
        self.assertEqual(api_manifest["bytes"], seed_bytes)


if __name__ == "__main__":
    unittest.main(verbosity=2)
