"""Normalization stage: pure functions turning raw values into canonical formats.

Each normalizer follows `normalize(raw) -> (value_or_None, ok)`. A value that
cannot be cleaned becomes None (robustness rule); the original is preserved in
provenance by the caller.
"""
from .phones import normalize_phone, DEFAULT_REGION
from .dates import normalize_date, normalize_year
from .location import (
    normalize_country,
    normalize_city,
    normalize_location,
    normalize_name,
    is_full_name,
    normalize_email,
    normalize_url,
)
from .skills import (
    normalize_skill,
    canonical_skill_set,
    is_known_skill,
    SKILLS_DICTIONARY,
)

__all__ = [
    "normalize_phone",
    "DEFAULT_REGION",
    "normalize_date",
    "normalize_year",
    "normalize_country",
    "normalize_city",
    "normalize_location",
    "normalize_name",
    "is_full_name",
    "normalize_email",
    "normalize_url",
    "normalize_skill",
    "canonical_skill_set",
    "is_known_skill",
    "SKILLS_DICTIONARY",
]
