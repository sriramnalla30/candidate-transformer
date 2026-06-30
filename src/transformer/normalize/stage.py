"""Stage 3 — NORMALIZE. Apply the pure normalizers to each RawRecord.

Produces a list of NormalizedRecord dicts. Each record keeps, per field:
  - the normalized value (or None / [] when it could not be cleaned)
  - the provenance method AFTER normalization (`_methods`)
  - whether normalization succeeded (`_norm_ok`) — used by confidence

Method rule: origin methods llm/rule/derived are sticky (so LLM-sourced values keep
their lower trust). A structured "exact" value that gets reformatted becomes
"normalized" (same confidence factor, just descriptive).
"""
from __future__ import annotations

from .phones import normalize_phone
from .dates import normalize_date, normalize_year
from .location import (
    normalize_country,
    normalize_city,
    normalize_name,
    normalize_email,
    normalize_url,
)
from .skills import canonical_skill_set, is_known_skill


def _post_method(origin: str, changed: bool) -> str:
    if origin in ("llm", "rule", "derived"):
        return origin
    return "normalized" if changed else "exact"


def _dedup_keep_order(items):
    seen, out = set(), []
    for x in items:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


def normalize_record(raw: dict) -> dict:
    """RawRecord -> NormalizedRecord. Pure; never raises on a single bad value."""
    source = raw.get("source", "unknown")
    methods_in = raw.get("_methods", {})
    default_method = raw.get("_method", "exact")

    def origin(field):
        return methods_in.get(field, default_method)

    out = {
        "source": source,
        "_index": raw.get("_index", 0),
        "_methods": {},
        "_norm_ok": {},
    }

    # --- full_name ---
    if raw.get("full_name"):
        name, ok = normalize_name(raw["full_name"])
        if name:
            changed = name != str(raw["full_name"]).strip()
            out["full_name"] = name
            out["_methods"]["full_name"] = _post_method(origin("full_name"), changed)
            out["_norm_ok"]["full_name"] = True

    # --- emails ---
    emails = []
    for e in raw.get("emails", []) or []:
        val, ok = normalize_email(e)
        if ok:
            emails.append(val)
    emails = _dedup_keep_order(emails)
    if emails:
        out["emails"] = emails
        out["_methods"]["emails"] = _post_method(origin("emails"), True)
        out["_norm_ok"]["emails"] = True

    # --- phones ---
    phones = []
    for p in raw.get("phones", []) or []:
        val, ok = normalize_phone(p)
        if ok:
            phones.append(val)
    phones = _dedup_keep_order(phones)
    if phones:
        out["phones"] = phones
        out["_methods"]["phones"] = _post_method(origin("phones"), True)
        out["_norm_ok"]["phones"] = True

    # --- location ---
    loc_in = raw.get("location") or {}
    if loc_in:
        city, _ = normalize_city(loc_in.get("city")) if loc_in.get("city") else (None, False)
        region, _ = normalize_city(loc_in.get("region")) if loc_in.get("region") else (None, False)
        country, c_ok = normalize_country(loc_in.get("country")) if loc_in.get("country") else (None, False)
        if city or region or country:
            out["location"] = {"city": city, "region": region, "country": country}
            out["_methods"]["location"] = _post_method(origin("location"), True)
            # norm_ok reflects country normalization (the strictly-validated part)
            out["_norm_ok"]["location"] = bool(country) if loc_in.get("country") else True

    # --- links ---
    links_in = raw.get("links") or {}
    if links_in:
        links = {"linkedin": None, "github": None, "portfolio": None, "other": []}
        for key in ("linkedin", "github", "portfolio"):
            if links_in.get(key):
                url, kind = normalize_url(links_in[key])
                if url:
                    links[kind if kind in links else "portfolio"] = url
        for o in links_in.get("other", []) or []:
            url, _ = normalize_url(o)
            if url:
                links["other"].append(url)
        if any([links["linkedin"], links["github"], links["portfolio"], links["other"]]):
            out["links"] = links
            out["_methods"]["links"] = _post_method(origin("links"), True)
            out["_norm_ok"]["links"] = True

    # --- headline ---
    if raw.get("headline"):
        hl = " ".join(str(raw["headline"]).split())
        out["headline"] = hl
        out["_methods"]["headline"] = origin("headline")
        out["_norm_ok"]["headline"] = True

    # --- years_experience ---
    ye = raw.get("years_experience")
    if ye is not None:
        try:
            num = float(ye)
            if num >= 0:
                # integer-ize whole numbers for clean output
                out["years_experience"] = int(num) if num == int(num) else round(num, 1)
                out["_methods"]["years_experience"] = origin("years_experience")
                out["_norm_ok"]["years_experience"] = True
        except (TypeError, ValueError):
            pass

    # --- skills ---
    raw_skills = raw.get("skills", []) or []
    canon = canonical_skill_set(raw_skills)  # [(name, mapped), ...]
    if canon:
        out["skills"] = [{"name": n, "mapped": m} for n, m in canon]
        out["_methods"]["skills"] = origin("skills")
        # field-level norm_ok = at least one mapped skill
        out["_norm_ok"]["skills"] = any(m for _, m in canon)

    # --- experience ---
    exp_out = []
    for e in raw.get("experience", []) or []:
        if not isinstance(e, dict):
            continue
        company = e.get("company")
        company = str(company).lstrip("@").strip() if company else None
        title = " ".join(str(e["title"]).split()) if e.get("title") else None
        start, s_ok = normalize_date(e.get("start")) if e.get("start") else (None, False)
        end, e_ok = normalize_date(e.get("end")) if e.get("end") else (None, False)
        summary = e.get("summary")
        if company or title:
            exp_out.append({
                "company": company.title() if company else None,
                "title": title,
                "start": start,
                "end": end,
                "summary": summary,
            })
    if exp_out:
        out["experience"] = exp_out
        out["_methods"]["experience"] = origin("experience")
        out["_norm_ok"]["experience"] = True

    # --- education ---
    edu_out = []
    for ed in raw.get("education", []) or []:
        if not isinstance(ed, dict):
            continue
        inst = " ".join(str(ed["institution"]).split()) if ed.get("institution") else None
        year, y_ok = normalize_year(ed.get("end_year")) if ed.get("end_year") is not None else (None, False)
        if inst or ed.get("degree"):
            edu_out.append({
                "institution": inst,
                "degree": ed.get("degree"),
                "field": ed.get("field"),
                "end_year": year,
            })
    if edu_out:
        out["education"] = edu_out
        out["_methods"]["education"] = origin("education")
        out["_norm_ok"]["education"] = True

    return out


def has_identity(rec: dict) -> bool:
    """True if a normalized record carries any usable identity/content."""
    return bool(
        rec.get("full_name") or rec.get("emails") or rec.get("phones")
        or rec.get("skills") or rec.get("experience") or rec.get("education")
    )


def normalize_records(raw_records, warnings=None):
    """Normalize a list of RawRecords; drop empty/no-identity records (robustness)."""
    warnings = warnings if warnings is not None else []
    out = []
    for raw in raw_records:
        try:
            nr = normalize_record(raw)
            if has_identity(nr):
                out.append(nr)
            else:
                warnings.append(
                    f"normalize: dropped a {raw.get('source','?')} record with no usable identity"
                )
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"normalize: failed on a {raw.get('source','?')} record: {exc}")
    return out
