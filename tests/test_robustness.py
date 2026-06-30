"""Phase 9 — robustness tests (spec 10). The required edge-case coverage.

These run with NO network and NO Groq key (conftest clears it), so the
deterministic fallback path is exercised throughout.
"""
import json
import os

from transformer.pipeline import run
from transformer.validate import validate_all
from transformer.schema import Config

HERE = os.path.dirname(__file__)
FIX = os.path.join(HERE, "fixtures")
SAMPLES = os.path.join(os.path.dirname(HERE), "data", "sample_inputs")


def _sample(name):
    return os.path.join(SAMPLES, name)


def test_malformed_json_does_not_crash():
    result = run([os.path.join(FIX, "broken.json"), _sample("recruiter_export.csv")],
                 "config/default.json")
    # broken source skipped with a warning; the CSV still yields candidates.
    assert result.num_candidates >= 1
    assert any("json" in w.lower() or "malformed" in w.lower() for w in result.warnings)


def test_empty_csv_no_records_no_crash():
    result = run([os.path.join(FIX, "empty.csv")], "config/default.json")
    assert result.num_candidates == 0
    assert result.profiles == []


def test_single_source_candidate_is_valid():
    # Anita appears in ONLY the recruiter CSV → still a valid profile.
    result = run([_sample("recruiter_export.csv")], "config/default.json")
    names = [p["full_name"] for p in result.profiles]
    assert "Anita Desai" in names
    anita = [p for p in result.profiles if p["full_name"] == "Anita Desai"][0]
    assert 0.0 <= anita["overall_confidence"] <= 1.0


def test_full_pipeline_output_is_schema_valid():
    inputs = [
        _sample("recruiter_export.csv"), _sample("ats_blob.json"),
        _sample("github_priya.json"), _sample("resume_priya.txt"),
        _sample("recruiter_notes.txt"), _sample("broken.json"),
    ]
    result = run(inputs, "config/default.json")
    cfg = Config.from_dict(json.load(open("config/default.json", encoding="utf-8")))
    warnings = []
    # Re-validate the projected output; must not raise and must keep candidates.
    validated = validate_all(result.profiles, cfg, warnings)
    assert len(validated) == result.num_candidates >= 2
    # every phone is E.164
    for p in validated:
        for ph in p.get("phones", []):
            assert ph.startswith("+")


def test_determinism_two_runs_identical():
    inputs = [
        _sample("recruiter_export.csv"), _sample("ats_blob.json"),
        _sample("github_priya.json"), _sample("resume_priya.txt"),
        _sample("recruiter_notes.txt"), _sample("broken.json"),
    ]
    a = json.dumps(run(inputs, "config/default.json").profiles, sort_keys=True)
    b = json.dumps(run(inputs, "config/default.json").profiles, sort_keys=True)
    assert a == b


def test_garbage_source_unknowns_become_null():
    # broken.json contributes nothing; no invented values leak into output.
    result = run([os.path.join(FIX, "broken.json")], "config/default.json")
    assert result.num_candidates == 0
