"""Recruiter notes adapter (UNSTRUCTURED). Lowest-trust free text → extractor."""
from __future__ import annotations

from .base import SourceAdapter, make_record, set_method
from ..llm.extractor import extract_fields


class RecruiterNotesAdapter(SourceAdapter):
    source_type = "recruiter_notes"

    def can_handle(self, descriptor) -> bool:
        d = str(descriptor).lower()
        return d.endswith(".txt") and "note" in d

    def extract(self, raw, warnings=None) -> list:
        warnings = warnings if warnings is not None else []
        try:
            with open(str(raw), "r", encoding="utf-8") as fh:
                text = fh.read()
        except FileNotFoundError:
            warnings.append(f"recruiter_notes: file not found: {raw}")
            return []
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"recruiter_notes: failed to read {raw}: {exc}")
            return []

        if not text.strip():
            return []

        try:
            fields, method = extract_fields(text, "notes")
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"recruiter_notes: extractor failed: {exc}")
            return []

        rec = make_record(
            "recruiter_notes",
            method=method,
            full_name=fields.get("full_name"),
            emails=fields.get("emails", []),
            phones=fields.get("phones", []),
            headline=fields.get("headline"),
            years_experience=fields.get("years_experience"),
            skills=fields.get("skills", []),
            experience=fields.get("experience", []),
            location=fields.get("location") if fields.get("location") and any(
                (fields.get("location") or {}).values()
            ) else None,
        )
        if method == "llm":
            for f in ("emails", "phones"):
                if f in rec:
                    set_method(rec, f, "rule")
        return [rec]
