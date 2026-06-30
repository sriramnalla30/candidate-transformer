"""Phase 9 — end-to-end gold-profile test (spec 10, recommended)."""
import os

from transformer.pipeline import run

SAMPLES = os.path.join(os.path.dirname(__file__), "..", "data", "sample_inputs")


def _sample(name):
    return os.path.join(SAMPLES, name)


ALL_INPUTS = [
    _sample("recruiter_export.csv"), _sample("ats_blob.json"),
    _sample("github_priya.json"), _sample("resume_priya.txt"),
    _sample("recruiter_notes.txt"), _sample("broken.json"),
]


def test_priya_gold_profile():
    result = run(ALL_INPUTS, "config/default.json")
    profiles = result.profiles
    priya = [p for p in profiles if p["full_name"] == "Priya Sharma"]
    assert len(priya) == 1, "Priya should merge into exactly one profile"
    p = priya[0]

    assert "priya.sharma@gmail.com" in p["emails"]
    assert "+919876543210" in p["phones"]
    skill_names = {s["name"] for s in p["skills"]}
    assert "Python" in skill_names
    assert "Go" in skill_names
    assert p["overall_confidence"] > 0.5
    # provenance + confidence present in default output
    assert p["provenance"]
    # merged from multiple sources (csv+ats+resume+notes+github)
    contributing = {entry["source"] for entry in p["provenance"]}
    assert len(contributing) >= 3


def test_at_least_two_candidates():
    result = run(ALL_INPUTS, "config/default.json")
    assert result.num_candidates >= 2
    names = {p["full_name"] for p in result.profiles}
    assert "Priya Sharma" in names
    assert names - {"Priya Sharma"}, "a second distinct candidate must exist"


def test_custom_config_summary_card():
    result = run(ALL_INPUTS, "config/custom_example.json")
    priya = [p for p in result.profiles if p["full_name"] == "Priya Sharma"][0]
    # renamed fields exist; provenance dropped; confidence kept
    assert priya["primary_email"] == "priya.sharma@gmail.com"
    assert priya["phone"] == "+919876543210"
    assert isinstance(priya["skills"], list) and all(isinstance(s, str) for s in priya["skills"])
    assert "provenance" not in priya
    assert "overall_confidence" in priya
