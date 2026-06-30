"""Minimal Flask UI (secondary). Same engine as the CLI via pipeline.run()."""
from __future__ import annotations

import json
import os
import sys

# Make src/ importable without installation.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(ROOT, ".env"))
except Exception:  # noqa: BLE001
    pass

from flask import Flask, render_template, request  # noqa: E402

from transformer.pipeline import run, ProjectionError, ValidationError  # noqa: E402

app = Flask(__name__)

SAMPLE_DIR = os.path.join(ROOT, "data", "sample_inputs")
CONFIG_DIR = os.path.join(ROOT, "config")


def _sample_files():
    if not os.path.isdir(SAMPLE_DIR):
        return []
    return sorted(os.listdir(SAMPLE_DIR))


def _config_files():
    if not os.path.isdir(CONFIG_DIR):
        return ["default.json"]
    return sorted(f for f in os.listdir(CONFIG_DIR) if f.endswith(".json"))


@app.route("/", methods=["GET"])
def index():
    return render_template(
        "index.html",
        files=_sample_files(),
        configs=_config_files(),
        selected=[],
        chosen_config="default.json",
        result_json=None,
        table=None,
        warnings=None,
        error=None,
    )


@app.route("/run", methods=["POST"])
def run_pipeline():
    selected = request.form.getlist("inputs")
    chosen_config = request.form.get("config", "default.json")

    error = None
    result_json = None
    table = None
    warnings = None

    if not selected:
        error = "Please select at least one input file."
    else:
        inputs = [os.path.join(SAMPLE_DIR, f) for f in selected]
        config_path = os.path.join(CONFIG_DIR, chosen_config)
        try:
            result = run(inputs, config_path)
            result_json = json.dumps(result.profiles, indent=2, ensure_ascii=False)
            warnings = result.warnings
            table = [
                {
                    "name": p.get("full_name") or p.get("primary_email") or "(unknown)",
                    "confidence": p.get("overall_confidence"),
                }
                for p in result.profiles
            ]
        except (ProjectionError, ValidationError) as exc:
            error = f"Config/schema error (error mode): {exc}"
        except Exception as exc:  # noqa: BLE001
            error = f"Unexpected error: {exc}"

    return render_template(
        "index.html",
        files=_sample_files(),
        configs=_config_files(),
        selected=selected,
        chosen_config=chosen_config,
        result_json=result_json,
        table=table,
        warnings=warnings,
        error=error,
    )


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
