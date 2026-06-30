"""GitHub adapter (UNSTRUCTURED). Local saved-JSON mode + optional live API mode."""
from __future__ import annotations

import json
import os

from .base import SourceAdapter, make_record, set_method
from ..llm.extractor import extract_fields


class GitHubAdapter(SourceAdapter):
    source_type = "github"

    def can_handle(self, descriptor) -> bool:
        d = str(descriptor).lower()
        return "github.com" in d or d.startswith("gh:")

    def extract(self, raw, warnings=None) -> list:
        warnings = warnings if warnings is not None else []
        data = self._load(raw, warnings)
        if data is None:
            return []
        try:
            rec = self._profile_to_record(data, warnings)
            return [rec] if rec else []
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"github: failed to map profile: {exc}")
            return []

    # ------------------------------------------------------------------ #
    def _load(self, raw, warnings):
        """Load a saved GitHub JSON file, or fetch live if a username/URL given."""
        raw_str = str(raw)
        if os.path.isfile(raw_str):
            try:
                with open(raw_str, "r", encoding="utf-8") as fh:
                    return json.load(fh)
            except Exception as exc:  # noqa: BLE001
                warnings.append(f"github: bad local file {raw}: {exc}")
                return None
        # Live mode (best-effort; offline-safe).
        login = self._extract_login(raw_str)
        if not login:
            warnings.append(f"github: cannot resolve a login from {raw}")
            return None
        return self._fetch_live(login, warnings)

    @staticmethod
    def _extract_login(raw_str):
        s = raw_str.strip()
        if s.startswith("gh:"):
            return s[3:].strip("/ ")
        if "github.com" in s:
            tail = s.split("github.com", 1)[1].strip("/ ")
            return tail.split("/")[0] if tail else None
        if "/" not in s and " " not in s and "." not in s:
            return s
        return None

    def _fetch_live(self, login, warnings):
        try:
            import urllib.request

            url = f"https://api.github.com/users/{login}"
            with urllib.request.urlopen(url, timeout=5) as resp:  # noqa: S310
                if resp.status != 200:
                    warnings.append(f"github: live fetch non-200 for {login}")
                    return None
                profile = json.loads(resp.read().decode("utf-8"))
            try:
                with urllib.request.urlopen(  # noqa: S310
                    f"https://api.github.com/users/{login}/repos?per_page=100", timeout=5
                ) as r2:
                    repos = json.loads(r2.read().decode("utf-8")) if r2.status == 200 else []
                profile["repos_languages"] = [
                    rp.get("language") for rp in repos if rp.get("language")
                ]
            except Exception:  # noqa: BLE001
                pass
            return profile
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"github: live fetch failed for {login}: {exc} (skipping)")
            return None

    # ------------------------------------------------------------------ #
    def _profile_to_record(self, data: dict, warnings):
        if not isinstance(data, dict):
            return None
        login = data.get("login")
        name = data.get("name")
        blog = data.get("blog")
        company = data.get("company")
        location_raw = data.get("location")
        bio = data.get("bio") or ""

        links = {}
        if login:
            links["github"] = f"https://github.com/{login}"
        if blog:
            links["portfolio"] = blog

        # Repo languages → skill candidates (frequency-ordered, deterministic).
        langs = data.get("repos_languages", []) or []
        freq: dict[str, int] = {}
        for lang in langs:
            if lang:
                freq[lang] = freq.get(lang, 0) + 1
        ranked_langs = [k for k, _ in sorted(freq.items(), key=lambda kv: (-kv[1], kv[0]))]

        # Bio → extractor (skills/headline). Method depends on LLM vs fallback.
        extracted, method = extract_fields(bio, "github_bio") if bio else ({}, "rule")
        bio_skills = extracted.get("skills", []) or []
        headline = extracted.get("headline")

        # "Bangalore, India" → city/country split (country normalized later).
        location = None
        if location_raw:
            parts = [p.strip() for p in str(location_raw).split(",")]
            if len(parts) >= 2:
                location = {"city": parts[0], "region": None, "country": parts[-1]}
            else:
                location = {"city": parts[0], "region": None, "country": None}

        experience = []
        if company:
            experience = [{
                "company": str(company).lstrip("@"), "title": None,
                "start": None, "end": None, "summary": None,
            }]

        all_skills = ranked_langs + [s for s in bio_skills if s not in ranked_langs]

        rec = make_record(
            "github",
            method="exact",
            full_name=name,
            links=links if links else None,
            headline=headline,
            skills=all_skills,
            location=location,
            experience=experience,
        )
        # Bio-derived fields carry the extractor's method (llm/rule); skills are a
        # mix of structured repo languages + bio, tagged with the extractor method.
        if "skills" in rec:
            set_method(rec, "skills", method)
        if "headline" in rec:
            set_method(rec, "headline", method)
        return rec
