"""Public extraction entry point: `extract_fields(text, kind) -> (dict, method)`.

Tries the Groq LLM first; on a missing key or ANY failure, falls back to a
deterministic regex/dictionary extractor so the project always runs. Both paths
return the SAME contract shape (spec 08) so adapters never branch. The fallback
NEVER invents a value — if a pattern is not found, the field stays null/empty.
"""
from __future__ import annotations

import re

from .groq_client import call_groq, GroqError, has_api_key
from ..normalize.skills import SKILLS_DICTIONARY

CONTRACT_KEYS = {
    "full_name", "headline", "years_experience", "skills",
    "experience", "education", "location", "phones", "emails",
}


def _empty():
    return {
        "full_name": None,
        "headline": None,
        "years_experience": None,
        "skills": [],
        "experience": [],
        "education": [],
        "location": {"city": None, "region": None, "country": None},
        "phones": [],
        "emails": [],
    }


def _coerce_contract(d: dict) -> dict:
    """Force any returned dict into exactly the contract shape."""
    out = _empty()
    if not isinstance(d, dict):
        return out
    for k in CONTRACT_KEYS:
        if k in d and d[k] is not None:
            out[k] = d[k]
    # guarantee list/dict types
    for k in ("skills", "experience", "education", "phones", "emails"):
        if not isinstance(out[k], list):
            out[k] = []
    if not isinstance(out["location"], dict):
        out["location"] = {"city": None, "region": None, "country": None}
    return out


def extract_fields(text: str, kind: str):
    """Returns (contract_dict, method) where method is 'llm' or 'rule'."""
    if not text or not text.strip():
        return _empty(), "rule"

    if has_api_key():
        try:
            data = call_groq(text, kind)
            return _coerce_contract(data), "llm"
        except GroqError:
            pass  # fall through to deterministic fallback
        except Exception:  # noqa: BLE001 — never let the LLM crash the run
            pass

    return _fallback(text, kind), "rule"


# --------------------------------------------------------------------------- #
# Deterministic fallback
# --------------------------------------------------------------------------- #
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
_YEARS_RE = re.compile(r"(\d+(?:\.\d+)?)\s*\+?\s*(?:years|yrs|yr)\b", re.IGNORECASE)
_PHONE_RE = re.compile(r"\+?\d[\d\s\-().]{8,}\d")
_ROLE_WORDS = (
    "engineer", "developer", "manager", "scientist", "designer",
    "architect", "analyst", "consultant", "lead", "director", "intern",
)


def _find_skills(text: str):
    low = text.lower()
    found = []
    for alias, canonical in SKILLS_DICTIONARY.items():
        # word-boundary match; tolerate symbols like c++, c#, ci/cd, node.js
        pattern = r"(?<![A-Za-z0-9])" + re.escape(alias) + r"(?![A-Za-z0-9])"
        if re.search(pattern, low):
            if canonical not in found:
                found.append(canonical)
    return found


def _find_emails(text: str):
    out = []
    for e in _EMAIL_RE.findall(text):
        e = e.strip().lower().rstrip(".")
        if e not in out:
            out.append(e)
    return out


def _find_phones(text: str):
    out = []
    for m in _PHONE_RE.findall(text):
        digits = re.sub(r"\D", "", m)
        if 10 <= len(digits) <= 15:
            cand = m.strip()
            if cand not in out:
                out.append(cand)
    return out


def _find_years(text: str):
    m = _YEARS_RE.search(text)
    if not m:
        return None
    val = float(m.group(1))
    return int(val) if val == int(val) else round(val, 1)


def _looks_like_name(line: str) -> bool:
    line = line.strip()
    if not line or "@" in line or any(ch.isdigit() for ch in line):
        return False
    toks = line.split()
    if not (2 <= len(toks) <= 4):
        return False
    return all(re.fullmatch(r"[A-Za-z][A-Za-z.\-']*", t) for t in toks)


def _find_headline(text: str, kind: str):
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if kind == "github_bio":
        first = re.split(r"[.|]", text.strip())[0].strip()
        if first and len(first) <= 80 and any(w in first.lower() for w in _ROLE_WORDS):
            return first
        return None
    for line in lines:
        # A role-word line that is short and has no sentence period is a title.
        if len(line) <= 80 and "." not in line and "," not in line \
                and any(w in line.lower() for w in _ROLE_WORDS):
            return line
    return None


def _find_full_name(text: str, kind: str):
    if kind == "notes":
        # Lead-in is case-insensitive; the name group stays strictly capitalized so
        # trailing lowercase words ("...Sharma today") are not swallowed.
        m = re.search(
            r"(?:[Ss]poke (?:with|to)|[Cc]andidate|[Nn]ame[:\s])\s+"
            r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})",
            text,
        )
        if m:
            return m.group(1)
        return None
    # resume / bio: first non-empty line that looks like a name
    for line in text.splitlines():
        if line.strip():
            if _looks_like_name(line):
                return line.strip()
            break
    return None


def _find_country_city(text: str):
    """Best-effort 'City, Country' where Country is a recognizable country name.

    Deliberately conservative: the country part must be a known alias or a word of
    length > 3 that normalizes cleanly — this avoids matching skill lists like
    "Knows Python, Go".
    """
    from ..normalize.location import normalize_country, _COUNTRY_ALIASES

    for m in re.finditer(
        r"([A-Z][A-Za-z]+(?:\s[A-Z][A-Za-z]+)?),\s*([A-Za-z][A-Za-z .]+?)(?:[.\n,]|$)", text
    ):
        city, country = m.group(1).strip(), m.group(2).strip()
        if country.lower() in _COUNTRY_ALIASES or (len(country) > 3 and normalize_country(country)[1]):
            return {"city": city, "region": None, "country": country}
    return {"city": None, "region": None, "country": None}


def _find_experience(text: str):
    """Parse resume-style 'Title, Company — Start to End' lines."""
    out = []
    pattern = re.compile(
        r"^(.+?),\s*(.+?)\s*[—\-–]\s*(.+?)\s+to\s+(.+?)\s*$", re.MULTILINE
    )
    for m in pattern.finditer(text):
        title, company, start, end = (g.strip() for g in m.groups())
        if any(ch.isdigit() for ch in company):  # avoid catching date-only lines
            continue
        out.append({
            "company": company, "title": title,
            "start": start, "end": end, "summary": None,
        })
    # also "at <Company>" mentions in notes
    for m in re.finditer(r"\b(?:at|@)\s+([A-Z][A-Za-z0-9&.\- ]{1,30})", text):
        company = m.group(1).strip().rstrip(".")
        if company and not any(e["company"].lower() == company.lower() for e in out):
            out.append({"company": company, "title": None, "start": None, "end": None, "summary": None})
    return out


def _find_education(text: str):
    out = []
    pattern = re.compile(
        r"(B\.?Tech|M\.?Tech|B\.?E\.?|M\.?E\.?|B\.?Sc|M\.?Sc|MBA|PhD|Bachelor[a-z']*|Master[a-z']*)"
        r"(?:\s+(?:in|of)\s+([A-Za-z ]+?))?,\s*([A-Z][A-Za-z .&]+?),\s*((?:19|20)\d{2})",
        re.IGNORECASE,
    )
    for m in pattern.finditer(text):
        degree, field, inst, year = m.groups()
        out.append({
            "institution": inst.strip(),
            "degree": degree.strip(),
            "field": field.strip() if field else None,
            "end_year": int(year),
        })
    return out


def _fallback(text: str, kind: str) -> dict:
    result = _empty()
    result["skills"] = _find_skills(text)
    result["emails"] = _find_emails(text)
    result["phones"] = _find_phones(text)
    result["years_experience"] = _find_years(text)
    result["headline"] = _find_headline(text, kind)
    result["full_name"] = _find_full_name(text, kind)
    if kind in ("resume", "notes"):
        # GitHub bios rarely carry a clean 'City, Country'; the github adapter uses
        # the structured `location` field instead, so skip bio location extraction.
        result["location"] = _find_country_city(text)
        result["experience"] = _find_experience(text)
    if kind == "resume":
        result["education"] = _find_education(text)
    return result
