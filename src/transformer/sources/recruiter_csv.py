"""Recruiter CSV adapter (STRUCTURED). Columns: name,email,phone,current_company,title."""
from __future__ import annotations

import csv

from .base import SourceAdapter, make_record


class RecruiterCSVAdapter(SourceAdapter):
    source_type = "recruiter_csv"

    def can_handle(self, descriptor) -> bool:
        return str(descriptor).lower().endswith(".csv")

    def extract(self, raw, warnings=None) -> list:
        warnings = warnings if warnings is not None else []
        records = []
        try:
            with open(raw, "r", encoding="utf-8-sig", newline="") as fh:
                reader = csv.DictReader(fh)
                for i, row in enumerate(reader):
                    try:
                        rec = self._row_to_record(row)
                        if rec:
                            records.append(rec)
                        else:
                            warnings.append(
                                f"recruiter_csv: skipped row {i + 2} (no usable identity)"
                            )
                    except Exception as exc:  # noqa: BLE001 — defensive per spec
                        warnings.append(f"recruiter_csv: bad row {i + 2}: {exc}")
        except FileNotFoundError:
            warnings.append(f"recruiter_csv: file not found: {raw}")
            return []
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"recruiter_csv: failed to read {raw}: {exc}")
            return []
        return records

    @staticmethod
    def _row_to_record(row: dict):
        name = (row.get("name") or "").strip()
        email = (row.get("email") or "").strip()
        phone = (row.get("phone") or "").strip()
        company = (row.get("current_company") or "").strip()
        title = (row.get("title") or "").strip()

        # A row needs at least a name or an email to be a usable identity.
        if not name and not email:
            return None

        experience = []
        if company or title:
            experience = [{
                "company": company or None,
                "title": title or None,
                "start": None, "end": None, "summary": None,
            }]

        return make_record(
            "recruiter_csv",
            method="exact",
            full_name=name or None,
            emails=[email] if email else [],
            phones=[phone] if phone else [],
            headline=title or None,
            experience=experience,
        )
