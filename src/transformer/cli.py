"""Command-line surface (primary). Thin wrapper over pipeline.run()."""
from __future__ import annotations

import argparse
import json
import os
import sys

# Load .env (GROQ_API_KEY etc.) if python-dotenv is available; safe if absent.
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:  # noqa: BLE001
    pass

from .pipeline import run, ProjectionError, ValidationError

DEFAULT_CONFIG = os.path.join("config", "default.json")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="transformer.cli",
        description="Multi-Source Candidate Data Transformer — build canonical profiles.",
    )
    p.add_argument("--inputs", nargs="+", required=True,
                   help="Input file paths/URLs. Override type with 'path:type'.")
    p.add_argument("--config", default=None,
                   help=f"Config JSON path (default: {DEFAULT_CONFIG}).")
    p.add_argument("--out", default=None,
                   help="Write JSON here; if omitted, print to stdout.")
    p.add_argument("--pretty", action="store_true", default=True,
                   help="Pretty-print JSON (default).")
    p.add_argument("--compact", dest="pretty", action="store_false",
                   help="Compact JSON (overrides --pretty).")
    p.add_argument("--quiet", action="store_true", help="Suppress warnings on stderr.")
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    config = args.config or DEFAULT_CONFIG

    try:
        result = run(args.inputs, config)
    except (ProjectionError, ValidationError) as exc:
        # Fatal only in on_missing='error' mode.
        print(f"FATAL (error mode): {exc}", file=sys.stderr)
        return 2
    except FileNotFoundError as exc:
        print(f"FATAL: config not found: {exc}", file=sys.stderr)
        return 2

    if not args.quiet:
        print(result.summary(), file=sys.stderr)
        for w in result.warnings:
            print(f"  warning: {w}", file=sys.stderr)

    indent = 2 if args.pretty else None
    text = json.dumps(result.profiles, indent=indent, ensure_ascii=False)

    if args.out:
        os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text)
        if not args.quiet:
            print(f"  wrote {args.out}", file=sys.stderr)
    else:
        print(text)

    return 0  # robustness: success even if some sources were skipped


if __name__ == "__main__":
    raise SystemExit(main())
