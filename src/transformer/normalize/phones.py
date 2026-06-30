"""Phone normalization → E.164. Pure function, never guesses."""
from __future__ import annotations

import os

import phonenumbers

# Default region for bare numbers without a country code (spec 05).
DEFAULT_REGION = os.getenv("DEFAULT_PHONE_REGION", "IN")


def normalize_phone(raw, region: str | None = None):
    """`normalize(raw) -> (value_or_None, ok)`.

    Parses, validates, and formats to E.164 (e.g. "+919876543210").
    Garbage / invalid numbers return (None, False) — never invented.
    """
    if raw is None:
        return None, False
    text = str(raw).strip()
    if not text:
        return None, False
    region = region or DEFAULT_REGION
    try:
        # If the string already carries a '+', let the lib infer the region.
        parsed = phonenumbers.parse(text, None if text.startswith("+") else region)
    except phonenumbers.NumberParseException:
        return None, False
    if not phonenumbers.is_valid_number(parsed):
        return None, False
    formatted = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
    return formatted, True
