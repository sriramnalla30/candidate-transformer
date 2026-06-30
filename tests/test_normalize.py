"""Phase 2 — normalization tests (spec 10)."""
from transformer.normalize import (
    normalize_phone,
    normalize_date,
    normalize_year,
    normalize_country,
    normalize_skill,
    normalize_email,
    normalize_name,
    is_full_name,
    normalize_url,
)


# --------------------------- phones --------------------------- #
def test_phones_to_e164():
    assert normalize_phone("+91 98765 43210")[0] == "+919876543210"
    assert normalize_phone("9876543210")[0] == "+919876543210"
    assert normalize_phone("098765 43210")[0] == "+919876543210"


def test_phone_garbage_is_none():
    val, ok = normalize_phone("N/A")
    assert val is None and ok is False
    assert normalize_phone("call me")[0] is None
    assert normalize_phone("")[0] is None


def test_phone_us_number():
    assert normalize_phone("+1 (415) 555-0199")[0] == "+14155550199"


# --------------------------- dates --------------------------- #
def test_dates():
    assert normalize_date("Jan 2020") == ("2020-01", True)
    assert normalize_date("2020-01") == ("2020-01", True)
    assert normalize_date("01/2020") == ("2020-01", True)
    assert normalize_date("March 2019") == ("2019-03", True)
    assert normalize_date("present") == ("present", True)
    assert normalize_date("current") == ("present", True)


def test_date_year_only_is_none():
    val, ok = normalize_date("2020")
    assert val is None and ok is False


def test_date_garbage_is_none():
    assert normalize_date("garbage") == (None, False)
    assert normalize_date("") == (None, False)


def test_normalize_year():
    assert normalize_year(2018) == (2018, True)
    assert normalize_year("Graduated 2018") == (2018, True)
    assert normalize_year("nope")[1] is False


# --------------------------- country --------------------------- #
def test_country():
    assert normalize_country("India") == ("IN", True)
    assert normalize_country("USA") == ("US", True)
    assert normalize_country("United Kingdom") == ("GB", True)
    assert normalize_country("IN") == ("IN", True)


def test_country_unknown_is_none():
    val, ok = normalize_country("Narnia")
    assert val is None and ok is False


# --------------------------- skills --------------------------- #
def test_skills_canonical():
    assert normalize_skill("js") == ("JavaScript", True)
    assert normalize_skill("PYTHON") == ("Python", True)
    assert normalize_skill("k8s") == ("Kubernetes", True)


def test_skill_unknown_kept_unmapped():
    name, mapped = normalize_skill("FooLang")
    assert name == "Foolang"
    assert mapped is False


# --------------------------- emails --------------------------- #
def test_emails():
    assert normalize_email("  Priya.Sharma@GMAIL.com ") == ("priya.sharma@gmail.com", True)
    assert normalize_email("not-an-email")[0] is None
    assert normalize_email("oops@,,")[0] is None


# --------------------------- names --------------------------- #
def test_names():
    assert normalize_name("  priya   sharma ") == ("Priya Sharma", True)
    assert is_full_name("Priya Sharma") is True
    assert is_full_name("Priya S.") is False
    assert is_full_name("Priya") is False


# --------------------------- urls --------------------------- #
def test_urls():
    url, kind = normalize_url("github.com/priyasharma")
    assert url == "https://github.com/priyasharma"
    assert kind == "github"
    url, kind = normalize_url("https://priyasharma.dev")
    assert kind == "portfolio"
