"""Phase 4 — merge tests (spec 10)."""
from transformer.merge import cluster, build_profiles, _resolve_single


def nrec(source, index, **fields):
    """Build a minimal NormalizedRecord for merge tests."""
    rec = {"source": source, "_index": index, "_methods": {}, "_norm_ok": {}}
    rec.update(fields)
    return rec


def _cand(value, source, index=0, complete=None):
    return {
        "value": value, "source": source, "method": "exact",
        "index": index, "complete": complete if complete is not None else len(str(value)),
    }


# ----------------------- clustering ----------------------- #
def test_shared_email_merges():
    recs = [
        nrec("recruiter_csv", 0, full_name="Priya Sharma", emails=["p@x.com"]),
        nrec("ats_json", 1, full_name="Priya S.", emails=["p@x.com"]),
    ]
    clusters = cluster(recs)
    assert len(clusters) == 1
    assert sorted(clusters[0]) == [0, 1]


def test_shared_phone_merges():
    recs = [
        nrec("recruiter_csv", 0, full_name="Priya Sharma", phones=["+919876543210"]),
        nrec("recruiter_notes", 1, full_name="Priya", phones=["+919876543210"]),
    ]
    clusters = cluster(recs)
    assert len(clusters) == 1


def test_name_initial_only_does_not_merge():
    # Different emails, different phones, only a same first name + initial → no merge.
    recs = [
        nrec("recruiter_csv", 0, full_name="Priya S.", emails=["a@x.com"], phones=["+911111111111"]),
        nrec("ats_json", 1, full_name="Priya S.", emails=["b@y.com"], phones=["+912222222222"]),
    ]
    clusters = cluster(recs)
    assert len(clusters) == 2  # guard against over-merging


def test_fullname_plus_country_weak_merge():
    # Same FULL name + same country, no email/phone overlap → weak key links them.
    recs = [
        nrec("github", 0, full_name="Priya Sharma", location={"city": None, "region": None, "country": "IN"}),
        nrec("resume", 1, full_name="Priya Sharma", location={"city": None, "region": None, "country": "IN"}),
    ]
    clusters = cluster(recs)
    assert len(clusters) == 1


# ----------------------- conflict resolution ----------------------- #
def test_source_trust_wins():
    # recruiter_csv company beats recruiter_notes company (higher trust).
    winner, _ = _resolve_single([
        _cand("Flipkart", "recruiter_csv", 0),
        _cand("Amazon", "recruiter_notes", 1),
    ])
    assert winner["value"] == "Flipkart"
    assert winner["source"] == "recruiter_csv"


def test_agreement_beats_lone_higher_trust():
    # ats_json (0.85) + github (0.80) agree → effective 1.00 > lone recruiter_csv 0.90.
    winner, n = _resolve_single([
        _cand("Bengaluru", "recruiter_csv", 0),
        _cand("Mumbai", "ats_json", 1),
        _cand("Mumbai", "github", 2),
    ])
    assert winner["value"] == "Mumbai"
    assert n == 2


def test_multivalue_union_dedup():
    recs = [
        nrec("recruiter_csv", 0, full_name="Priya Sharma",
             emails=["p@x.com"], phones=["+919876543210"],
             skills=[{"name": "Python", "mapped": True}]),
        nrec("ats_json", 1, full_name="Priya S.",
             emails=["p@x.com", "priya@work.com"], phones=["+919876543210"],
             skills=[{"name": "Go", "mapped": True}]),
    ]
    profiles = build_profiles(recs)
    assert len(profiles) == 1
    p = profiles[0]
    assert sorted(p.emails) == ["p@x.com", "priya@work.com"]   # union + dedup
    assert p.phones == ["+919876543210"]                        # deduped
    names = sorted(s.name for s in p.skills)
    assert names == ["Go", "Python"]                            # union of skills
