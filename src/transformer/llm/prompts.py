"""Fixed extraction prompt + the JSON contract we ask the LLM to return (spec 08)."""

SYSTEM_PROMPT = (
    "You are a precise information extraction engine. Extract ONLY facts explicitly "
    "present in the text. If a field is not clearly stated, use null (or an empty "
    "array). NEVER guess, infer, or invent values. Return a single JSON object that "
    "matches the requested schema exactly. No commentary."
)

# The exact key set the extractor (and adapters) rely on.
SCHEMA_HINT = """Return JSON with EXACTLY these keys:
{
  "full_name": "string | null",
  "headline": "string | null",
  "years_experience": "number | null",
  "skills": ["string", "..."],
  "experience": [{"company": "...", "title": "...", "start": "YYYY-MM | null", "end": "YYYY-MM | present | null", "summary": "..."}],
  "education": [{"institution": "...", "degree": "...", "field": "...", "end_year": 2018}],
  "location": {"city": "string|null", "region": "string|null", "country": "string|null"},
  "phones": ["string", "..."],
  "emails": ["string", "..."]
}"""


def build_user_prompt(text: str, kind: str) -> str:
    return (
        f"{SCHEMA_HINT}\n\n"
        f"The text below is of kind: {kind}.\n"
        f"Extract the fields from it. Remember: use null / empty arrays when unsure.\n\n"
        f"TEXT:\n\"\"\"\n{text}\n\"\"\""
    )
