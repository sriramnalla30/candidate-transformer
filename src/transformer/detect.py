"""Stage 1 — DETECT. Decide each input's source type. Never raises.

Input descriptors may be:
  - a plain path/URL string ("data/x.csv")
  - a "path:type" string to force a type ("data/x.json:ats_json")
An undetectable input is skipped (returns None) with a warning recorded.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass

VALID_TYPES = {"recruiter_csv", "ats_json", "github", "resume", "recruiter_notes"}


@dataclass
class DetectedSource:
    source_type: str
    handle: str          # path or login/URL to hand to the adapter
    original_index: int  # for deterministic tie-breaks downstream


def _split_explicit(descriptor: str):
    """Return (path, explicit_type or None). Supports 'path:type' (not the URL colon)."""
    s = str(descriptor)
    if ":" in s:
        head, _, tail = s.rpartition(":")
        if tail in VALID_TYPES and head:
            return head, tail
    return s, None


def _looks_like_github_json(path: str) -> bool:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception:  # noqa: BLE001 — detection must never crash
        return False
    if not isinstance(data, dict):
        return False
    keys = set(data.keys())
    return bool(keys & {"login", "html_url", "repos_languages", "public_repos"})


def detect_one(descriptor, index: int, warnings: list[str]):
    """Detect a single input → DetectedSource | None."""
    path, explicit = _split_explicit(descriptor)

    if explicit:
        return DetectedSource(explicit, path, index)

    low = path.lower()

    # URL / username github mode
    if "github.com" in low or low.startswith("gh:"):
        return DetectedSource("github", path, index)

    if low.endswith(".csv"):
        return DetectedSource("recruiter_csv", path, index)

    if low.endswith(".json"):
        # Distinguish a saved GitHub profile JSON from an ATS blob by content.
        if os.path.isfile(path) and _looks_like_github_json(path):
            return DetectedSource("github", path, index)
        return DetectedSource("ats_json", path, index)

    if low.endswith(".pdf"):
        return DetectedSource("resume", path, index)

    if low.endswith(".txt"):
        # notes vs resume by filename hint
        if "note" in low:
            return DetectedSource("recruiter_notes", path, index)
        return DetectedSource("resume", path, index)

    warnings.append(f"detect: could not determine source type for '{descriptor}' (skipped)")
    return None


def detect(descriptors, warnings: list[str] | None = None):
    """Detect a list of inputs → list[DetectedSource] (undetectable ones skipped)."""
    warnings = warnings if warnings is not None else []
    out = []
    for i, d in enumerate(descriptors):
        try:
            ds = detect_one(d, i, warnings)
            if ds is not None:
                out.append(ds)
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"detect: error on '{d}': {exc} (skipped)")
    return out
