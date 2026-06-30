"""pipeline.run(inputs, config) — wires all stages with per-stage robustness.

detect → extract → normalize → merge → confidence → project → validate

Each stage is wrapped so a failing source/item removes only its own contribution
and the run still produces output (spec 02 robustness rules). Returns a RunResult
that both the CLI and the web UI consume.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field as dc_field

from .detect import detect
from .sources import get_adapter
from .normalize.stage import normalize_records
from .merge import build_profiles
from .project import project_all, ProjectionError
from .validate import validate_all, ValidationError
from .schema import Config


@dataclass
class RunResult:
    profiles: list           # list[dict] — projected + validated output objects
    warnings: list = dc_field(default_factory=list)
    num_inputs: int = 0
    num_candidates: int = 0

    def summary(self) -> str:
        return (
            f"{self.num_inputs} inputs -> {self.num_candidates} candidates, "
            f"{len(self.warnings)} warnings"
        )


def load_config(config) -> Config:
    """Accept a Config, a dict, or a path to a JSON config file."""
    if isinstance(config, Config):
        return config
    if isinstance(config, dict):
        return Config.from_dict(config)
    if config is None:
        return Config.from_dict({"fields": [], "include_confidence": True,
                                 "include_provenance": True, "on_missing": "null"})
    with open(config, "r", encoding="utf-8") as fh:
        return Config.from_dict(json.load(fh))


def run(inputs, config=None) -> RunResult:
    """Run the full pipeline. `inputs` is a list of path/URL descriptors."""
    warnings: list[str] = []
    cfg = load_config(config)

    # Stage 1 — DETECT
    detected = detect(inputs, warnings)

    # Stage 2 — EXTRACT (assign a stable global index for deterministic tie-breaks)
    raw_records = []
    idx = 0
    for ds in detected:
        adapter = get_adapter(ds.source_type)
        if adapter is None:
            warnings.append(f"extract: no adapter for type '{ds.source_type}' (skipped)")
            continue
        try:
            recs = adapter.extract(ds.handle, warnings)
        except Exception as exc:  # noqa: BLE001 — a source failure must not crash the run
            warnings.append(f"extract: {ds.source_type} failed on {ds.handle}: {exc}")
            recs = []
        for r in recs:
            r["_index"] = idx
            idx += 1
            raw_records.append(r)

    # Stage 3 — NORMALIZE
    normalized = normalize_records(raw_records, warnings)

    # Stage 4+5 — MERGE + CONFIDENCE
    profiles = build_profiles(normalized, warnings)
    num_candidates = len(profiles)
    canonical_dicts = [p.to_dict() for p in profiles]

    # Stage 6 — PROJECT  (error mode propagates as a fatal config/schema error)
    projected = project_all(canonical_dicts, cfg, warnings)

    # Stage 7 — VALIDATE
    validated = validate_all(projected, cfg, warnings)

    return RunResult(
        profiles=validated,
        warnings=warnings,
        num_inputs=len(inputs),
        num_candidates=num_candidates,
    )


__all__ = ["run", "RunResult", "load_config", "ProjectionError", "ValidationError"]
