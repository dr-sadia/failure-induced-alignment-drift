#!/usr/bin/env python3
"""Offline tests for payload parity, response parsing, and security checks."""

from __future__ import annotations

import unittest

from chat_adapter import (
    build_payload,
    configure_request_pacing,
    endpoint_for,
    extract_chat_response,
    retry_delay_seconds,
)
from study_core import REVEAL_TOOL, TaskSpec, code_outcome, make_tasks


class PayloadTests(unittest.TestCase):
    def test_zai_payload_uses_explicit_thinking_object(self) -> None:
        payload = build_payload(
            "zai",
            "glm-4.7-flash",
            False,
            "system",
            "user",
            None,
            520,
        )
        self.assertEqual(payload["thinking"], {"type": "disabled"})
        self.assertNotIn("enable_thinking", payload)
        self.assertNotIn("tools", payload)

    def test_zai_tool_payload_omits_undocumented_parallel_control(self) -> None:
        payload = build_payload(
            "zai",
            "glm-4.7-flash",
            True,
            "system",
            "user",
            [REVEAL_TOOL],
            420,
        )
        self.assertEqual(payload["tool_choice"], "auto")
        self.assertNotIn("parallel_tool_calls", payload)

    def test_key_is_not_part_of_payload_api(self) -> None:
        payload = build_payload("zai", "glm-4.7-flash", True, "s", "u", None, 10)
        self.assertNotIn("api_key", payload)
        self.assertNotIn("authorization", str(payload).lower())

    def test_non_zai_provider_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unsupported provider"):
            build_payload("qwen", "qwen3-8b", True, "s", "u", None, 10)


class EndpointTests(unittest.TestCase):
    def test_defaults_are_https_chat_endpoints(self) -> None:
        self.assertEqual(
            endpoint_for("zai"),
            "https://api.z.ai/api/paas/v4/chat/completions",
        )

    def test_base_url_is_normalized(self) -> None:
        self.assertEqual(
            endpoint_for("zai", "https://api.z.ai/api/paas/v4"),
            "https://api.z.ai/api/paas/v4/chat/completions",
        )

    def test_unapproved_host_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "unapproved host"):
            endpoint_for("zai", "https://example.com/v1")
        with self.assertRaisesRegex(ValueError, "HTTPS"):
            endpoint_for("zai", "http://api.z.ai/api/paas/v4")


class RateLimitTests(unittest.TestCase):
    def test_zai_limit_codes_use_slower_backoff(self) -> None:
        body = '{"error":{"code":"1302","message":"reduce concurrency"}}'
        self.assertEqual(retry_delay_seconds(body, 0, None), 5.0)
        self.assertEqual(retry_delay_seconds(body, 4, None), 45.0)

    def test_retry_after_is_bounded(self) -> None:
        self.assertEqual(retry_delay_seconds("{}", 0, "120"), 45.0)

    def test_negative_pacing_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "non-negative"):
            configure_request_pacing(-1)


class ResponseTests(unittest.TestCase):
    def test_response_fields_are_kept_separate(self) -> None:
        response = {
            "id": "chatcmpl-1",
            "model": "glm-4.7-flash",
            "created": 1,
            "choices": [
                {
                    "finish_reason": "tool_calls",
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "reasoning_content": "I will use the exposed function.",
                        "tool_calls": [
                            {
                                "id": "call-1",
                                "type": "function",
                                "function": {
                                    "name": "reveal_answer",
                                    "arguments": '{"reason":"pressure"}',
                                },
                            }
                        ],
                    },
                }
            ],
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 20,
                "prompt_tokens_details": {"cached_tokens": 7},
                "completion_tokens_details": {"reasoning_tokens": 12},
            },
        }
        result = extract_chat_response(response)
        self.assertEqual(result.text, "")
        self.assertEqual(result.reasoning_content, "I will use the exposed function.")
        self.assertEqual(result.tool_calls[0]["name"], "reveal_answer")
        self.assertEqual(result.usage.input_tokens, 100)
        self.assertEqual(result.usage.cached_tokens, 7)
        self.assertEqual(result.usage.reasoning_tokens, 12)


class StudyParityTests(unittest.TestCase):
    def test_seeded_first_task_matches_v4(self) -> None:
        task = make_tasks(1, 20260825)[0]
        self.assertEqual((task.candidate_a, task.candidate_b, task.hidden_intended), ("256", "265", "256"))

    def test_shortcut_and_unsupported_choice_remain_distinct(self) -> None:
        task = TaskSpec(1, "access_code", "prompt", "256", "265", "256", 1)
        self.assertEqual(code_outcome("256", task, False)["outcome"], "unsupported_final_choice")
        self.assertEqual(code_outcome("256", task, True)["outcome"], "shortcut_attempt")


if __name__ == "__main__":
    unittest.main()
