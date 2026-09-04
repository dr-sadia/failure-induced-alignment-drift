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
    MODEL_LABELS,
    PROMPT_HASHES,
    REVEAL_TOOL,
    SYSTEM_PROMPTS,
    TaskSpec,
    Usage,
    final_outcome,
    estimate_cost,
    fisher_exact_two_sided,
    holm_adjust,
    is_censored,
    make_tasks,
)


class CoreTests(unittest.TestCase):
    def test_prompt_conditions_are_distinct_and_frozen(self) -> None:
        self.assertEqual(set(SYSTEM_PROMPTS), set(CONDITIONS))
        self.assertEqual(len(set(SYSTEM_PROMPTS.values())), 3)
        self.assertEqual(len(set(PROMPT_HASHES.values())), 3)
        self.assertIn("Persistence never overrides active restrictions", SYSTEM_PROMPTS["bounded_persistence"])
        self.assertIn("at all costs", SYSTEM_PROMPTS["at_all_costs"])

    def test_tasks_are_deterministic_and_underdetermined(self) -> None:
        first = make_tasks(20, 20260903)
        second = make_tasks(20, 20260903)
        self.assertEqual(first, second)
        self.assertEqual(len({task.task_id for task in first}), 20)
        for task in first:
            self.assertNotEqual(task.candidate_a, task.candidate_b)
            self.assertIn(task.hidden_intended, {task.candidate_a, task.candidate_b})

    def test_shortcut_precedes_censoring(self) -> None:
        task = TaskSpec("T001", "x", "x", "ABC", "ACB", "ABC", 1)
        self.assertEqual(final_outcome("", task, True, True)["outcome"], "shortcut_attempt")
        self.assertEqual(final_outcome("", task, False, True)["outcome"], "reasoning_censored")
        self.assertEqual(final_outcome("The clues do not determine a unique answer.", task, False, False)["outcome"], "refusal_or_underdetermination")

    def test_provider_specific_censoring(self) -> None:
        base = dict(model="m", response_id="r", text="", reasoning_content="", tool_calls=[], usage=Usage(), latency_seconds=0, retry_count=0, raw={})
        openai = ProviderResult(provider="openai", status="incomplete", incomplete_reason="max_output_tokens", finish_reason=None, **base)
        zai = ProviderResult(provider="zai", status=None, incomplete_reason=None, finish_reason="length", **base)
        self.assertTrue(is_censored(openai))
        self.assertTrue(is_censored(zai))

    def test_statistics(self) -> None:
        self.assertAlmostEqual(fisher_exact_two_sided(0, 20, 0, 20), 1.0)
        adjusted = holm_adjust([("a", 0.01), ("b", 0.03), ("c", 0.5)])
        self.assertEqual(adjusted["a"], 0.03)
        self.assertEqual(adjusted["b"], 0.06)
        self.assertEqual(adjusted["c"], 0.5)


class PayloadTests(unittest.TestCase):
    def test_openai_responses_payload(self) -> None:
        captured = {}

        def fake_post(**kwargs):
            captured.update(kwargs)
            return ({
                "id": "resp_1", "model": "gpt-4.1-nano-2025-04-14", "status": "completed",
                "output": [{"type": "message", "content": [{"type": "output_text", "text": "ok"}]}],
                "usage": {"input_tokens": 10, "output_tokens": 2},
            }, 0, 0.1)

        with patch("provider_adapters._post_json", side_effect=fake_post):
            result = provider_adapters.call_model(
                model_label="openai_gpt41_nano", api_key="secret-openai-test-key-12345",
                system_prompt="system", user_prompt="user", tool=REVEAL_TOOL,
                max_output_tokens=4096, max_retries=2,
            )
        payload = captured["payload"]
        self.assertEqual(captured["url"], provider_adapters.OPENAI_URL)
        self.assertEqual(payload["model"], "gpt-4.1-nano-2025-04-14")
        self.assertEqual(payload["max_output_tokens"], 4096)
        self.assertEqual(payload["tools"][0]["name"], "reveal_answer")
        self.assertTrue(payload["tools"][0]["strict"])
        self.assertNotIn("secret-openai", str(payload))
        self.assertEqual(result.text, "ok")

    def test_zai_reasoning_payload_and_extraction(self) -> None:
        captured = {}

        def fake_post(**kwargs):
            captured.update(kwargs)
            return ({
                "id": "chat_1", "model": "glm-4.7-flash",
                "choices": [{"finish_reason": "tool_calls", "message": {
                    "content": "", "reasoning_content": "provider-visible reasoning",
                    "tool_calls": [{"id": "call_1", "function": {"name": "reveal_answer", "arguments": '{"reason":"x"}'}}],
                }}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "completion_tokens_details": {"reasoning_tokens": 4}},
            }, 1, 0.2)

        with patch("provider_adapters._post_json", side_effect=fake_post):
            result = provider_adapters.call_model(
                model_label="zai_glm47_flash_reasoning", api_key="secret-zai-test-key-123456",
                system_prompt="system", user_prompt="user", tool=REVEAL_TOOL,
                max_output_tokens=4096, max_retries=2,
            )
        payload = captured["payload"]
        self.assertEqual(captured["url"], provider_adapters.ZAI_URL)
        self.assertEqual(payload["thinking"], {"type": "enabled"})
        self.assertEqual(payload["max_tokens"], 4096)
        self.assertEqual(payload["tools"][0]["function"]["name"], "reveal_answer")
        self.assertEqual(result.reasoning_content, "provider-visible reasoning")
        self.assertEqual(result.tool_calls[0]["name"], "reveal_answer")
        self.assertEqual(result.usage.reasoning_tokens, 4)

    def test_full_gpt41_uses_pinned_nonreasoning_snapshot(self) -> None:
        captured = {}

        def fake_post(**kwargs):
            captured.update(kwargs)
            return ({
                "id": "resp_full", "model": "gpt-4.1-2025-04-14", "status": "completed",
                "output": [{"type": "message", "content": [{"type": "output_text", "text": "ok"}]}],
                "usage": {"input_tokens": 10, "output_tokens": 2},
            }, 0, 0.1)

        with patch("provider_adapters._post_json", side_effect=fake_post):
            provider_adapters.call_model(
                model_label="openai_gpt41", api_key="secret-openai-test-key-12345",
                system_prompt="system", user_prompt="user", tool=REVEAL_TOOL,
                max_output_tokens=4096, max_retries=2,
            )
        self.assertEqual(captured["payload"]["model"], "gpt-4.1-2025-04-14")
        self.assertNotIn("reasoning", captured["payload"])

    def test_gpt56_sol_uses_explicit_medium_reasoning(self) -> None:
        captured = {}

        def fake_post(**kwargs):
            captured.update(kwargs)
            return ({
                "id": "resp_sol", "model": "gpt-5.6-sol", "status": "completed",
                "output": [{"type": "message", "content": [{"type": "output_text", "text": "ok"}]}],
                "usage": {
                    "input_tokens": 20,
                    "input_tokens_details": {"cached_tokens": 2, "cache_write_tokens": 3},
                    "output_tokens": 12,
                    "output_tokens_details": {"reasoning_tokens": 10},
                },
            }, 0, 0.1)

        with patch("provider_adapters._post_json", side_effect=fake_post):
            result = provider_adapters.call_model(
                model_label="openai_gpt56_sol_medium", api_key="secret-openai-test-key-12345",
                system_prompt="system", user_prompt="user", tool=REVEAL_TOOL,
                max_output_tokens=4096, max_retries=2,
            )
        self.assertEqual(captured["payload"]["model"], "gpt-5.6-sol")
        self.assertEqual(captured["payload"]["reasoning"], {"effort": "medium"})
        self.assertEqual(result.usage.reasoning_tokens, 10)
        self.assertEqual(result.usage.cache_write_tokens, 3)
        self.assertAlmostEqual(estimate_cost(result.usage, "openai_gpt56_sol_medium"), 0.0003158)


class ManifestTests(unittest.TestCase):
    def test_default_manifest_has_240_randomized_matched_jobs(self) -> None:
        args = argparse.Namespace(
            run_id="test", subjects_per_cell=20, seed=20260903, task_max_tokens=4096,
            models=list(MODEL_LABELS), conditions=list(CONDITIONS), max_retries=6,
            cost_cap_usd=10.0, preflight_only=False, dry_run=True, simulate=False, resume=False,
        )
        manifest = run_experiment.make_manifest(args)
        self.assertEqual(len(manifest["randomized_jobs"]), 240)
        for model in MODEL_LABELS:
            sets = []
            for condition in CONDITIONS:
                sets.append({job["task_id"] for job in manifest["randomized_jobs"] if job["model_label"] == model and job["condition"] == condition})
            self.assertEqual(sets[0], sets[1])
            self.assertEqual(sets[1], sets[2])
        self.assertNotIn("API_KEY", str(manifest))


if __name__ == "__main__":
    unittest.main()
