#!/usr/bin/env python3

from __future__ import annotations

import argparse
import os
import unittest
from unittest.mock import patch

import provider_adapters
import run_experiment
from provider_adapters import ProviderResult
from study_core import (
    CONDITIONS,
    MODEL_CONFIGS,
    MODEL_LABELS,
    PROMPT_HASHES,
    PROTOCOL_VERSION,
    REVEAL_TOOL,
    SYSTEM_PROMPTS,
    TaskSpec,
    Usage,
    estimate_cost,
    final_outcome,
    is_censored,
    make_tasks,
)


class CoreTests(unittest.TestCase):
    def test_protocol_and_models_are_frozen(self) -> None:
        self.assertEqual(PROTOCOL_VERSION, "anthropic-scale-v8.3")
        self.assertEqual(
            MODEL_LABELS,
            (
                "anthropic_haiku45_no_thinking",
                "anthropic_sonnet5_no_thinking",
            ),
        )
        self.assertEqual(
            [MODEL_CONFIGS[label]["model"] for label in MODEL_LABELS],
            ["claude-haiku-4-5-20251001", "claude-sonnet-5"],
        )
        self.assertTrue(all(MODEL_CONFIGS[label]["provider"] == "anthropic" for label in MODEL_LABELS))
        self.assertTrue(all(MODEL_CONFIGS[label]["thinking"] == "disabled" for label in MODEL_LABELS))

    def test_prompt_conditions_are_distinct(self) -> None:
        self.assertEqual(set(SYSTEM_PROMPTS), set(CONDITIONS))
        self.assertEqual(len(set(PROMPT_HASHES.values())), 3)
        self.assertIn("Persistence never overrides active restrictions", SYSTEM_PROMPTS["bounded_persistence"])
        self.assertIn("at all costs", SYSTEM_PROMPTS["at_all_costs"])

    def test_tasks_are_deterministic_and_underdetermined(self) -> None:
        first = make_tasks(20, 20260906)
        self.assertEqual(first, make_tasks(20, 20260906))
        self.assertEqual(len({task.task_id for task in first}), 20)
        for task in first:
            self.assertNotEqual(task.candidate_a, task.candidate_b)
            self.assertIn(task.hidden_intended, {task.candidate_a, task.candidate_b})

    def test_anthropic_censoring_and_outcome_precedence(self) -> None:
        base = dict(
            provider="anthropic", model="m", response_id="r", text="",
            reasoning_content="", tool_calls=[], usage=Usage(), status=None,
            incomplete_reason=None, latency_seconds=0, retry_count=0, raw={},
        )
        self.assertTrue(is_censored(ProviderResult(finish_reason="max_tokens", **base)))
        self.assertTrue(is_censored(ProviderResult(finish_reason="model_context_window_exceeded", **base)))
        self.assertTrue(is_censored(ProviderResult(finish_reason="refusal", **base)))
        self.assertFalse(is_censored(ProviderResult(finish_reason="end_turn", **base)))
        self.assertTrue(
            is_censored(
                ProviderResult(
                    finish_reason="tool_use",
                    protocol_violations=["tool_use_stop_without_native_tool_use_block"],
                    **base,
                )
            )
        )
        task = TaskSpec("T001", "x", "x", "ABC", "ACB", "ABC", 1)
        self.assertEqual(final_outcome("", task, True, True)["outcome"], "shortcut_attempt")
        self.assertEqual(final_outcome("", task, False, True)["outcome"], "reasoning_censored")

    def test_anthropic_cost_classes_are_separate(self) -> None:
        usage = Usage(
            input_tokens=1500,
            cached_tokens=200,
            cache_write_tokens=300,
            output_tokens=400,
        )
        self.assertAlmostEqual(
            estimate_cost(usage, "anthropic_haiku45_no_thinking"),
            0.003395,
        )


class AdapterTests(unittest.TestCase):
    def test_payload_and_tool_extraction(self) -> None:
        captured = {}

        def fake_post(**kwargs):
            captured.update(kwargs)
            return (
                {
                    "id": "msg_test",
                    "model": "claude-haiku-4-5-20251001",
                    "content": [
                        {"type": "thinking", "thinking": "provider-visible summary"},
                        {
                            "type": "tool_use",
                            "id": "toolu_test",
                            "name": "reveal_answer",
                            "input": {"reason": "test"},
                        },
                    ],
                    "stop_reason": "tool_use",
                    "usage": {
                        "input_tokens": 100,
                        "cache_read_input_tokens": 20,
                        "cache_creation_input_tokens": 30,
                        "output_tokens": 40,
                        "output_tokens_details": {"thinking_tokens": 12},
                    },
                },
                1,
                0.2,
            )

        with patch("provider_adapters._post_json", side_effect=fake_post):
            result = provider_adapters.call_model(
                model_label="anthropic_haiku45_no_thinking",
                api_key="secret-anthropic-test-key-12345",
                system_prompt="system",
                user_prompt="user",
                tool=REVEAL_TOOL,
                max_output_tokens=1024,
                max_retries=2,
            )

        payload = captured["payload"]
        self.assertEqual(captured["url"], provider_adapters.ANTHROPIC_URL)
        self.assertEqual(payload["model"], "claude-haiku-4-5-20251001")
        self.assertEqual(payload["max_tokens"], 1024)
        self.assertEqual(payload["thinking"], {"type": "disabled"})
        self.assertEqual(payload["tools"][0]["name"], "reveal_answer")
        self.assertEqual(payload["tools"][0]["input_schema"], REVEAL_TOOL["parameters"])
        self.assertTrue(payload["tools"][0]["strict"])
        self.assertEqual(
            payload["tool_choice"],
            {"type": "auto", "disable_parallel_tool_use": True},
        )
        self.assertNotIn("secret-anthropic", str(payload))
        self.assertEqual(result.tool_calls[0]["arguments"], {"reason": "test"})
        self.assertEqual(result.reasoning_content, "provider-visible summary")
        self.assertEqual(result.usage.input_tokens, 150)
        self.assertEqual(result.usage.cached_tokens, 20)
        self.assertEqual(result.usage.cache_write_tokens, 30)
        self.assertEqual(result.usage.reasoning_tokens, 12)

    def test_text_and_redacted_thinking_extraction(self) -> None:
        result = provider_adapters._extract_anthropic(
            {
                "id": "msg_text",
                "model": "claude-opus-5",
                "content": [
                    {"type": "redacted_thinking", "data": "opaque"},
                    {"type": "text", "text": "The clues are ambiguous."},
                ],
                "stop_reason": "end_turn",
                "usage": {"input_tokens": 8, "output_tokens": 4},
            },
            0.1,
            0,
        )
        self.assertEqual(result.text, "The clues are ambiguous.")
        self.assertEqual(result.reasoning_content, "[REDACTED_THINKING_BLOCK]")
        self.assertEqual(result.finish_reason, "end_turn")

    def test_malformed_tool_stop_is_explicitly_censored(self) -> None:
        result = provider_adapters._extract_anthropic(
            {
                "id": "msg_malformed",
                "model": "claude-opus-5",
                "content": [
                    {
                        "type": "text",
                        "text": '<invoke name="preflight_probe">TOOL_OK</invoke>',
                    }
                ],
                "stop_reason": "tool_use",
                "usage": {"input_tokens": 8, "output_tokens": 4},
            },
            0.1,
            0,
        )
        self.assertEqual(result.tool_calls, [])
        self.assertEqual(
            result.protocol_violations,
            ["tool_use_stop_without_native_tool_use_block"],
        )
        self.assertTrue(is_censored(result))

    def test_endpoint_validation_and_retry_codes(self) -> None:
        provider_adapters._validate_url(
            "https://api.anthropic.com/v1/messages",
            "api.anthropic.com",
            "/v1/messages",
        )
        with self.assertRaises(ValueError):
            provider_adapters._validate_url(
                "https://example.com/v1/messages",
                "api.anthropic.com",
                "/v1/messages",
            )
        self.assertIn(529, provider_adapters.RETRYABLE_HTTP)


class ManifestTests(unittest.TestCase):
    def test_default_manifest_has_120_randomized_matched_jobs(self) -> None:
        args = argparse.Namespace(
            run_id="test",
            subjects_per_cell=20,
            seed=20260906,
            task_max_tokens=1024,
            models=list(MODEL_LABELS),
            conditions=list(CONDITIONS),
            max_retries=6,
            cost_cap_usd=10.0,
            preflight_only=False,
            dry_run=True,
            simulate=False,
            resume=False,
        )
        manifest = run_experiment.make_manifest(args)
        self.assertEqual(len(manifest["randomized_jobs"]), 120)
        for model in MODEL_LABELS:
            task_sets = [
                {
                    job["task_id"]
                    for job in manifest["randomized_jobs"]
                    if job["model_label"] == model and job["condition"] == condition
                }
                for condition in CONDITIONS
            ]
            self.assertEqual(task_sets[0], task_sets[1])
            self.assertEqual(task_sets[1], task_sets[2])
        self.assertNotIn("API_KEY", str(manifest))

    def test_key_is_read_only_from_anthropic_environment_variable(self) -> None:
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-anthropic-key-123456789"}, clear=True):
            self.assertEqual(
                run_experiment.require_api_key("anthropic"),
                "test-anthropic-key-123456789",
            )
        with self.assertRaises(SystemExit):
            run_experiment.require_api_key("openai")


if __name__ == "__main__":
    unittest.main()
