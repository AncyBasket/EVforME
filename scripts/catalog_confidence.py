"""Versioned, deterministic catalog data-quality scoring.

The score is an ordinal data-quality index in [0, 1], not a calibrated probability.
It is derived only from source/evidence fields; the legacy score is never an input.
"""
from __future__ import annotations

import re
from typing import Any

POLICY_VERSION = 1
SCORE_LABEL = "ordinal_data_quality"

# Fixed rubric values; changing these requires a new POLICY_VERSION and tests.
SCORES = {
    "pre_2010_unverified_estimate": 0.30,
    "weak_single_sample_proxy": 0.35,
    "stale_or_uncovered_estimate": 0.35,
    "estimated_or_unmatched_it_data": 0.40,
    "unmatched_eu_version": 0.40,
    "oem_label_with_unmatched_measurement": 0.75,
    "eea_it_exact_year_provisional": 0.70,
    "eea_it_exact_year_low_sample": 0.65,
    "eea_it_exact_year_sampled": 0.85,
    "eea_it_exact_year_unsized": 0.75,
    "eea_it_one_year_old": 0.45,
    "eea_it_older_year": 0.35,
    "eea_it_future_year": 0.55,
    "eea_wltp_record_level": 0.80,
    "eea_nedc_older_cycle": 0.65,
    "epa_official_source": 0.80,
    "oem_or_official_list_price_source": 0.90,
    "official_importer_wltp_source": 0.80,
    "generic_local_reference": 0.50,
    "field_source_partial": 0.75,
    "field_source_documented": 0.90,
    "field_source_exact_match_and_dated": 0.95,
    "unknown_or_legacy_source": 0.35,
}

_REQUIRED_FIELDS = {
    "ice": ("fuelConsumptionLPerKm",),
    "hev": ("fuelConsumptionLPerKm",),
    "ev": ("energyConsumptionKWhPerKm",),
    "phev": ("fuelConsumptionLPerKm", "energyConsumptionKWhPerKm"),
}
_YEAR_RE = re.compile(r"\b(20\d{2})\b")
_EEA_IT_YEAR_RE = re.compile(r"EEA(?:\s+co2cars)?\s+IT\s+(20\d{2})", re.IGNORECASE)
_SAMPLE_RE = re.compile(r"\bn\s*=\s*(\d+)\b", re.IGNORECASE)


def _source_year(source: str) -> int | None:
    match = _EEA_IT_YEAR_RE.search(source)
    if match:
        return int(match.group(1))
    # OEM/product sources sometimes state an explicit model year; exclude ISO dates.
    for match in _YEAR_RE.finditer(source):
        year = int(match.group(1))
        tail = source[match.end():]
        if not re.match(r"-\d{2}-\d{2}", tail):
            return year
    return None


def _source_class(source: str) -> str:
    text = source.split(";", 1)[0].lower()
    if "eea co2cars eu" in text:
        return "eea_eu"
    if "eea co2cars it" in text or "eea it" in text:
        return "eea_it"
    if "eea-nedc" in text or "eea nedc" in text:
        return "eea_nedc"
    if "eea-wltp" in text or "eea wltp" in text or "co2cars" in text:
        return "eea_wltp_or_catalog"
    if "epa-fueleconomy" in text or "epa fuel economy" in text:
        return "epa"
    if any(token in text for token in ("oem", "listino", "configurator", "manufacturer", "tesla italia", "press", "newsroom", "preisliste", "envkv")):
        return "oem_or_official_price"
    if "it-common" in text:
        return "local_reference"
    if "it-import" in text:
        return "official_importer"
    if "stima" in text or "estimate" in text:
        return "estimate"
    if "nhtsa" in text:
        return "nhtsa_normalization"
    if text:
        return "other_named_source"
    return "unknown"


def _required_fields(row: dict[str, Any]) -> tuple[str, ...]:
    return _REQUIRED_FIELDS.get(str(row.get("powertrain", "")).lower(), ())


def assess_confidence(row: dict[str, Any]) -> tuple[float, dict[str, Any]]:
    """Return the policy score and its reproducible evidence record.

    `sourceName` is legacy record-level provenance; the evidence explicitly states
    when it is not per-field. Existing confidenceScore values are ignored.
    """
    source = str(row.get("sourceName") or "")
    # Semicolon-separated notes can describe unrelated estimates (e.g. maintenance).
    # The first segment identifies the source used for the vehicle's main data.
    primary_text = source.split(";", 1)[0].lower()
    text = primary_text
    year = row.get("year")
    model_year = int(year) if isinstance(year, (int, float)) else None
    source_year = _source_year(source.split(";", 1)[0])
    sample_match = _SAMPLE_RE.search(source.split(";", 1)[0])
    sample_size = int(sample_match.group(1)) if sample_match else None
    provisional = "provvisorio" in text or "provisional" in text
    field_sources = row.get("fieldSources") if isinstance(row.get("fieldSources"), dict) else {}
    field_dates = row.get("fieldSourceDates") if isinstance(row.get("fieldSourceDates"), dict) else {}
    required = _required_fields(row)
    field_covered = [key for key in required if field_sources.get(key)]
    field_dated = [key for key in field_covered if field_dates.get(key)]
    field_source_coverage = len(field_covered) / len(required) if required else 0.0
    year_relation = "unknown"
    if model_year is not None and source_year is not None:
        delta = model_year - source_year
        year_relation = "same_year" if delta == 0 else "source_one_year_old" if delta == 1 else "source_older" if delta > 1 else "source_future"

    if "pre-2010" in primary_text:
        reason = "pre_2010_unverified_estimate"
        variant_match = "not_available"
    elif "n=1" in primary_text and ("proxy" in primary_text or "variante sorella" in primary_text or "troppo basso" in primary_text):
        reason = "weak_single_sample_proxy"
        variant_match = "sibling_proxy"
    elif "eea co2cars eu" in text and "official oem label" in text:
        reason = "oem_label_with_unmatched_measurement"
        variant_match = "oem_label_measurement_unmatched"
    elif "unmatched version" in text:
        reason = "unmatched_eu_version"
        variant_match = "unmatched"
    elif "stessa variante" in primary_text or "same variant" in primary_text:
        reason = "estimated_or_unmatched_it_data"
        variant_match = "same_variant_prior_year"
    elif "non copre" in primary_text or "does not cover" in primary_text:
        reason = "stale_or_uncovered_estimate"
        variant_match = "year_not_covered"
    elif "ripristinata" in primary_text or "restored" in primary_text:
        reason = "stale_or_uncovered_estimate"
        variant_match = "restored_without_reliable_match"
    elif "nessun match" in primary_text or "no match" in primary_text or "stima" in primary_text or "estimate" in primary_text:
        reason = "estimated_or_unmatched_it_data"
        variant_match = "no_reliable_match"
    elif required and len(field_dated) == len(required) and row.get("officialMatched") is True:
        reason = "field_source_exact_match_and_dated"
        variant_match = "official_exact_match"
    elif required and len(field_covered) == len(required):
        reason = "field_source_documented"
        variant_match = "field_source_present"
    elif required and field_covered:
        reason = "field_source_partial"
        variant_match = "partly_field_sourced"
    elif "eea co2cars eu" in text:
        reason = "unmatched_eu_version"
        variant_match = "unmatched"
    elif "eea co2cars it" in text or "eea it" in text:
        if year_relation == "same_year":
            if provisional:
                reason = "eea_it_exact_year_provisional"
            elif sample_size is not None and sample_size < 5:
                reason = "eea_it_exact_year_low_sample"
            elif sample_size is not None:
                reason = "eea_it_exact_year_sampled"
            else:
                reason = "eea_it_exact_year_unsized"
            variant_match = "model_year_match"
        elif year_relation == "source_one_year_old":
            reason = "eea_it_one_year_old"
            variant_match = "year_proxy"
        elif year_relation == "source_older":
            reason = "eea_it_older_year"
            variant_match = "stale_source"
        elif year_relation == "source_future":
            reason = "eea_it_future_year"
            variant_match = "year_mismatch"
        else:
            reason = "eea_it_exact_year_unsized"
            variant_match = "model_year_unverified"
    elif "eea-nedc" in text or "eea nedc" in text:
        reason = "eea_nedc_older_cycle"
        variant_match = "record_level_source"
    elif "eea-wltp" in text or "eea wltp" in text:
        reason = "eea_wltp_record_level"
        variant_match = "record_level_source"
    elif "epa-fueleconomy" in text or "epa fuel economy" in text:
        reason = "epa_official_source"
        variant_match = "market_source"
    elif any(token in primary_text for token in ("it-import",)):
        reason = "official_importer_wltp_source"
        variant_match = "model_level_source"
    elif "it-common" in primary_text:
        reason = "generic_local_reference"
        variant_match = "generic_market_reference"
    elif any(token in primary_text for token in ("oem", "listino", "configurator", "manufacturer", "tesla italia", "press", "newsroom", "preisliste", "envkv")):
        reason = "oem_or_official_list_price_source"
        variant_match = "record_level_source"
    else:
        reason = "unknown_or_legacy_source"
        variant_match = "unknown"

    score = SCORES[reason]
    evidence = {
        "policyVersion": POLICY_VERSION,
        "scoreKind": SCORE_LABEL,
        "reasonCode": reason,
        "sourceClass": _source_class(source),
        "sourceYear": source_year,
        "modelYear": model_year,
        "yearRelation": year_relation,
        "variantMatch": variant_match,
        "sampleSize": sample_size,
        "provisional": provisional,
        "requiredCalculationFields": list(required),
        "fieldSourceCoveredFields": field_covered,
        "fieldSourceDatedFields": field_dated,
        "fieldSourceCoverage": round(field_source_coverage, 3),
        "evidenceScope": "record_level" if not field_covered else "partly_field_level",
    }
    return score, evidence


def apply_confidence(row: dict[str, Any], *, preserve_legacy: bool = True) -> dict[str, Any]:
    """Apply current policy in-place and return row; safe to call repeatedly."""
    if preserve_legacy and "confidenceScoreLegacy" not in row and row.get("confidenceScore") is not None:
        row["confidenceScoreLegacy"] = row.get("confidenceScore")
    score, evidence = assess_confidence(row)
    row["confidenceScore"] = score
    row["confidencePolicyVersion"] = POLICY_VERSION
    row["confidenceEvidence"] = evidence
    return row
