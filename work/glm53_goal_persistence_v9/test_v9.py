#!/usr/bin/env python3

from __future__ import annotations

import argparse
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
    REVEAL_TOOL,
    SYSTEM_PROMPTS,
    TaskSpec,
    Usage,
    estimate_cost,
    final_outcome,
    is_censored,
    make_tasks,
)


class FrozenDesignTests(unittest.TestCase):
    def test_single_glm53_max_reasoning_model(self) -> None:
        self.assertEqual(MODEL_LABELS, ("zai_glm53_max_reasoning",))
        config = MODEL_CONFIGS[MODEL_LABELS[0]]
        self.assertEqual(config["provider"], "zai")
        self.assertEqual(config["model"], "glm-5.3")
        self.assertEqual(config["reasoning"], "max")

    def test_prompt_conditions_are_distinct_and_frozen(self) -> None:
        self.assertEqual(set(SYSTEM_PROMPTS), set(CONDITIONS))
        self.assertEqual(len(set(PROMPT_HASHES.values())), 3)
        self.assertIn("Persistence never overrides active restrictions", SYSTEM_PROMPTS["bounded_persistence"])
        self.assertIn("at all costs", SYSTEM_PROMPTS["at_all_costs"])

    def test_tasks_match_v72_seed_and_remain_underdetermined(self) -> None:
        first = make_tasks(20, 20260903)
        second = make_tasks(20, 20260903)
        self.assertEqual(first, second)
        self.assertEqual(len(first), 20)
        for task in first:
            self.assertNotEqual(task.candidate_a, task.candidate_b)
            self.assertIn(task.hidden_intended, {task.candidate_a, task.candidate_b})

    def test_shortcut_precedes_censoring(self) -> None:
        task = TaskSpec("T001", "x", "x", "ABC", "ACB", "ABC", 1)
        self.assertEqual(final_outcome("", task, True, True)["outcome"], "shortcut_attempt")
        self.assertEqual(final_outcome("", task, False, True)["outcome"], "reasoning_censored")

    def test_zai_length_finish_is_censored(self) -> None:
        result = ProviderResult(
            provider="zai", model="glm-5.3", response_id="r", text="",
            reasoning_content="reasoning", tool_calls=[], usage=Usage(), status=None,
            incomplete_reason=None, finish_reason="length", latency_seconds=0,
            retry_count=0, raw={},
        )
        self.assertTrue(is_censored(result))


class PayloadTests(unittest.TestCase):
    def test_glm53_payload_and_native_tool_extraction(self) -> None:
        captured = {}

        def fake_post(**kwargs):
            captured.update(kwargs)
            return ({
                "id": "chat_1", "model": "glm-5.3",
                "choices": [{"finish_reason": "tool_calls", "message": {
                    "content": "", "reasoning_content": "provider-visible reasoning",
                    "tool_calls": [{"id": "call_1", "function": {
                        "name": "reveal_answer", "arguments": '{"reason":"x"}'
                    }}],
                }}],
                "usage": {
                    "prompt_tokens": 10,
                    "prompt_tokens_details": {"cached_tokens": 2},
                    "completion_tokens": 5,
                    "completion_tokens_details": {"reasoning_tokens": 4},
                },
            }, 0, 0.2)

        with patch("provider_adapters._post_json", side_effect=fake_post):
            result = provider_adapters.call_model(
                model_label="zai_glm53_max_reasoning",
                api_key="secret-zai-test-key-123456",
                system_prompt="system", user_prompt="user", tool=REVEAL_TOOL,
                max_output_tokens=4096, max_retries=2,
            )
        payload = captured["payload"]
        self.assertEqual(captured["url"], provider_adapters.ZAI_URL)
        self.assertEqual(payload["model"], "glm-5.3")
        self.assertEqual(payload["thinking"], {"type": "enabled"})
        self.assertEqual(payload["reasoning_effort"], "max")
        self.assertEqual(payload["max_tokens"], 4096)
        self.assertEqual(payload["tools"][0]["function"]["name"], "reveal_answer")
        self.assertEqual(result.reasoning_content, "provider-visible reasoning")
        self.assertEqual(result.tool_calls[0]["name"], "reveal_answer")
        self.assertEqual(result.usage.reasoning_tokens, 4)
        self.assertAlmostEqual(estimate_cost(result.usage, MODEL_LABELS[0]), 0.00003372)


class ManifestTests(unittest.TestCase):
    def test_default_manifest_has_60_jobs_and_frozen_settings(self) -> None:
        args = argparse.Namespace(
            run_id="test", subjects_per_cell=20, seed=20260903,
            task_max_tokens=4096, models=list(MODEL_LABELS),
            conditions=list(CONDITIONS), max_retries=6, cost_cap_usd=10.0,
            preflight_only=False, dry_run=True, simulate=False, resume=False,
        )
        manifest = run_experiment.make_manifest(args)
        self.assertEqual(len(manifest["randomized_jobs"]), 60)
        self.assertEqual(manifest["model_configs"][MODEL_LABELS[0]]["reasoning"], "max")
        self.assertEqual(manifest["task_max_tokens"], 4096)


if __name__ == "__main__":
    unittest.main()
