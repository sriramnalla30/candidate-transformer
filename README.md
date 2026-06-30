# Multi-Source Candidate Data Transformer

Turns messy candidate data from many sources into one clean, deduplicated, confidence-scored
canonical profile per candidate — with full provenance and a runtime-configurable output.

> **Design doc:** [`NallaSriRam_sriramnalla30@gmail.com_Eightfold.pdf`](./NallaSriRam_sriramnalla30@gmail.com_Eightfold.pdf) (one-page Stage-1 design).
> **Produced output on the sample inputs** is checked in under [`examples/`](./examples) — `profiles_default.json` (default schema) and `profiles_custom.json` (custom config), regenerable via `python run_demo.py`.

## What it does
- Ingests **structured** sources (Recruiter CSV, ATS JSON) and **unstructured** sources (Resume
  `.txt`/`.pdf`, Recruiter notes, GitHub profile).
- Pipeline: `detect → extract → normalize → merge → confidence → project → validate`.
- Normalizes phones to E.164, dates to `YYYY-MM`, country to ISO-3166 alpha-2, skills to canonical
  names.
- Merges records into one profile per candidate, records where every value came from (provenance),
  and scores confidence per field + overall.
- Accepts a runtime **config** that reshapes the output (subset, rename, per-field normalize, toggle
  provenance/confidence, `on_missing` policy) — same engine, no code changes.
- Optional **Groq LLM** extraction for unstructured text, with a deterministic fallback so it runs
  with or without an API key.
- Surfaces: a **CLI** (primary) and a **minimal Flask web UI** (secondary).

## Requirements
- Python 3.10+ (developed/verified on 3.14)
- `pip install -r requirements.txt`
- (Optional) A free Groq API key for AI extraction — see "AI mode" below. Without it, the project
  runs in fully deterministic fallback mode.

## Setup
```bash
cd candidate-transformer
python -m venv .venv
# Windows:  .venv\Scripts\activate     (PowerShell: .venv\Scripts\Activate.ps1)
# macOS/Linux:  source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # optional: paste your GROQ_API_KEY into .env
```

> This project uses a `src/` layout with **no install step**. `run_demo.py`, the web UI, and the
> test suite add `src/` to the path automatically. To call the CLI module directly, prefix commands
> with `PYTHONPATH=src` (macOS/Linux) or `$env:PYTHONPATH="src"` (PowerShell).

## Run the demo (default + custom config) — easiest
```bash
python run_demo.py
# writes output/profiles_default.json and output/profiles_custom.json
```

## Run the CLI directly
```bash
# macOS/Linux
PYTHONPATH=src python -m transformer.cli \
  --inputs data/sample_inputs/recruiter_export.csv data/sample_inputs/ats_blob.json \
           data/sample_inputs/github_priya.json data/sample_inputs/resume_priya.txt \
           data/sample_inputs/recruiter_notes.txt data/sample_inputs/broken.json \
  --config config/default.json \
  --out output/profiles_default.json

# compact summary-card output (same engine, different schema):
PYTHONPATH=src python -m transformer.cli \
  --inputs data/sample_inputs/recruiter_export.csv data/sample_inputs/ats_blob.json \
           data/sample_inputs/github_priya.json data/sample_inputs/resume_priya.txt \
           data/sample_inputs/recruiter_notes.txt data/sample_inputs/broken.json \
  --config config/custom_example.json --out output/profiles_custom.json
```
On **Windows PowerShell**, set the path first:
```powershell
$env:PYTHONPATH="src"
python -m transformer.cli --inputs data/sample_inputs/recruiter_export.csv `
  data/sample_inputs/ats_blob.json data/sample_inputs/github_priya.json `
  data/sample_inputs/resume_priya.txt data/sample_inputs/recruiter_notes.txt `
  data/sample_inputs/broken.json --config config/default.json --out output/profiles_default.json
```
CLI flags: `--inputs` (files; override type with `path:type`), `--config`, `--out` (omit → stdout),
`--compact`, `--quiet`. Exit code is `0` even when some sources are skipped (robustness); non-zero
only on a fatal config/schema error in `on_missing: "error"` mode.

## Run the web UI
```bash
python webui/app.py
# open http://localhost:5000  → select inputs + a config → "Build profiles"
```

## Run the tests
```bash
python -m pytest -q          # 42 tests, no network, no Groq key needed
```

## AI mode (Groq, free) vs fallback
- Set `GROQ_API_KEY` in `.env` to enable LLM extraction from resumes/notes/bios
  (model: `llama-3.3-70b-versatile`, `temperature=0`, JSON mode).
- No key → automatic deterministic regex/dictionary fallback. **The deterministic path is fully
  reproducible**; LLM output may vary slightly across model versions. LLM-derived values are tagged
  `method: "llm"` in provenance and given a lower confidence factor, so they can never silently
  overpower a structured source.

## Example output (trimmed — merged "Priya Sharma", default config)
Priya appears in **all five sources** (CSV, ATS, résumé, notes, GitHub) and merges into one profile:
```json
{
  "candidate_id": "cand_443c362250",
  "full_name": "Priya Sharma",
  "emails": ["priya.sharma@gmail.com"],
  "phones": ["+919876543210"],
  "location": { "city": "Bengaluru", "region": null, "country": "IN" },
  "links": {
    "linkedin": null,
    "github": "https://github.com/priyasharma",
    "portfolio": "https://priyasharma.dev",
    "other": []
  },
  "headline": "Senior Software Engineer",
  "years_experience": 6,
  "skills": [
    { "name": "Distributed Systems", "confidence": 1.0, "sources": ["github", "recruiter_notes", "resume"] },
    { "name": "Python", "confidence": 1.0, "sources": ["github", "recruiter_notes", "resume"] },
    { "name": "Go", "confidence": 1.0, "sources": ["github", "recruiter_notes", "resume"] }
  ],
  "experience": [
    { "company": "Flipkart", "title": "Senior Software Engineer", "start": "2021-01", "end": "present", "summary": null },
    { "company": "Amazon",   "title": "Software Engineer",        "start": "2018-07", "end": "2020-12", "summary": null }
  ],
  "education": [
    { "institution": "IIT Bombay", "degree": "B.Tech", "field": "Computer Science", "end_year": 2018 }
  ],
  "provenance": [
    { "field": "full_name", "source": "recruiter_csv", "method": "exact",      "value": "Priya Sharma" },
    { "field": "emails[0]", "source": "recruiter_csv", "method": "normalized", "value": "priya.sharma@gmail.com" },
    { "field": "phones[0]", "source": "recruiter_csv", "method": "normalized", "value": "+919876543210" }
  ],
  "overall_confidence": 0.92
}
```
The **same engine** with `config/custom_example.json` emits a compact card instead:
```json
{
  "full_name": "Priya Sharma",
  "primary_email": "priya.sharma@gmail.com",
  "phone": "+919876543210",
  "current_title": "Senior Software Engineer",
  "years_experience": 6,
  "skills": ["Distributed Systems", "Go", "Python", "Kubernetes", "AWS"],
  "city": "Bengaluru",
  "country": "IN",
  "overall_confidence": 0.92
}
```
Running on the sample set yields **3 candidates**: Priya Sharma (merged from 5 sources), Rahul Verma
(CSV + ATS), and Anita Desai (CSV only, lower confidence). `broken.json` is skipped with a warning —
the run never crashes.

## Design overview
- **Canonical record vs projection:** a rich internal record is built once; the config-driven
  projection layer produces the output, then validation guarantees its shape. This separation is
  what lets one engine serve many downstream schemas.
- **Sources are plug-ins:** each source implements one `SourceAdapter` interface behind a registry,
  so adding a source never touches merge or projection logic.
- **Merge policy:** blocking on email → phone → (full name + country), union-find clustering, then
  conflict resolution by **source trust → cross-source agreement → completeness → recency** (stable).
- **Confidence:** per-field = `trust × method × agreement × normalization`; overall = importance-
  weighted mean over populated fields. Null fields are excluded from the denominator
  (honestly-empty is not penalized as wrong).

## Assumptions & deliberately descoped
- Default phone region is `IN` for bare numbers (configurable via `DEFAULT_PHONE_REGION`).
- Date parsing covers common English formats; **year-only dates store a null month** (the year is
  kept in provenance / `education.end_year`). `present`/`current` is an allowed `end` sentinel.
- **Agreement boost** raises a field's effective score by `+0.15` per extra agreeing source and the
  final confidence is clamped to `[0,1]` (so two agreeing mid-trust sources can overcome one lone
  higher-trust outlier — see `tests/test_merge.py`).
- Skill canonicalization is dictionary-based (explainable), not embeddings; unknown skills are kept
  (title-cased) with slightly lower confidence, never dropped.
- Schema models use **dataclasses + a hand-written validator** (pydantic optional) for maximum
  Python-version portability.
- GitHub supports an **offline local-JSON mode** (used in the demo) and a best-effort **live API
  mode**; on any network/rate-limit error it skips with a warning.
- LinkedIn adapter is designed but not implemented (slots in without merge/projection changes).
- The web UI is intentionally minimal per the assignment's "lower priority" guidance.

## Project layout
```
src/transformer/    engine: detect, sources/, normalize/, merge, confidence, project, validate, pipeline, cli, llm/
config/             default.json + custom_example.json
data/sample_inputs/ demo data (incl. broken.json for robustness)
output/             generated JSON (gitignored)
webui/              minimal Flask UI
tests/              pytest suite (42 tests, incl. robustness + end-to-end)
```

## The seven stages (where to look)
| Stage | Module | Job |
|---|---|---|
| detect | `detect.py` | identify each input's source type (never throws) |
| extract | `sources/*.py` | map each source's shape → `RawRecord` (defensive) |
| normalize | `normalize/` + `normalize/stage.py` | phones/dates/country/skills/emails → canonical formats |
| merge | `merge.py` | blocking + union-find clustering + conflict resolution + provenance |
| confidence | `confidence.py` | per-field + overall confidence |
| project | `project.py` | config-driven output projection (never mutates canonical record) |
| validate | `validate.py` | type + format checks; degrade or raise per `on_missing` |
