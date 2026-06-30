"""Phase 6 — projection + validation tests (spec 10)."""
import pytest

from transformer.schema import Config, resolve, MISSING
from transformer.project import project, ProjectionError
from transformer.validate import validate, ValidationError


CANON = {
    "candidate_id": "cand_x",
    "full_name": "Priya Sharma",
    "emails": ["priya@x.com", "p2@y.com"],
    "phones": ["+919876543210"],
    "location": {"city": "Bengaluru", "region": None, "country": "IN"},
    "links": {"linkedin": None, "github": "https://github.com/p", "portfolio": None, "other": []},
    "headline": "Senior Software Engineer",
    "years_experience": 6,
    "skills": [
        {"name": "Python", "confidence": 0.9, "sources": ["resume"]},
        {"name": "Go", "confidence": 0.8, "sources": ["github"]},
    ],
    "experience": [{"company": "Flipkart", "title": "SSE", "start": "2021-01", "end": "present", "summary": None}],
    "education": [],
    "provenance": [{"field": "full_name", "source": "recruiter_csv", "method": "exact", "value": "Priya Sharma"}],
    "overall_confidence": 0.91,
}


def _cfg(fields, **kw):
    data = {"fields": fields}
    data.update(kw)
    return Config.from_dict(data)


def test_default_full_shape():
    cfg = _cfg(
        [{"path": "full_name", "type": "string"}, {"path": "emails", "type": "string[]"},
         {"path": "skills", "type": "object[]"}],
        include_confidence=True, include_provenance=True, on_missing="null",
    )
    out = project(CANON, cfg)
    assert out["full_name"] == "Priya Sharma"
    assert out["emails"] == ["priya@x.com", "p2@y.com"]
    assert isinstance(out["skills"][0], dict)
    assert out["overall_confidence"] == 0.91
    assert "provenance" in out


def test_custom_renames_and_from_paths():
    cfg = _cfg([
        {"path": "full_name", "from": "full_name", "type": "string", "required": True},
        {"path": "primary_email", "from": "emails[0]", "type": "string", "required": True},
        {"path": "phone", "from": "phones[0]", "type": "string", "normalize": "E164"},
        {"path": "skills", "from": "skills[].name", "type": "string[]", "normalize": "canonical"},
        {"path": "city", "from": "location.city", "type": "string"},
    ], include_provenance=False, include_confidence=True)
    out = project(CANON, cfg)
    assert out["primary_email"] == "priya@x.com"
    assert out["phone"] == "+919876543210"
    assert out["skills"] == ["Python", "Go"]
    assert out["city"] == "Bengaluru"
    assert "provenance" not in out
    assert "overall_confidence" in out


def test_on_missing_null_omit_error():
    fields = [{"path": "portfolio", "from": "links.portfolio", "type": "string", "required": True}]
    # null
    out = project(CANON, _cfg(fields, on_missing="null"))
    assert out["portfolio"] is None
    # omit
    out = project(CANON, _cfg(fields, on_missing="omit"))
    assert "portfolio" not in out
    # error
    with pytest.raises(ProjectionError):
        project(CANON, _cfg(fields, on_missing="error"))


def test_resolver_edge_cases():
    assert resolve(CANON, "emails[0]") == "priya@x.com"
    assert resolve(CANON, "location.city") == "Bengaluru"
    assert resolve(CANON, "skills[].name") == ["Python", "Go"]
    assert resolve(CANON, "emails[9]") is MISSING  # out of range, no crash


def test_validation_type_and_required():
    cfg = _cfg([{"path": "full_name", "type": "string", "required": True}],
               on_missing="null")
    assert validate({"full_name": "Priya Sharma"}, cfg)["full_name"] == "Priya Sharma"

    # error mode + missing required → raises
    cfg_err = _cfg([{"path": "full_name", "type": "string", "required": True}],
                   on_missing="error")
    with pytest.raises(ValidationError):
        validate({"full_name": None}, cfg_err)


def test_validation_degrades_bad_type():
    cfg = _cfg([{"path": "years_experience", "type": "number"}], on_missing="null")
    warnings = []
    out = validate({"years_experience": "not a number"}, cfg, warnings)
    assert out["years_experience"] is None  # degraded, not crashed
    assert warnings
