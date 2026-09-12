#!/usr/bin/env python3
"""Run the isolated Gemini tier panel on the frozen impossible add-two task."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
BASE = ROOT.parent / "impossible_add2_v10"
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

import analyze as base_analyze  # noqa: E402
import provider_adapters as base_adapters  # noqa: E402
import run_experiment as base_runner  # noqa: E402
import study_core as base_core  # noqa: E402

from analyze_gemini import add_tier_analysis  # noqa: E402
from config import MODEL_CONFIGS, MODEL_LABELS, PROTOCOL_VERSION  # noqa: E402
from gemini_adapter import call_model, gemini_is_censored  # noqa: E402


def configure_base() -> None:
    """Patch only this process; the frozen v10.2 source and live run stay untouched."""
    base_core.PROTOCOL_VERSION = PROTOCOL_VERSION
    base_core.MODEL_CONFIGS = MODEL_CONFIGS
    base_core.MODEL_LABELS = MODEL_LABELS

    base_adapters.MODEL_CONFIGS = MODEL_CONFIGS

    base_analyze.MODEL_CONFIGS = MODEL_CONFIGS

    base_runner.PROTOCOL_VERSION = PROTOCOL_VERSION
    base_runner.MODEL_CONFIGS = MODEL_CONFIGS
    base_runner.MODEL_LABELS = MODEL_LABELS
    base_runner.KEY_VARIABLES = {"gemini": "GEMINI_API_KEY"}
    base_runner.ROOT = ROOT
    base_runner.RUNS_ROOT = ROOT / "runs"
    base_runner.call_model = call_model
    base_runner.is_censored = gemini_is_censored


def main() -> int:
    configure_base()
    code = base_runner.main()
    if code == 0:
        try:
            args = base_runner.parse_args()
        except SystemExit:
            return code
        run_dir = ROOT / "runs" / args.run_id
        if (run_dir / "summary.json").exists():
            add_tier_analysis(run_dir)
    return code


if __name__ == "__main__":
    raise SystemExit(main())

