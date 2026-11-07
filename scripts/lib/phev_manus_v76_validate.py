#!/usr/bin/env python3
"""Shared validation for Manus PHEV v76 selective recovery.

Used by check script on both fixtures and real seed rows / downloaded artifacts.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

PURE_ENERGY_LABEL = re.compile(
    r"solo elettrico|charge[- ]?depleting|\(CD(?:,|\s|\)|/)|"
    r"bei vollständig geladener|batteria carica|batterie chargée|"
    r"pure electric|consumo elettrico puro|rein elektrischem|"
    r"geladenen batterie|/ CD\b",
    re.I,
)

EAER_CITY_ONLY = re.compile(
    r"\bEAER\b.*\bCity\b|\bCity\b.*\bEAER\b|autonomia\s+city|reichweite\s+city",
    re.I,
)
EAER_COMBINED = re.compile(
    r"combinat|combined|gesamt|WLTP(?!\s*City)|EAER(?!\s*City)",
    re.I,
)


@dataclass(frozen=True)
class Verdict:
    ok: bool
    reason: str


def missing_calc_fields(row: dict[str, Any]) -> list[str]:
    miss: list[str] = []
    cs = row.get("fuelConsumptionLPerKm")
    if cs is None or float(cs) * 100 < 3.0:
        miss.append("fuelConsumptionLPerKm")
    e = row.get("energyConsumptionKWhPerKm")
    if e is None or row.get("energyIsWeighted") is True:
        miss.append("energyConsumptionKWhPerKm")
    if row.get("wltpRangeKm") is None:
        miss.append("wltpRangeKm")
    if row.get("batteryKWh") is None:
        miss.append("batteryKWh")
    return miss


def has_pure_energy_label(cite: str) -> bool:
    return bool(PURE_ENERGY_LABEL.search(cite or ""))


def inspect_download(path: Path | str, *, claimed_ext: str | None = None) -> Verdict:
    """Validate acquired source bytes (format), not HTTP status alone."""
    p = Path(path)
    if not p.is_file():
        return Verdict(False, "download_missing")
    raw = p.read_bytes()
    if not raw:
        return Verdict(False, "download_empty")
    head = raw[:16]
    lower = raw[:200].lower()
    is_pdf = head.startswith(b"%PDF")
    is_html = lower.lstrip().startswith(b"<!doctype html") or lower.lstrip().startswith(
        b"<html"
    )
    ext = (claimed_ext or p.suffix).lower()
    if ext in {".pdf"} and is_html:
        return Verdict(False, "fake_pdf_html")
    if ext in {".pdf"} and not is_pdf:
        return Verdict(False, "not_pdf")
    if is_html and b"listino" in lower and b"2026" in lower and b"2022" not in raw[:5000]:
        # generic live listino page masquerading as historical source
        return Verdict(False, "generic_redirect_or_live_listino")
    if is_pdf or is_html or ext in {".html", ".htm", ".txt"}:
        return Verdict(True, "ok_format")
    return Verdict(False, "unknown_format")


def validate_source_dating(
    *,
    row_year: int,
    source_date: str | None,
    url: str,
    current_calendar_year: int = 2026,
) -> Verdict:
    """Official dating rules for field import."""
    url_l = (url or "").lower()
    if not url_l:
        return Verdict(False, "missing_url")
    if "archive.org" in url_l or "web.archive.org" in url_l:
        # require snapshot year in path when present
        m = re.search(r"/web/(\d{4})\d{10}/", url_l)
        if m and int(m.group(1)) != int(row_year):
            return Verdict(False, "archive_year_mismatch")
        return Verdict(True, "ok_archive")
    if not source_date or len(source_date) < 4:
        return Verdict(False, "missing_source_date")
    try:
        doc_year = int(source_date[:4])
    except ValueError:
        return Verdict(False, "bad_source_date")
    if doc_year != int(row_year):
        return Verdict(False, "source_date_incompatible")
    path = urlparse(url).path.lower()
    is_pdf_url = path.endswith(".pdf") or ".pdf" in path
    # Live HTML pages (press/newsroom article pages) only admissible for current calendar year.
    if int(row_year) < int(current_calendar_year) and not is_pdf_url:
        if "press." in url_l or "/article/" in path or path.endswith("/") or not path.split("/")[-1]:
            return Verdict(False, "live_page_past_year")
    # Live unversioned generic PDF URLs for past years are not proof by themselves.
    unversioned = not re.search(
        rf"{row_year}|my{str(row_year)[-2:]}|my-{str(row_year)[-2:]}", path
    )
    if (
        int(row_year) < int(current_calendar_year)
        and is_pdf_url
        and unversioned
        and "download/" not in path
        and "asset." not in path
    ):
        return Verdict(False, "live_url_past_year")
    return Verdict(True, "ok_dating")


def validate_inherited_date(
    *,
    field_source_date: str | None,
    document_date: str | None,
    row_year: int,
) -> Verdict:
    if not field_source_date:
        return Verdict(False, "missing_field_source_date")
    if document_date and field_source_date != document_date:
        return Verdict(False, "inherited_incompatible_date")
    if int(field_source_date[:4]) != int(row_year):
        return Verdict(False, "field_date_year_mismatch")
    return Verdict(True, "ok_field_date")


def validate_range_label(label: str, chosen_km: float | int | None) -> Verdict:
    if chosen_km is None:
        return Verdict(False, "range_nil")
    text = label or ""
    if EAER_CITY_ONLY.search(text) and not re.search(r"combin|combined|gesamt", text, re.I):
        return Verdict(False, "eaer_city_only")
    # interval min for range (en/em dash or hyphen or "bis")
    pairs = re.findall(r"(\d+(?:[.,]\d+)?)\s*(?:–|—|-|bis)\s*(\d+(?:[.,]\d+)?)", text)
    if pairs:
        lo, hi = (float(pairs[0][0].replace(",", ".")), float(pairs[0][1].replace(",", ".")))
        if abs(float(chosen_km) - min(lo, hi)) > 1e-9:
            return Verdict(False, "non_prudent_range_extremum")
    return Verdict(True, "ok_range")


def validate_cs_interval_pick(lo: float, hi: float, chosen: float) -> Verdict:
    """CS / pure electric consumption: must pick max of pertinent interval."""
    if abs(float(chosen) - max(float(lo), float(hi))) > 1e-9:
        return Verdict(False, "non_prudent_cs_extremum")
    return Verdict(True, "ok_cs_max")


def validate_energy_cite(cite: str, energy_value: float | None) -> Verdict:
    if energy_value is None:
        return Verdict(True, "ok_energy_nil")
    if not has_pure_energy_label(cite):
        return Verdict(False, "energy_without_pure_label")
    return Verdict(True, "ok_energy")


def validate_completeness_flag(row: dict[str, Any]) -> Verdict:
    miss = missing_calc_fields(row)
    incomplete = bool(row.get("catalogDataIncomplete"))
    if miss and not incomplete:
        return Verdict(False, "complete_with_nil_calc")
    if not miss and incomplete:
        return Verdict(False, "incomplete_flag_with_full_calc")
    return Verdict(True, "ok_completeness")


def validate_field_import(
    *,
    row_year: int,
    field: str,
    value: Any,
    url: str,
    source_date: str | None,
    label: str,
    download_path: Path | str | None = None,
) -> Verdict:
    """Single entry used for fixtures and real accepted imports."""
    if download_path is not None:
        fmt = inspect_download(download_path)
        if not fmt.ok:
            return fmt
    dating = validate_source_dating(row_year=row_year, source_date=source_date, url=url)
    if not dating.ok:
        return dating
    if field == "wltpRangeKm":
        return validate_range_label(label, value)
    if field == "energyConsumptionKWhPerKm":
        return validate_energy_cite(label, value)
    if field == "fuelConsumptionLPerKm":
        # if label embeds an interval, require max
        pairs = re.findall(r"(\d+(?:[.,]\d+)?)\s*(?:–|-|bis)\s*(\d+(?:[.,]\d+)?)", label or "")
        if pairs:
            lo, hi = (float(pairs[0][0].replace(",", ".")), float(pairs[0][1].replace(",", ".")))
            return validate_cs_interval_pick(lo, hi, float(value))
    return Verdict(True, "ok_import")
