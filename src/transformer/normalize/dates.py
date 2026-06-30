"""Date normalization → "YYYY-MM". Pure functions, never guess.

Rules (spec 05):
  - Output "YYYY-MM" only when the month is known.
  - "present"/"current" → literal "present" (allowed sentinel for experience end).
  - Year-only → (None, False) for YYYY-MM; the bare year is kept by the caller in
    provenance, and education.end_year uses normalize_year() instead.
  - Garbage → (None, False).
"""
from __future__ import annotations

import re

_MONTHS = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}

_PRESENT = {"present", "current", "now", "ongoing", "till date", "to date"}


def normalize_date(raw):
    """`normalize(raw) -> (value_or_None, ok)` producing "YYYY-MM" or "present"."""
    if raw is None:
        return None, False
    text = str(raw).strip().lower()
    if not text:
        return None, False

    if text in _PRESENT:
        return "present", True

    # "2020-01" or "2020/01"
    m = re.fullmatch(r"(\d{4})[-/](\d{1,2})", text)
    if m:
        year, month = int(m.group(1)), int(m.group(2))
        if 1 <= month <= 12:
            return f"{year:04d}-{month:02d}", True
        return None, False

    # "01/2020" or "01-2020" (month first)
    m = re.fullmatch(r"(\d{1,2})[-/](\d{4})", text)
    if m:
        month, year = int(m.group(1)), int(m.group(2))
        if 1 <= month <= 12:
            return f"{year:04d}-{month:02d}", True
        return None, False

    # "Jan 2020" / "March 2019" / "Sep. 2021"
    m = re.fullmatch(r"([a-z]+)\.?\s+(\d{4})", text)
    if m and m.group(1) in _MONTHS:
        month = _MONTHS[m.group(1)]
        year = int(m.group(2))
        return f"{year:04d}-{month:02d}", True

    # "2020 Jan" (year first, month name)
    m = re.fullmatch(r"(\d{4})\s+([a-z]+)\.?", text)
    if m and m.group(2) in _MONTHS:
        month = _MONTHS[m.group(2)]
        year = int(m.group(1))
        return f"{year:04d}-{month:02d}", True

    # Bare year → month unknown → not a valid YYYY-MM (spec rule).
    if re.fullmatch(r"\d{4}", text):
        return None, False

    return None, False


def normalize_year(raw):
    """`normalize(raw) -> (int_year_or_None, ok)` for education end_year."""
    if raw is None:
        return None, False
    if isinstance(raw, int):
        return (raw, True) if 1900 <= raw <= 2100 else (None, False)
    text = str(raw).strip()
    m = re.search(r"\b(19|20)\d{2}\b", text)
    if m:
        return int(m.group(0)), True
    return None, False
