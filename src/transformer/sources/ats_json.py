"""ATS JSON adapter (STRUCTURED/semi-structured). Remaps foreign field names → ours."""
from __future__ import annotations

import json

from .base import SourceAdapter, make_record


class ATSJsonAdapter(SourceAdapter):
    source_type = "ats_json"

    def can_handle(self, descriptor) -> bool:
        return str(descriptor).lower().endswith(".json")

    def extract(self, raw, warnings=None) -> list:
        warnings = warnings if warnings is not None else []
        try:
            with open(raw, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except FileNotFoundError:
            warnings.append(f"ats_json: file not found: {raw}")
            return []
        except json.JSONDecodeError as exc:
            warnings.append(f"ats_json: malformed JSON in {raw}: {exc}")
            return []
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"ats_json: failed to read {raw}: {exc}")
            return []

        candidates = self._iter_candidates(data)
        records = []
        for i, cand in enumerate(candidates):
            try:
                rec = self._candidate_to_record(cand)
                if rec:
                    records.append(rec)
            except Exception as exc:  # noqa: BLE001
                warnings.append(f"ats_json: bad candidate {i}: {exc}")
        return records

    @staticmethod
    def _iter_candidates(data):
        """Accept a single object, {'candidate':{}}, {'candidates':[...]}, or a list."""
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            if "candidates" in data and isinstance(data["candidates"], list):
                return data["candidates"]
            if "candidate" in data and isinstance(data["candidate"], dict):
                return [data["candidate"]]
            return [data]
        return []

    @staticmethod
    def _candidate_to_record(c: dict):
        if not isinstance(c, dict):
            return None
        name = c.get("fullName")
        email = c.get("emailAddress")
        mobile = c.get("mobile")
        company = c.get("companyName")
        title = c.get("jobTitle")

        experience = []
        if company or title:
            experience = [{
                "company": company, "title": title,
                "start": None, "end": None, "summary": None,
            }]

        education = []
        for sc in c.get("schools", []) or []:
            if not isinstance(sc, dict):
                continue
            education.append({
                "institution": sc.get("name"),
                "degree": sc.get("degree"),
                "field": sc.get("field"),
                "end_year": sc.get("gradYear"),
            })

        location = {
            "city": c.get("locationCity"),
            "region": c.get("locationRegion"),
            "country": c.get("locationCountry"),
        }

        return make_record(
            "ats_json",
            method="exact",
            full_name=name,
            emails=[email] if email else [],
            phones=[str(mobile)] if mobile is not None else [],
            headline=title,
            years_experience=c.get("yearsExp"),
            location=location if any(location.values()) else None,
            experience=experience,
            education=education,
        )
