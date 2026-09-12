#!/usr/bin/env python3
"""Offline tests for the Gemini adapter and isolated experiment wrapper."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parent
BASE = ROOT.parent / "impossible_add2_v10"
sys.path.insert(0, str(BASE))
sys.path.insert(0, str(ROOT))

import gemini_adapter  # noqa: E402
import run_gemini_experiment  # noqa: E402
from config import MODEL_CONFIGS, MODEL_LABELS, PROTOCOL_VERSION  # noqa: E402
from study_core import SUBJECT_TOOLS  # noqa: E402


class GeminiAdapterTest(unittest.TestCase):
    def test_payload_and_extraction(self) -> None:
        response = {
            "id": "interaction-1",
            "model": "gemini-3.8-flash",
            "status": "requires_action",
            "steps": [
                {
                    "type": "thought",
                    "summary": [{"type": "text", "text": "short summary"}],
                    "signature": "opaque",
                },
                {"type": "function_call", "name": "set_value", "arguments": {"value": 7}, "id": "call-1"},
            ],
            "usage": {
                "total_input_tokens": 100,
                "total_cached_tokens": 10,
                "total_output_tokens": 25,
                "total_thought_tokens": 30,
            },
        }
        with patch.object(gemini_adapter, "_post_json", return_value=(response, 1, 0.2)) as post:
            result = gemini_adapter.call_model(
                model_label="gemini38_flash_low",
                api_key="secret-key-that-is-long-enough",
                system_prompt="system",
                user_prompt="user",
                tools=SUBJECT_TOOLS,
                max_output_tokens=4096,
                max_retries=6,
            )
        request = post.call_args.kwargs
        payload = request["payload"]
        self.assertEqual(payload["model"], "gemini-3.8-flash")
        self.assertFalse(payload["store"])
        self.assertEqual(payload["generation_config"]["thinking_level"], "low")
        self.assertEqual(payload["generation_config"]["thinking_summaries"], "none")
        self.assertEqual(payload["generation_config"]["tool_choice"], "auto")
        self.assertEqual({tool["name"] for tool in payload["tools"]}, {"add_two", "set_value"})
        self.assertFalse(request["bearer_authorization"])
        self.assertEqual(request["extra_headers"]["x-goog-api-key"], "secret-key-that-is-long-enough")
        self.assertEqual(result.tool_calls[0]["arguments"], {"value": 7})
        self.assertEqual(result.usage.output_tokens, 55)
        self.assertEqual(result.usage.reasoning_tokens, 30)
        self.assertFalse(gemini_adapter.gemini_is_censored(result))

    def test_incomplete_is_censored(self) -> None:
        response = {
            "id": "interaction-2",
            "model": "gemini-3.5-flash-lite",
            "status": "incomplete",
            "steps": [],
            "usage": {},
        }
        result = gemini_adapter._extract_gemini(response, 0.1, 0)
        self.assertTrue(gemini_adapter.gemini_is_censored(result))


class WrapperTest(unittest.TestCase):
    def test_isolated_manifest_has_216_subjects(self) -> None:
        run_gemini_experiment.configure_base()
        runner = run_gemini_experiment.base_runner
        argv = [
            "run_gemini_experiment.py", "--run-id", "test", "--dry-run",
            "--chains-per-cell", "3", "--subjects-per-chain", "4",
            "--cost-cap-usd", "20",
        ]
        with patch.object(sys, "argv", argv):
            args = runner.parse_args()
        manifest = runner.make_manifest(args)
        self.assertEqual(manifest["protocol_version"], PROTOCOL_VERSION)
        self.assertEqual(manifest["models"], list(MODEL_LABELS))
        self.assertEqual(len(manifest["randomized_jobs"]), 216)
        self.assertEqual(manifest["model_configs"], MODEL_CONFIGS)
        self.assertEqual(runner.RUNS_ROOT, ROOT / "runs")

    def test_adapter_does_not_modify_base_files(self) -> None:
        frozen = (BASE / "FROZEN_SHA256.txt").read_text(encoding="utf-8")
        run_gemini_experiment.configure_base()
        self.assertEqual((BASE / "FROZEN_SHA256.txt").read_text(encoding="utf-8"), frozen)


if __name__ == "__main__":
    unittest.main()

