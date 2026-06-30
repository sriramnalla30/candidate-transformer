"""Location, country (ISO-3166 alpha-2), name, email, and URL normalization."""
from __future__ import annotations

import re

import pycountry

# Common explicit aliases first (fast + deterministic for the demo cases).
_COUNTRY_ALIASES = {
    "india": "IN",
    "bharat": "IN",
    "usa": "US",
    "u.s.a.": "US",
    "u.s.": "US",
    "us": "US",
    "united states": "US",
    "united states of america": "US",
    "america": "US",
    "uk": "GB",
    "u.k.": "GB",
    "united kingdom": "GB",
    "great britain": "GB",
    "england": "GB",
    "uae": "AE",
    "south korea": "KR",
}


def normalize_country(raw):
    """`normalize(raw) -> (alpha2_or_None, ok)` (ISO-3166 alpha-2)."""
    if raw is None:
        return None, False
    text = str(raw).strip()
    if not text:
        return None, False
    low = text.lower()

    if low in _COUNTRY_ALIASES:
        return _COUNTRY_ALIASES[low], True

    # Already a valid alpha-2?
    if len(text) == 2 and text.isalpha():
        match = pycountry.countries.get(alpha_2=text.upper())
        if match:
            return text.upper(), True

    # Try alpha-3 and full names via pycountry.
    try:
        if len(text) == 3 and text.isalpha():
            match = pycountry.countries.get(alpha_3=text.upper())
            if match:
                return match.alpha_2, True
        match = pycountry.countries.get(name=text.title())
        if match:
            return match.alpha_2, True
        # Fuzzy lookup as a last resort (handles "Republic of India" etc.), but only
        # for inputs long enough to be unambiguous — guards against "Go", "JS", etc.
        if len(text) >= 4:
            results = pycountry.countries.search_fuzzy(text)
            if results:
                return results[0].alpha_2, True
    except (LookupError, KeyError):
        pass

    return None, False


def _clean_text(raw):
    if raw is None:
        return None
    return re.sub(r"\s+", " ", str(raw)).strip()


def normalize_city(raw):
    """City/region passthrough: collapse whitespace + title-case."""
    cleaned = _clean_text(raw)
    if not cleaned:
        return None, False
    return cleaned.title(), True


def normalize_location(city=None, region=None, country=None):
    """Build a normalized {city, region, country} dict (None where unknown)."""
    out_city, _ = normalize_city(city) if city else (None, False)
    out_region, _ = normalize_city(region) if region else (None, False)
    out_country, _ = normalize_country(country) if country else (None, False)
    return {"city": out_city, "region": out_region, "country": out_country}


# --------------------------------------------------------------------------- #
# Names
# --------------------------------------------------------------------------- #
def normalize_name(raw):
    """Collapse whitespace, strip, title-case. Keeps initials like 'Priya S.'."""
    cleaned = _clean_text(raw)
    if not cleaned:
        return None, False
    parts = []
    for tok in cleaned.split(" "):
        # Preserve trailing-dot initials ("S." -> "S.") with a capital letter.
        if re.fullmatch(r"[A-Za-z]\.?", tok):
            parts.append(tok.upper() if tok.endswith(".") else tok.upper() + ".")
            # bare single letter -> add a dot for consistency
            if not tok.endswith("."):
                parts[-1] = tok.upper() + "."
        else:
            parts.append(tok.capitalize())
    return " ".join(parts), True


def is_full_name(name) -> bool:
    """A name is 'full' if it has 2+ tokens and none is a bare initial."""
    if not name:
        return False
    toks = str(name).split()
    if len(toks) < 2:
        return False
    return not any(re.fullmatch(r"[A-Za-z]\.?", t) for t in toks)


# --------------------------------------------------------------------------- #
# Emails
# --------------------------------------------------------------------------- #
_EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")


def normalize_email(raw):
    """Lowercase, strip, validate. Invalid → (None, False)."""
    if raw is None:
        return None, False
    text = str(raw).strip().lower()
    if not text or not _EMAIL_RE.match(text):
        return None, False
    return text, True


# --------------------------------------------------------------------------- #
# URLs / links
# --------------------------------------------------------------------------- #
def normalize_url(raw):
    """Ensure scheme, lowercase host, strip simple tracking params.

    Returns (normalized_url, kind) where kind ∈ {linkedin, github, portfolio}.
    Invalid → (None, None).
    """
    if raw is None:
        return None, None
    text = str(raw).strip()
    if not text:
        return None, None
    if not re.match(r"^https?://", text, re.IGNORECASE):
        text = "https://" + text.lstrip("/")

    m = re.match(r"^(https?)://([^/]+)(.*)$", text, re.IGNORECASE)
    if not m:
        return None, None
    scheme, host, rest = m.group(1).lower(), m.group(2).lower(), m.group(3)
    # strip common tracking query params
    rest = re.sub(r"[?&](utm_[^=&]+|ref|source)=[^&]*", "", rest)
    rest = rest.rstrip("?&")
    url = f"https://{host}{rest}"

    if "linkedin.com" in host:
        kind = "linkedin"
    elif "github.com" in host:
        kind = "github"
    else:
        kind = "portfolio"
    return url, kind
