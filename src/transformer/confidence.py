"""Stage 5 — CONFIDENCE. Deterministic, fully explainable scores in [0,1].

Per-field:
    field_conf = base_trust(source) * method_factor * agreement_boost * normalization_factor
    (final clamped to [0,1])

Skill:
    skill_conf = clamp(0.5 + 0.15 * #sources + dictionary_bonus, 0, 1)

Overall:
    importance-weighted mean of per-field confidences over POPULATED fields only.
"""
from __future__ import annotations

from .schema import SOURCE_TRUST, METHOD_FACTOR, FIELD_WEIGHTS


def clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def base_trust(source: str) -> float:
    return SOURCE_TRUST.get(source, 0.5)


def method_factor(method: str) -> float:
    return METHOD_FACTOR.get(method, 0.8)


def agreement_boost(num_agreeing_sources: int) -> float:
    """1.0 for a lone source; +0.15 per additional agreeing source (>=1)."""
    n = max(1, num_agreeing_sources)
    return 1.0 + 0.15 * (n - 1)


def field_confidence(source: str, method: str, num_agreeing: int,
                     normalization_factor: float = 1.0) -> float:
    raw = (
        base_trust(source)
        * method_factor(method)
        * agreement_boost(num_agreeing)
        * normalization_factor
    )
    return round(clamp(raw), 4)


def skill_confidence(num_sources: int, in_dictionary: bool) -> float:
    bonus = 0.1 if in_dictionary else 0.0
    return round(clamp(0.5 + 0.15 * num_sources + bonus), 4)


def overall_confidence(field_confidences: dict[str, float]) -> float:
    """Importance-weighted mean over populated fields (those present in the dict)."""
    num = 0.0
    den = 0.0
    for field, conf in field_confidences.items():
        w = FIELD_WEIGHTS.get(field, 1)
        num += conf * w
        den += w
    if den == 0:
        return 0.0
    return round(num / den, 2)
