"""Make the `src/` layout importable during tests without installation.

Also forces deterministic fallback mode by clearing GROQ_API_KEY for the test
session (spec 10: tests must run with NO network and NO Groq key).
"""
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

os.environ.pop("GROQ_API_KEY", None)
