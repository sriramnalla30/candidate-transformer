"""Source adapter registry. Maps source_type -> adapter instance."""
from .base import SourceAdapter, RawRecord, make_record, set_method, method_for
from .recruiter_csv import RecruiterCSVAdapter
from .ats_json import ATSJsonAdapter
from .github import GitHubAdapter
from .resume import ResumeAdapter
from .recruiter_notes import RecruiterNotesAdapter

# Instantiated once; adapters are stateless.
REGISTRY: dict[str, SourceAdapter] = {
    "recruiter_csv": RecruiterCSVAdapter(),
    "ats_json": ATSJsonAdapter(),
    "github": GitHubAdapter(),
    "resume": ResumeAdapter(),
    "recruiter_notes": RecruiterNotesAdapter(),
}


def get_adapter(source_type: str) -> SourceAdapter | None:
    return REGISTRY.get(source_type)


__all__ = [
    "SourceAdapter",
    "RawRecord",
    "make_record",
    "set_method",
    "method_for",
    "REGISTRY",
    "get_adapter",
]
