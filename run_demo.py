"""Convenience demo: run BOTH the default and custom config on the sample inputs.

Writes output/profiles_default.json and output/profiles_custom.json. This is what
the README and the demo use. Works with or without a GROQ_API_KEY (fallback mode).

    python run_demo.py
"""
from __future__ import annotations

import json
import os
import sys

# Make src/ importable without installation.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:  # noqa: BLE001
    pass

from transformer.pipeline import run  # noqa: E402

SAMPLE_DIR = os.path.join("data", "sample_inputs")
OUT_DIR = "output"

INPUTS = [
    os.path.join(SAMPLE_DIR, "recruiter_export.csv"),
    os.path.join(SAMPLE_DIR, "ats_blob.json"),
    os.path.join(SAMPLE_DIR, "github_priya.json"),
    os.path.join(SAMPLE_DIR, "resume_priya.txt"),
    os.path.join(SAMPLE_DIR, "recruiter_notes.txt"),
    os.path.join(SAMPLE_DIR, "broken.json"),  # robustness: must not crash the run
]

JOBS = [
    ("config/default.json", os.path.join(OUT_DIR, "profiles_default.json")),
    ("config/custom_example.json", os.path.join(OUT_DIR, "profiles_custom.json")),
]


def main() -> int:
    os.makedirs(OUT_DIR, exist_ok=True)
    for config_path, out_path in JOBS:
        result = run(INPUTS, config_path)
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(result.profiles, fh, indent=2, ensure_ascii=False)
        print(f"[{os.path.basename(config_path):20s}] {result.summary()} -> {out_path}")
        for w in result.warnings:
            print(f"    warning: {w}")
    print("\nDone. Inspect the two files in output/.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
