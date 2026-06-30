"""Canonical record models, config models, and the `from`-path resolver.

The internal canonical record is rich and stable; the OUTPUT is a projection of it
(see project.py). Models are dataclasses (no pydantic) so they work on any Python 3.10+,
including very new interpreters. Validation is hand-written in validate.py.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict
from typing import Any, Optional


# --------------------------------------------------------------------------- #
# Source trust ranking (spec 04). Higher = more trusted for identity/contact.
# --------------------------------------------------------------------------- #
SOURCE_TRUST: dict[str, float] = {
    "recruiter_csv": 0.90,
    "ats_json": 0.85,
    "github": 0.80,
    "resume": 0.65,
    "recruiter_notes": 0.45,
}

# Field importance weights for overall_confidence (spec 06).
FIELD_WEIGHTS: dict[str, int] = {
    "full_name": 3,
    "emails": 3,
    "phones": 2,
    "location": 1,
    "headline": 1,
    "years_experience": 1,
    "skills": 2,
    "experience": 2,
    "education": 1,
}

# method -> confidence factor (spec 06).
METHOD_FACTOR: dict[str, float] = {
    "exact": 1.0,
    "normalized": 1.0,
    "rule": 0.85,
    "llm": 0.80,
    "derived": 0.75,
}


# --------------------------------------------------------------------------- #
# Canonical sub-models
# --------------------------------------------------------------------------- #
@dataclass
class Location:
    city: Optional[str] = None
    region: Optional[str] = None
    country: Optional[str] = None  # ISO-3166 alpha-2


@dataclass
class Links:
    linkedin: Optional[str] = None
    github: Optional[str] = None
    portfolio: Optional[str] = None
    other: list[str] = field(default_factory=list)


@dataclass
class Skill:
    name: str
    confidence: float = 0.5
    sources: list[str] = field(default_factory=list)


@dataclass
class ExperienceEntry:
    company: Optional[str] = None
    title: Optional[str] = None
    start: Optional[str] = None      # "YYYY-MM" or None
    end: Optional[str] = None        # "YYYY-MM", "present", or None
    summary: Optional[str] = None


@dataclass
class EducationEntry:
    institution: Optional[str] = None
    degree: Optional[str] = None
    field: Optional[str] = None
    end_year: Optional[int] = None


@dataclass
class ProvenanceEntry:
    field: str       # dotted/indexed canonical path the value populated
    source: str      # recruiter_csv | ats_json | github | resume | recruiter_notes
    method: str      # exact | normalized | llm | rule | derived
    value: Any


@dataclass
class CanonicalProfile:
    candidate_id: str = ""
    full_name: Optional[str] = None
    emails: list[str] = field(default_factory=list)
    phones: list[str] = field(default_factory=list)
    location: Location = field(default_factory=Location)
    links: Links = field(default_factory=Links)
    headline: Optional[str] = None
    years_experience: Optional[float] = None
    skills: list[Skill] = field(default_factory=list)
    experience: list[ExperienceEntry] = field(default_factory=list)
    education: list[EducationEntry] = field(default_factory=list)
    provenance: list[ProvenanceEntry] = field(default_factory=list)
    overall_confidence: float = 0.0

    def to_dict(self) -> dict:
        """Plain JSON-serializable dict of the full canonical record."""
        return asdict(self)


# --------------------------------------------------------------------------- #
# Config models (spec 07)
# --------------------------------------------------------------------------- #
@dataclass
class FieldSpec:
    path: str                       # key name in the OUTPUT object
    from_: Optional[str] = None     # canonical path to read from (defaults to path)
    type: str = "string"            # string|number|boolean|object|string[]|object[]
    required: bool = False
    normalize: Optional[str] = None  # E164 | canonical | iso-date | none

    @property
    def source_path(self) -> str:
        return self.from_ or self.path


@dataclass
class Config:
    fields: list[FieldSpec] = field(default_factory=list)
    include_confidence: bool = True
    include_provenance: bool = True
    on_missing: str = "null"        # null | omit | error

    @staticmethod
    def from_dict(data: dict) -> "Config":
        fields: list[FieldSpec] = []
        for f in data.get("fields", []):
            fields.append(
                FieldSpec(
                    path=f["path"],
                    from_=f.get("from"),
                    type=f.get("type", "string"),
                    required=bool(f.get("required", False)),
                    normalize=f.get("normalize"),
                )
            )
        return Config(
            fields=fields,
            include_confidence=bool(data.get("include_confidence", True)),
            include_provenance=bool(data.get("include_provenance", True)),
            on_missing=data.get("on_missing", "null"),
        )


# --------------------------------------------------------------------------- #
# `from`-path resolver (spec 07 mini-language)
# --------------------------------------------------------------------------- #
class _Missing:
    """Singleton sentinel for 'value not present'."""

    _inst = None

    def __new__(cls):
        if cls._inst is None:
            cls._inst = super().__new__(cls)
        return cls._inst

    def __repr__(self) -> str:
        return "MISSING"

    def __bool__(self) -> bool:
        return False


MISSING = _Missing()

# A segment is a key optionally followed by [N] or [].
_SEG_RE = re.compile(r"^([A-Za-z0-9_]+)(\[\d+\]|\[\])?$")


def resolve(record: Any, path: str) -> Any:
    """Resolve a `from` path against the canonical record (dict form).

    Supported forms (chainable across '.'):
      - `field`        top-level field
      - `field[0]`     Nth element of an array
      - `obj.key`      nested object key
      - `array[].key`  collect `key` from each element into a list

    Returns the value, or MISSING if any step is absent/out-of-range. Never raises.
    """
    if path is None:
        return MISSING
    current: Any = record
    segments = path.split(".")
    for i, seg in enumerate(segments):
        m = _SEG_RE.match(seg)
        if not m:
            return MISSING
        key, suffix = m.group(1), m.group(2)

        if suffix == "[]":
            # Collect `key` from each element, then apply the REST of the path
            # to each collected element.
            if not isinstance(current, dict) or key not in current:
                return MISSING
            arr = current[key]
            if not isinstance(arr, list):
                return MISSING
            rest = ".".join(segments[i + 1:])
            collected = []
            for elem in arr:
                if rest:
                    v = resolve(elem, rest)
                    if v is not MISSING and v is not None:
                        collected.append(v)
                else:
                    collected.append(elem)
            return collected

        # plain key access
        if not isinstance(current, dict) or key not in current:
            return MISSING
        current = current[key]

        if suffix and suffix.startswith("[") and suffix != "[]":
            idx = int(suffix[1:-1])
            if not isinstance(current, list) or idx >= len(current) or idx < -len(current):
                return MISSING
            current = current[idx]

    return current
