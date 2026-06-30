"""Skill canonicalization via a dictionary of aliases. Deterministic, explainable."""
from __future__ import annotations

import json
import os
import re

_DICT_PATH = os.path.join(os.path.dirname(__file__), "skills_dictionary.json")

with open(_DICT_PATH, "r", encoding="utf-8") as _fh:
    SKILLS_DICTIONARY: dict[str, str] = json.load(_fh)


def normalize_skill(raw):
    """`normalize(raw) -> (canonical_name_or_None, mapped: bool)`.

    Unknown skills are NOT dropped — they are title-cased and returned with
    mapped=False so confidence can be slightly lowered (spec 05/06).
    """
    if raw is None:
        return None, False
    cleaned = re.sub(r"\s+", " ", str(raw)).strip()
    if not cleaned:
        return None, False
    key = cleaned.lower()
    if key in SKILLS_DICTIONARY:
        return SKILLS_DICTIONARY[key], True
    # Keep unknown skill, title-cased, flagged unmapped.
    return cleaned.title(), False


def canonical_skill_set(raw_skills):
    """Normalize a list of raw skills → list of (name, mapped) de-duplicated
    case-insensitively, preserving first-seen order (deterministic)."""
    seen: dict[str, tuple[str, bool]] = {}
    for raw in raw_skills or []:
        name, mapped = normalize_skill(raw)
        if not name:
            continue
        k = name.lower()
        if k not in seen:
            seen[k] = (name, mapped)
        elif mapped and not seen[k][1]:
            # upgrade to mapped form if we later see a dictionary hit
            seen[k] = (name, mapped)
    return list(seen.values())


def is_known_skill(name) -> bool:
    """True if the canonical name corresponds to a dictionary entry."""
    if not name:
        return False
    return name in set(SKILLS_DICTIONARY.values())
