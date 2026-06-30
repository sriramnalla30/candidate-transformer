"""Common source-adapter interface + the RawRecord helper.

A RawRecord is a loose dict of canonical-ish fields plus bookkeeping keys:
  - "source":   the source_type tag (e.g. "recruiter_csv")
  - "_method":  default provenance method for this record's fields
                ("exact" | "llm" | "rule" | "derived")
  - "_methods": optional per-field method overrides {field_name: method}

Adapters NEVER normalize and NEVER merge — they only map a source's own shape
onto our field names, defensively (a bad item is skipped, never crashes).
"""
from __future__ import annotations

from typing import Any

# Warnings are collected here by the pipeline; adapters append human-readable strings.
RawRecord = dict[str, Any]


class SourceAdapter:
    source_type: str = "base"

    def can_handle(self, descriptor) -> bool:
        raise NotImplementedError

    def extract(self, raw, warnings: list[str] | None = None) -> list[RawRecord]:
        """Map source data → list[RawRecord]. Must never raise out of here."""
        raise NotImplementedError


def make_record(source: str, method: str = "exact", **fields) -> RawRecord:
    """Build a RawRecord, dropping None/empty values for cleanliness."""
    rec: RawRecord = {"source": source, "_method": method, "_methods": {}}
    for k, v in fields.items():
        if v is None:
            continue
        if isinstance(v, (list, dict, str)) and len(v) == 0:
            continue
        rec[k] = v
    return rec


def set_method(rec: RawRecord, field: str, method: str) -> None:
    """Override the provenance method for one field of a record."""
    rec.setdefault("_methods", {})[field] = method


def method_for(rec: RawRecord, field: str) -> str:
    """Resolve the provenance method for a given field of a record."""
    return rec.get("_methods", {}).get(field, rec.get("_method", "exact"))
