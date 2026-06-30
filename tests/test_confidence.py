"""Phase 4 — confidence tests (spec 10)."""
from transformer.confidence import (
    field_confidence, overall_confidence, skill_confidence, base_trust,
)
from transformer.merge import build_profiles


def nrec(source, index, **fields):
    rec = {"source": source, "_index": index, "_methods": {}, "_norm_ok": {}}
    rec.update(fields)
    return rec


def test_structured_beats_informal():
    # recruiter_csv exact > recruiter_notes rule/llm for the same field.
    csv_conf = field_confidence("recruiter_csv", "exact", 1)
    notes_conf = field_confidence("recruiter_notes", "rule", 1)
    assert csv_conf > notes_conf


def test_agreement_raises_confidence():
    lone = field_confidence("ats_json", "exact", 1)
    agreed = field_confidence("ats_json", "exact", 3)
    assert agreed > lone


def test_overall_in_range_and_excludes_nulls():
    confs = {"full_name": 0.9, "emails": 0.9, "skills": 0.7}
    overall = overall_confidence(confs)
    assert 0.0 <= overall <= 1.0
    # weighted mean of populated fields only (full_name:3, emails:3, skills:2)
    expected = round((0.9 * 3 + 0.9 * 3 + 0.7 * 2) / (3 + 3 + 2), 2)
    assert overall == expected


def test_skill_confidence_more_sources_and_dictionary():
    assert skill_confidence(2, True) > skill_confidence(1, False)
    assert 0.0 <= skill_confidence(5, True) <= 1.0


def test_profile_overall_confidence_bounds():
    recs = [nrec("recruiter_csv", 0, full_name="Priya Sharma", emails=["p@x.com"])]
    p = build_profiles(recs)[0]
    assert 0.0 <= p.overall_confidence <= 1.0


def test_trust_ordering():
    assert base_trust("recruiter_csv") > base_trust("ats_json") > base_trust("github") \
        > base_trust("resume") > base_trust("recruiter_notes")
