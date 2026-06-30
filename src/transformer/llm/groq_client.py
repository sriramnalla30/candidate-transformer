"""Thin wrapper around the Groq chat API. Returns parsed JSON or raises GroqError."""
from __future__ import annotations

import json
import os

from .prompts import SYSTEM_PROMPT, build_user_prompt


class GroqError(Exception):
    """Any failure talking to Groq (missing key, network, non-JSON, rate-limit)."""


# Loaded lazily so importing this module never requires a key or network.
_PRIMARY_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
_FALLBACK_MODEL = "llama-3.1-8b-instant"


def has_api_key() -> bool:
    return bool(os.getenv("GROQ_API_KEY", "").strip())


def call_groq(text: str, kind: str) -> dict:
    """Call Groq with temperature=0 + JSON mode. Raises GroqError on any problem."""
    if not has_api_key():
        raise GroqError("no GROQ_API_KEY set")
    try:
        from groq import Groq
    except Exception as exc:  # noqa: BLE001
        raise GroqError(f"groq SDK unavailable: {exc}") from exc

    client = Groq(api_key=os.environ["GROQ_API_KEY"])
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": build_user_prompt(text, kind)},
    ]
    last_exc: Exception | None = None
    for model in (_PRIMARY_MODEL, _FALLBACK_MODEL):
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0,
                response_format={"type": "json_object"},
            )
            content = resp.choices[0].message.content
            return json.loads(content)
        except Exception as exc:  # noqa: BLE001 — try fallback model, then give up
            last_exc = exc
            continue
    raise GroqError(f"Groq call failed: {last_exc}")
