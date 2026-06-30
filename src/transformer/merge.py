"""Stage 4 — MERGE (dedup + conflict resolution) and assembly of CanonicalProfiles.

Blocking keys (email > phone > name+country) feed a union-find so we never do an
O(n^2) all-pairs comparison. Within each cluster every canonical field is resolved
to a winner by: source trust -> cross-source agreement -> completeness -> recency
(stable). ALL contributing values are retained as provenance.
"""
from __future__ import annotations

import hashlib
import re

from .schema import (
    CanonicalProfile, Location, Links, Skill, ExperienceEntry, EducationEntry,
    ProvenanceEntry, SOURCE_TRUST,
)
from .normalize import is_full_name, is_known_skill
from . import confidence as conf


# --------------------------------------------------------------------------- #
# Union-Find
# --------------------------------------------------------------------------- #
class UnionFind:
    def __init__(self, n: int):
        self.parent = list(range(n))

    def find(self, x: int) -> int:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            # union by smaller root for determinism
            lo, hi = sorted((ra, rb))
            self.parent[hi] = lo


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(text or "").lower()).strip("-")


# --------------------------------------------------------------------------- #
# Blocking + clustering
# --------------------------------------------------------------------------- #
def cluster(records: list[dict]) -> list[list[int]]:
    """Return clusters as lists of record indices, via blocking-key union-find."""
    n = len(records)
    uf = UnionFind(n)
    key_to_indices: dict[tuple, list[int]] = {}

    for i, rec in enumerate(records):
        keys = []
        for e in rec.get("emails", []) or []:
            keys.append(("email", e))
        for p in rec.get("phones", []) or []:
            keys.append(("phone", p))
        # Weak key: full name + country (never name alone; never bare initials).
        name = rec.get("full_name")
        country = (rec.get("location") or {}).get("country")
        if name and is_full_name(name) and country:
            keys.append(("nl", _slug(name) + "|" + country))
        for k in keys:
            key_to_indices.setdefault(k, []).append(i)

    for indices in key_to_indices.values():
        first = indices[0]
        for j in indices[1:]:
            uf.union(first, j)

    groups: dict[int, list[int]] = {}
    for i in range(n):
        groups.setdefault(uf.find(i), []).append(i)
    # deterministic order: by smallest member index
    return [sorted(g) for _, g in sorted(groups.items(), key=lambda kv: min(kv[1]))]


# --------------------------------------------------------------------------- #
# Field resolution
# --------------------------------------------------------------------------- #
def _trust(source: str) -> float:
    return SOURCE_TRUST.get(source, 0.5)


def _resolve_single(candidates):
    """candidates: list of dicts {value, source, method, index, complete}.
    Returns (winner_dict, supporters_count) using the ordered policy, or (None, 0).
    """
    cands = [c for c in candidates if c["value"] not in (None, "", [])]
    if not cands:
        return None, 0

    # group by normalized value for agreement
    by_value: dict = {}
    for c in cands:
        vk = str(c["value"]).strip().lower()
        by_value.setdefault(vk, []).append(c)

    def effective(value_group):
        supporters = {c["source"] for c in value_group}
        best_trust = max(_trust(c["source"]) for c in value_group)
        return best_trust + 0.15 * (len(supporters) - 1)

    def sort_key(value_group):
        # higher effective, then more complete, then earliest index, then source name
        best = max(value_group, key=lambda c: (_trust(c["source"]), c["complete"], -c["index"]))
        supporters = {c["source"] for c in value_group}
        return (
            effective(value_group),
            best["complete"],
            -best["index"],
            -ord(best["source"][0]) if best["source"] else 0,
        )

    best_group = max(by_value.values(), key=sort_key)
    supporters = sorted({c["source"] for c in best_group})
    # winning representative within the group: highest trust, most complete, earliest
    winner = max(best_group, key=lambda c: (_trust(c["source"]), c["complete"], -c["index"]))
    winner = dict(winner)
    winner["supporters"] = supporters
    return winner, len(supporters)


def _gather(records, indices, field, completeness=None):
    """Collect candidate dicts for a top-level scalar field across cluster records."""
    out = []
    for i in indices:
        rec = records[i]
        if field in rec and rec[field] not in (None, "", []):
            val = rec[field]
            out.append({
                "value": val,
                "source": rec["source"],
                "method": rec.get("_methods", {}).get(field, "exact"),
                "index": rec.get("_index", i),
                "complete": completeness(val) if completeness else len(str(val)),
            })
    return out


# --------------------------------------------------------------------------- #
# Main: build one CanonicalProfile per cluster
# --------------------------------------------------------------------------- #
def build_profiles(records: list[dict], warnings=None) -> list[CanonicalProfile]:
    warnings = warnings if warnings is not None else []
    clusters = cluster(records)
    profiles = []
    for group in clusters:
        try:
            profiles.append(_build_one(records, group))
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"merge: failed to build a profile: {exc}")
    # deterministic ordering of output: by full_name then candidate_id
    profiles.sort(key=lambda p: ((p.full_name or "~").lower(), p.candidate_id))
    return profiles


def _build_one(records, indices) -> CanonicalProfile:
    prov: list[ProvenanceEntry] = []
    field_confs: dict[str, float] = {}
    p = CanonicalProfile()

    # ---- full_name (completeness: full names beat initials) ----
    def name_completeness(v):
        return (1 if is_full_name(v) else 0, len(str(v)))

    name_cands = _gather(records, indices, "full_name", name_completeness)
    winner, n_agree = _resolve_single(name_cands)
    if winner:
        p.full_name = winner["value"]
        prov.append(ProvenanceEntry("full_name", winner["source"], winner["method"], p.full_name))
        field_confs["full_name"] = conf.field_confidence(winner["source"], winner["method"], n_agree)

    # ---- emails (UNION, ordered by best source trust) ----
    p.emails, e_prov, e_conf = _union_contacts(records, indices, "emails")
    prov.extend(e_prov)
    if e_conf is not None:
        field_confs["emails"] = e_conf

    # ---- phones (UNION) ----
    p.phones, ph_prov, ph_conf = _union_contacts(records, indices, "phones")
    prov.extend(ph_prov)
    if ph_conf is not None:
        field_confs["phones"] = ph_conf

    # ---- location (resolve each sub-field) ----
    loc, loc_prov, loc_conf = _resolve_location(records, indices)
    p.location = loc
    prov.extend(loc_prov)
    if loc_conf is not None:
        field_confs["location"] = loc_conf

    # ---- links ----
    p.links, links_prov = _resolve_links(records, indices)
    prov.extend(links_prov)

    # ---- headline ----
    hl_cands = _gather(records, indices, "headline")
    winner, n_agree = _resolve_single(hl_cands)
    if winner:
        p.headline = winner["value"]
        prov.append(ProvenanceEntry("headline", winner["source"], winner["method"], p.headline))
        field_confs["headline"] = conf.field_confidence(winner["source"], winner["method"], n_agree)

    # ---- years_experience ----
    ye_cands = _gather(records, indices, "years_experience", lambda v: float(v))
    winner, n_agree = _resolve_single(ye_cands)
    if winner:
        p.years_experience = winner["value"]
        prov.append(ProvenanceEntry("years_experience", winner["source"], winner["method"], p.years_experience))
        field_confs["years_experience"] = conf.field_confidence(winner["source"], winner["method"], n_agree)

    # ---- skills (UNION; per-skill confidence) ----
    p.skills, skills_prov, skills_conf = _merge_skills(records, indices)
    prov.extend(skills_prov)
    if skills_conf is not None:
        field_confs["skills"] = skills_conf

    # ---- experience ----
    p.experience, exp_prov, exp_conf = _merge_experience(records, indices)
    prov.extend(exp_prov)
    if exp_conf is not None:
        field_confs["experience"] = exp_conf

    # ---- education ----
    p.education, edu_prov, edu_conf = _merge_education(records, indices)
    prov.extend(edu_prov)
    if edu_conf is not None:
        field_confs["education"] = edu_conf

    # ---- candidate_id (deterministic) ----
    p.candidate_id = _candidate_id(p)

    # ---- overall confidence ----
    p.overall_confidence = conf.overall_confidence(field_confs)
    p.provenance = prov
    return p


def _union_contacts(records, indices, field):
    """Union emails/phones across the cluster, ordered by best contributing trust."""
    value_to_best = {}  # value -> (best_trust, source, method)
    order = []
    for i in indices:
        rec = records[i]
        method = rec.get("_methods", {}).get(field, "exact")
        for v in rec.get(field, []) or []:
            t = _trust(rec["source"])
            if v not in value_to_best or t > value_to_best[v][0]:
                value_to_best[v] = (t, rec["source"], method)
            if v not in order:
                order.append(v)
    if not order:
        return [], [], None
    ordered = sorted(order, key=lambda v: (-value_to_best[v][0], v))
    prov = []
    idx = 0
    for v in ordered:
        _, src, method = value_to_best[v]
        prov.append(ProvenanceEntry(f"{field}[{idx}]", src, method, v))
        idx += 1
    # field confidence: best contributing source, agreement = #distinct sources
    sources = {value_to_best[v][1] for v in ordered}
    best_v = ordered[0]
    _, best_src, best_method = value_to_best[best_v]
    fconf = conf.field_confidence(best_src, best_method, len(sources))
    return ordered, prov, fconf


def _resolve_location(records, indices):
    prov = []
    sub = {}
    confs = []
    for key in ("city", "region", "country"):
        cands = []
        for i in indices:
            rec = records[i]
            loc = rec.get("location") or {}
            if loc.get(key):
                cands.append({
                    "value": loc[key],
                    "source": rec["source"],
                    "method": rec.get("_methods", {}).get("location", "exact"),
                    "index": rec.get("_index", i),
                    "complete": len(str(loc[key])),
                })
        winner, n_agree = _resolve_single(cands)
        if winner:
            sub[key] = winner["value"]
            prov.append(ProvenanceEntry(f"location.{key}", winner["source"], winner["method"], winner["value"]))
            confs.append(conf.field_confidence(winner["source"], winner["method"], n_agree))
        else:
            sub[key] = None
    location = Location(city=sub.get("city"), region=sub.get("region"), country=sub.get("country"))
    loc_conf = round(sum(confs) / len(confs), 4) if confs else None
    return location, prov, loc_conf


def _resolve_links(records, indices):
    prov = []
    links = Links()
    for key in ("linkedin", "github", "portfolio"):
        cands = []
        for i in indices:
            rec = records[i]
            l = rec.get("links") or {}
            if l.get(key):
                cands.append({
                    "value": l[key], "source": rec["source"],
                    "method": rec.get("_methods", {}).get("links", "exact"),
                    "index": rec.get("_index", i), "complete": len(str(l[key])),
                })
        winner, _ = _resolve_single(cands)
        if winner:
            setattr(links, key, winner["value"])
            prov.append(ProvenanceEntry(f"links.{key}", winner["source"], winner["method"], winner["value"]))
    # union 'other'
    others = []
    for i in indices:
        for o in ((records[i].get("links") or {}).get("other") or []):
            if o not in others:
                others.append(o)
    links.other = others
    return links, prov


def _merge_skills(records, indices):
    name_to_sources: dict[str, list[str]] = {}
    name_to_method: dict[str, str] = {}
    order = []
    for i in indices:
        rec = records[i]
        method = rec.get("_methods", {}).get("skills", "rule")
        for sk in rec.get("skills", []) or []:
            name = sk["name"] if isinstance(sk, dict) else sk
            if name not in name_to_sources:
                name_to_sources[name] = []
                order.append(name)
                name_to_method[name] = method
            if rec["source"] not in name_to_sources[name]:
                name_to_sources[name].append(rec["source"])
    if not order:
        return [], [], None

    skills = []
    prov = []
    confs = []
    # order by confidence desc, then name
    def sk_conf(name):
        return conf.skill_confidence(len(name_to_sources[name]), is_known_skill(name))

    for name in sorted(order, key=lambda n: (-sk_conf(n), n)):
        sources = sorted(name_to_sources[name])
        c = sk_conf(name)
        skills.append(Skill(name=name, confidence=c, sources=sources))
        confs.append(c)
        for s in sources:
            prov.append(ProvenanceEntry(f"skills.{name}", s, name_to_method[name], name))
    field_conf = round(sum(confs) / len(confs), 4) if confs else None
    return skills, prov, field_conf


def _exp_sort_key(e: ExperienceEntry):
    """Newest-first: 'present' is most recent, then by start desc, undated last."""
    end = e.end
    if end == "present":
        return (2, "9999-99")
    start = e.start or e.end or ""
    return (1 if start else 0, start)


def _merge_experience(records, indices):
    entries: list[tuple[str, ExperienceEntry, str, str]] = []  # (compkey, entry, source, method)
    for i in indices:
        rec = records[i]
        method = rec.get("_methods", {}).get("experience", "exact")
        for e in rec.get("experience", []) or []:
            comp = (e.get("company") or "").strip().lower()
            entries.append((comp, e, rec["source"], method))

    merged: dict[str, dict] = {}
    order = []
    for comp, e, source, method in entries:
        key = comp or f"_noco_{len(order)}"
        if key not in merged:
            merged[key] = {
                "company": e.get("company"), "title": e.get("title"),
                "start": e.get("start"), "end": e.get("end"), "summary": e.get("summary"),
                "sources": {source: method}, "best_trust": _trust(source),
            }
            order.append(key)
        else:
            m = merged[key]
            m["sources"].setdefault(source, method)
            # fill gaps preferring higher-trust source for scalar fields
            if _trust(source) > m["best_trust"]:
                m["best_trust"] = _trust(source)
                for f in ("title", "start", "end", "summary", "company"):
                    if e.get(f):
                        m[f] = e.get(f)
            else:
                for f in ("title", "start", "end", "summary"):
                    if not m.get(f) and e.get(f):
                        m[f] = e.get(f)

    out = []
    prov = []
    confs = []
    for key in order:
        m = merged[key]
        entry = ExperienceEntry(
            company=m["company"], title=m["title"],
            start=m["start"], end=m["end"], summary=m["summary"],
        )
        out.append(entry)
        # best source for this entry
        best_source = max(m["sources"], key=lambda s: _trust(s))
        confs.append(conf.field_confidence(best_source, m["sources"][best_source], len(m["sources"])))
        for s, method in m["sources"].items():
            prov.append(ProvenanceEntry(f"experience.{m['company']}", s, method, m["company"]))

    out.sort(key=_exp_sort_key, reverse=True)
    field_conf = round(sum(confs) / len(confs), 4) if confs else None
    return out, prov, field_conf


def _merge_education(records, indices):
    merged: dict[str, dict] = {}
    order = []
    for i in indices:
        rec = records[i]
        method = rec.get("_methods", {}).get("education", "exact")
        for ed in rec.get("education", []) or []:
            inst = (ed.get("institution") or "").strip().lower()
            key = inst or f"_noinst_{len(order)}"
            if key not in merged:
                merged[key] = {
                    "institution": ed.get("institution"), "degree": ed.get("degree"),
                    "field": ed.get("field"), "end_year": ed.get("end_year"),
                    "sources": {rec["source"]: method}, "best_trust": _trust(rec["source"]),
                }
                order.append(key)
            else:
                m = merged[key]
                m["sources"].setdefault(rec["source"], method)
                for f in ("degree", "field", "end_year"):
                    if not m.get(f) and ed.get(f):
                        m[f] = ed.get(f)

    out, prov, confs = [], [], []
    for key in order:
        m = merged[key]
        out.append(EducationEntry(
            institution=m["institution"], degree=m["degree"],
            field=m["field"], end_year=m["end_year"],
        ))
        best_source = max(m["sources"], key=lambda s: _trust(s))
        confs.append(conf.field_confidence(best_source, m["sources"][best_source], len(m["sources"])))
        for s, method in m["sources"].items():
            prov.append(ProvenanceEntry(f"education.{m['institution']}", s, method, m["institution"]))

    out.sort(key=lambda e: (e.end_year is not None, e.end_year or 0), reverse=True)
    field_conf = round(sum(confs) / len(confs), 4) if confs else None
    return out, prov, field_conf


def _candidate_id(p: CanonicalProfile) -> str:
    if p.emails:
        key = p.emails[0].lower()
    elif p.phones:
        key = p.phones[0]
    else:
        company = ""
        if p.experience and p.experience[0].company:
            company = p.experience[0].company
        key = _slug(p.full_name or "") + "|" + _slug(company)
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:10]
    return "cand_" + digest
