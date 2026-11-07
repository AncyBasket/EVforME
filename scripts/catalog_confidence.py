"""Versioned, deterministic catalog data-quality scoring (policy v2).

The score is an ordinal coverage/quality index in [0, 1], not a calibrated
probability and not documentary certification. Non-empty fieldSources /
fieldSourceDates do NOT prove year, variant, market, or correctness.
A nil calculation field never counts as covered.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from lib.phev_manus_v76_validate import (  # noqa: E402
    validate_inherited_date,
    validate_source_dating,
)

POLICY_VERSION = 2
SCORE_LABEL = "ordinal_data_quality_coverage"

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
    # Provenance strings present — NOT documentary verification.
    "field_provenance_partial_unverified": 0.70,
    "field_provenance_full_unverified": 0.80,
    "homolog_derivation_declared": 0.70,
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
_HOMOLOG_RE = re.compile(
    r"dataDerivedFromSameHomologationYear|same[- ]homolog|derivazione omologativ|same MY homolog",
    re.I,
)
_GENERIC_URL_RE = re.compile(
    r"https?://[^\s;]+/(?:scheda-tecnica|gamma|models?)/[^\s;]*\.pdf",
    re.I,
)


def _source_year(source: str) -> int | None:
    match = _EEA_IT_YEAR_RE.search(source)
    if match:
        return int(match.group(1))
    for match in _YEAR_RE.finditer(source):
        year = int(match.group(1))
        tail = source[match.end() :]
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
    if any(
        token in text
        for token in (
            "oem",
            "listino",
            "configurator",
            "manufacturer",
            "tesla italia",
            "press",
            "newsroom",
            "preisliste",
            "envkv",
        )
    ):
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


def _field_value_present(row: dict[str, Any], key: str) -> bool:
    val = row.get(key)
    if val is None:
        return False
    if isinstance(val, str) and not val.strip():
        return False
    return True


def _extract_url(cite: str) -> str:
    m = re.search(r"https?://[^\s;]+", cite or "")
    return m.group(0) if m else ""


def _provenance_usable(
    *,
    row_year: int | None,
    cite: str,
    date: str | None,
) -> tuple[bool, str]:
    """Return whether provenance strings are usable as coverage (still unverified).

    Downgrades incompatible dates / live past-year / generic live PDFs using the
    same dating helpers as the PHEV data pipeline. Never upgrades to verified.
    """
    if not (cite or "").strip():
        return False, "missing_cite"
    if row_year is not None and date:
        inh = validate_inherited_date(
            field_source_date=date,
            document_date=date,
            row_year=int(row_year),
        )
        if not inh.ok:
            return False, inh.reason
    url = _extract_url(cite)
    if row_year is not None and url:
        syn_date = date or f"{int(row_year)}-06-15"
        dating = validate_source_dating(
            row_year=int(row_year),
            source_date=syn_date,
            url=url,
        )
        if dating.reason in {
            "source_date_incompatible",
            "live_page_past_year",
            "live_url_past_year",
            "archive_year_mismatch",
            "bad_source_date",
        }:
            return False, dating.reason
        if _GENERIC_URL_RE.search(url) and dating.reason == "live_url_past_year":
            return False, "live_url_past_year"
    return True, "provenance_string_present"


def assess_field_evidence(row: dict[str, Any]) -> dict[str, Any]:
    """Classify required calc fields: missing / provenance_unverified / verified.

    `verified` is never assigned by string presence or officialMatched alone.
    This policy does not invent retroactive documentary verification.
    """
    required = _required_fields(row)
    field_sources = row.get("fieldSources") if isinstance(row.get("fieldSources"), dict) else {}
    field_dates = row.get("fieldSourceDates") if isinstance(row.get("fieldSourceDates"), dict) else {}
    year = row.get("year")
    model_year = int(year) if isinstance(year, (int, float)) else None

    missing: list[str] = []
    unverified: list[str] = []
    verified: list[str] = []
    rejected_provenance: list[str] = []

    for key in required:
        cite = str(field_sources.get(key) or "")
        date = field_dates.get(key)
        date_s = str(date) if date else None
        if not _field_value_present(row, key):
            missing.append(key)
            continue
        usable, why = _provenance_usable(row_year=model_year, cite=cite, date=date_s)
        if not usable:
            missing.append(key)
            rejected_provenance.append(f"{key}:{why}")
            continue
        # Explicit verification marker only — never officialMatched / non-empty strings.
        # Current catalog has no per-field verified flag; keep empty by design.
        verified_marker = False
        if verified_marker:
            verified.append(key)
        else:
            unverified.append(key)

    return {
        "requiredCalculationFields": list(required),
        "missingFields": missing,
        "provenanceUnverifiedFields": unverified,
        "verifiedFields": verified,
        "rejectedProvenance": rejected_provenance,
        "fieldSourceCoveredFields": unverified + verified,  # value+usable cite
        "fieldSourceDatedFields": [
            k
            for k in (unverified + verified)
            if field_dates.get(k)
        ],
        "fieldSourceCoverage": (
            round(len(unverified + verified) / len(required), 3) if required else 0.0
        ),
    }


def assess_confidence(row: dict[str, Any]) -> tuple[float, dict[str, Any]]:
    """Return the policy score and its reproducible evidence record.

    Legacy confidenceScore values are ignored as inputs.
    """
    source = str(row.get("sourceName") or "")
    primary_text = source.split(";", 1)[0].lower()
    text = primary_text
    year = row.get("year")
    model_year = int(year) if isinstance(year, (int, float)) else None
    source_year = _source_year(source.split(";", 1)[0])
    sample_match = _SAMPLE_RE.search(source.split(";", 1)[0])
    sample_size = int(sample_match.group(1)) if sample_match else None
    provisional = "provvisorio" in text or "provisional" in text

    field_ev = assess_field_evidence(row)
    required = tuple(field_ev["requiredCalculationFields"])
    covered = field_ev["fieldSourceCoveredFields"]
    dated = field_ev["fieldSourceDatedFields"]
    missing = field_ev["missingFields"]

    year_relation = "unknown"
    if model_year is not None and source_year is not None:
        delta = model_year - source_year
        year_relation = (
            "same_year"
            if delta == 0
            else "source_one_year_old"
            if delta == 1
            else "source_older"
            if delta > 1
            else "source_future"
        )

    homolog = bool(_HOMOLOG_RE.search(source))

    if "pre-2010" in primary_text:
        reason = "pre_2010_unverified_estimate"
        variant_match = "not_available"
    elif "n=1" in primary_text and (
        "proxy" in primary_text or "variante sorella" in primary_text or "troppo basso" in primary_text
    ):
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
    elif (
        "nessun match" in primary_text
        or "no match" in primary_text
        or "stima" in primary_text
        or "estimate" in primary_text
    ):
        reason = "estimated_or_unmatched_it_data"
        variant_match = "no_reliable_match"
    elif homolog and required:
        reason = "homolog_derivation_declared"
        variant_match = "homolog_declared"
    elif required and len(covered) == len(required) and not missing:
        # Full provenance coverage — still unverified (no documentary cert).
        reason = "field_provenance_full_unverified"
        variant_match = "field_provenance_present_unverified"
    elif required and covered:
        reason = "field_provenance_partial_unverified"
        variant_match = "partly_field_provenance_unverified"
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
    elif "it-import" in primary_text:
        reason = "official_importer_wltp_source"
        variant_match = "model_level_source"
    elif "it-common" in primary_text:
        reason = "generic_local_reference"
        variant_match = "generic_market_reference"
    elif any(
        token in primary_text
        for token in (
            "oem",
            "listino",
            "configurator",
            "manufacturer",
            "tesla italia",
            "press",
            "newsroom",
            "preisliste",
            "envkv",
        )
    ):
        reason = "oem_or_official_list_price_source"
        variant_match = "record_level_source"
    else:
        reason = "unknown_or_legacy_source"
        variant_match = "unknown"

    # officialMatched must never promote to verified / top documentary tier.
    _ = row.get("officialMatched")

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
        "missingFields": missing,
        "provenanceUnverifiedFields": field_ev["provenanceUnverifiedFields"],
        "verifiedFields": field_ev["verifiedFields"],
        "rejectedProvenance": field_ev["rejectedProvenance"],
        "fieldSourceCoveredFields": covered,
        "fieldSourceDatedFields": dated,
        "fieldSourceCoverage": field_ev["fieldSourceCoverage"],
        "evidenceScope": "record_level" if not covered else "partly_field_level",
        "documentaryVerification": "none_invented",
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
