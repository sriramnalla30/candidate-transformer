"""Resume adapter (UNSTRUCTURED). Accepts .txt and .pdf; sends text to the extractor."""
from __future__ import annotations

from .base import SourceAdapter, make_record, set_method
from ..llm.extractor import extract_fields


class ResumeAdapter(SourceAdapter):
    source_type = "resume"

    def can_handle(self, descriptor) -> bool:
        d = str(descriptor).lower()
        return d.endswith(".pdf") or (d.endswith(".txt") and "note" not in d)

    def extract(self, raw, warnings=None) -> list:
        warnings = warnings if warnings is not None else []
        text = self._read_text(raw, warnings)
        if not text:
            return []
        try:
            fields, method = extract_fields(text, "resume")
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"resume: extractor failed: {exc}")
            return []

        rec = make_record(
            "resume",
            method=method,
            full_name=fields.get("full_name"),
            emails=fields.get("emails", []),
            phones=fields.get("phones", []),
            headline=fields.get("headline"),
            years_experience=fields.get("years_experience"),
            skills=fields.get("skills", []),
            experience=fields.get("experience", []),
            education=fields.get("education", []),
            location=fields.get("location") if fields.get("location") and any(
                (fields.get("location") or {}).values()
            ) else None,
        )
        # Emails/phones are literal text matches → "rule" even when other fields are llm.
        if method == "llm":
            for f in ("emails", "phones"):
                if f in rec:
                    set_method(rec, f, "rule")
        return [rec]

    @staticmethod
    def _read_text(raw, warnings):
        path = str(raw)
        if path.lower().endswith(".pdf"):
            try:
                from pypdf import PdfReader

                reader = PdfReader(path)
                return "\n".join((page.extract_text() or "") for page in reader.pages)
            except Exception as exc:  # noqa: BLE001
                warnings.append(f"resume: PDF extraction failed for {path}: {exc}")
                return ""
        try:
            with open(path, "r", encoding="utf-8") as fh:
                return fh.read()
        except FileNotFoundError:
            warnings.append(f"resume: file not found: {path}")
            return ""
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"resume: failed to read {path}: {exc}")
            return ""
