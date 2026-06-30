"""Stage 6 — PROJECT. Config-driven output projection. NEVER mutates the canonical record."""
from __future__ import annotations

from .schema import Config, resolve, MISSING
from .normalize import normalize_phone, normalize_skill


class ProjectionError(Exception):
    """Raised in on_missing='error' mode when a required field is absent."""


def _apply_normalize(value, norm):
    """Apply an optional per-field normalization override during projection."""
    if not norm or norm == "none":
        return value
    if norm == "E164":
        if isinstance(value, str):
            return normalize_phone(value)[0] or value
        if isinstance(value, list):
            return [normalize_phone(v)[0] or v if isinstance(v, str) else v for v in value]
        return value
    if norm == "canonical":
        if isinstance(value, str):
            return normalize_skill(value)[0] or value
        if isinstance(value, list):
            out = []
            for v in value:
                if isinstance(v, str):
                    out.append(normalize_skill(v)[0] or v)
                else:
                    out.append(v)  # already-canonical skill objects pass through
            return out
        return value
    # iso-date and anything else: the canonical record is already normalized.
    return value


def project(canonical_dict: dict, config: Config, warnings=None) -> dict:
    """Build one OUTPUT object from a canonical profile dict per the config."""
    warnings = warnings if warnings is not None else []
    output: dict = {}

    for f in config.fields:
        raw = resolve(canonical_dict, f.source_path)
        # Treat both a truly-absent path and a present-but-null value as "missing".
        if raw is MISSING or raw is None:
            if config.on_missing == "omit":
                continue
            if config.on_missing == "error" and f.required:
                raise ProjectionError(
                    f"required field '{f.path}' is missing (from '{f.source_path}')"
                )
            output[f.path] = None
            continue
        output[f.path] = _apply_normalize(raw, f.normalize)

    if config.include_confidence:
        output["overall_confidence"] = canonical_dict.get("overall_confidence")
    if config.include_provenance:
        output["provenance"] = canonical_dict.get("provenance", [])

    return output


def project_all(canonical_dicts, config: Config, warnings=None) -> list:
    """Project a list of canonical profiles independently (robust per-candidate)."""
    warnings = warnings if warnings is not None else []
    out = []
    for cd in canonical_dicts:
        try:
            out.append(project(cd, config, warnings))
        except ProjectionError:
            raise  # error mode must propagate
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"project: failed on candidate {cd.get('candidate_id','?')}: {exc}")
    return out
