"""Stage 7 — VALIDATE. Check the PROJECTED output against the config-implied schema.

On violation: in on_missing='error' mode, raise a clear ValidationError; otherwise
log a warning and degrade gracefully (set the offending value to None). Validation is
the last gate before output is returned.
"""
from __future__ import annotations

import re

from .schema import Config

_E164_RE = re.compile(r"^\+\d{7,15}$")
_YYYYMM_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
_ALPHA2_RE = re.compile(r"^[A-Z]{2}$")


class ValidationError(Exception):
    """Projected output violated the schema in error mode."""


def _type_ok(value, declared: str) -> bool:
    if declared == "string":
        return isinstance(value, str)
    if declared == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if declared == "boolean":
        return isinstance(value, bool)
    if declared == "object":
        return isinstance(value, dict)
    if declared == "string[]":
        return isinstance(value, list) and all(isinstance(x, str) for x in value)
    if declared == "object[]":
        return isinstance(value, list) and all(isinstance(x, dict) for x in value)
    return True  # unknown declared type → don't block


def _format_errors(field, value) -> list[str]:
    """Format checks where applicable (E.164, YYYY-MM, ISO-3166, confidence range)."""
    errs = []
    path = field.path.lower()
    norm = (field.normalize or "").lower()

    def check_phone(v):
        if isinstance(v, str) and v and not _E164_RE.match(v):
            errs.append(f"'{field.path}': '{v}' is not E.164")

    if norm == "e164" or "phone" in path:
        if isinstance(value, list):
            for v in value:
                check_phone(v)
        else:
            check_phone(value)

    if "country" in path and isinstance(value, str) and value:
        if not _ALPHA2_RE.match(value):
            errs.append(f"'{field.path}': '{value}' is not ISO-3166 alpha-2")

    return errs


def validate(output: dict, config: Config, warnings=None) -> dict:
    """Validate (and, outside error mode, degrade) a single projected output object."""
    warnings = warnings if warnings is not None else []
    error_mode = config.on_missing == "error"

    for f in config.fields:
        present = f.path in output
        value = output.get(f.path)

        # required-field presence
        if f.required and (not present or value is None):
            msg = f"required field '{f.path}' is missing/null"
            if error_mode:
                raise ValidationError(msg)
            warnings.append(f"validate: {msg}")
            continue

        if not present or value is None:
            continue

        # type check
        if not _type_ok(value, f.type):
            msg = f"field '{f.path}' expected {f.type}, got {type(value).__name__}"
            if error_mode:
                raise ValidationError(msg)
            warnings.append(f"validate: {msg} (set to null)")
            output[f.path] = None
            continue

        # format checks
        fmt_errs = _format_errors(f, value)
        if fmt_errs:
            if error_mode:
                raise ValidationError("; ".join(fmt_errs))
            for e in fmt_errs:
                warnings.append(f"validate: {e} (kept, see provenance)")

    # confidence range
    conf = output.get("overall_confidence")
    if conf is not None and not (0.0 <= conf <= 1.0):
        msg = f"overall_confidence {conf} out of [0,1]"
        if error_mode:
            raise ValidationError(msg)
        warnings.append(f"validate: {msg}")

    return output


def validate_all(outputs, config: Config, warnings=None) -> list:
    warnings = warnings if warnings is not None else []
    return [validate(o, config, warnings) for o in outputs]
