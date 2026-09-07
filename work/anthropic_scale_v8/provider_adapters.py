#!/usr/bin/env python3
"""Minimal, auditable HTTP adapter for the Anthropic Messages API."""

from __future__ import annotations

import dataclasses
import json
import random
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

try:
    import certifi

    SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())
except ImportError:  # pragma: no cover - standard library fallback
    SSL_CONTEXT = ssl.create_default_context()

from study_core import MODEL_CONFIGS, Usage


ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
RETRYABLE_HTTP = {408, 409, 429, 500, 502, 503, 504, 529}


class ProviderError(RuntimeError):
    """An unrecovered provider/transport failure; no secret is included."""


@dataclasses.dataclass
class ProviderResult:
    provider: str
    model: str
    response_id: str | None
    text: str
    reasoning_content: str
    tool_calls: list[dict[str, Any]]
    usage: Usage
    status: str | None
    incomplete_reason: str | None
    finish_reason: str | None
    latency_seconds: float
    retry_count: int
    raw: dict[str, Any]
    protocol_violations: list[str] = dataclasses.field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        value = dataclasses.asdict(self)
        value["usage"] = self.usage.as_dict()
        return value


def _validate_url(url: str, allowed_host: str, expected_path: str) -> None:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != allowed_host or parsed.path != expected_path:
        raise ValueError(f"Refusing unexpected provider endpoint: {url}")


def _post_json(
    *,
    url: str,
    key: str,
    payload: dict[str, Any],
    max_retries: int,
    timeout_seconds: float,
) -> tuple[dict[str, Any], int, float]:
    encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    started = time.monotonic()
    for attempt in range(max_retries + 1):
        request = urllib.request.Request(
            url,
            data=encoded,
            headers={
                "Authorization": f"Bearer {key}",
                "anthropic-version": ANTHROPIC_VERSION,
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds, context=SSL_CONTEXT) as response:
                decoded = json.loads(response.read().decode("utf-8"))
                if not isinstance(decoded, dict):
                    raise ProviderError("Provider returned a non-object JSON response")
                return decoded, attempt, time.monotonic() - started
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")[:2000]
            if exc.code not in RETRYABLE_HTTP or attempt >= max_retries:
                safe_body = body.replace(key, "[REDACTED]")
                raise ProviderError(
                    f"HTTP {exc.code} after {attempt + 1} attempt(s): {safe_body}"
                ) from None
            retry_after = exc.headers.get("retry-after")
            if retry_after:
                try:
                    delay = min(45.0, max(0.0, float(retry_after)))
                except ValueError:
                    delay = 0.0
            else:
                delay = 0.0
            if not delay:
                delay = min(45.0, 1.5 * (2**attempt))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            if attempt >= max_retries:
                safe_error = str(exc).replace(key, "[REDACTED]")
                raise ProviderError(
                    f"Transport/JSON failure after {attempt + 1} attempt(s): "
                    f"{type(exc).__name__}: {safe_error}"
                ) from None
            delay = min(45.0, 1.5 * (2**attempt))
        time.sleep(delay + random.random() * 0.25)
    raise AssertionError("unreachable")


def _anthropic_tool(tool: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": tool["name"],
        "description": tool["description"],
        "input_schema": tool["parameters"],
        "strict": True,
    }


def _extract_anthropic(
    response: dict[str, Any], latency: float, retries: int
) -> ProviderResult:
    texts: list[str] = []
    reasoning: list[str] = []
    calls: list[dict[str, Any]] = []
    for block in response.get("content") or []:
        if not isinstance(block, dict):
            continue
        block_type = block.get("type")
        if block_type == "text" and block.get("text"):
            texts.append(str(block["text"]))
        elif block_type == "thinking" and block.get("thinking"):
            reasoning.append(str(block["thinking"]))
        elif block_type == "redacted_thinking":
            reasoning.append("[REDACTED_THINKING_BLOCK]")
        elif block_type == "tool_use":
            calls.append(
                {
                    "name": block.get("name"),
                    "arguments": block.get("input"),
                    "call_id": block.get("id"),
                    "item_id": None,
                }
            )

    usage_raw = response.get("usage") or {}
    output_details = usage_raw.get("output_tokens_details") or {}
    uncached_input = int(usage_raw.get("input_tokens") or 0)
    cached_input = int(usage_raw.get("cache_read_input_tokens") or 0)
    cache_write_input = int(usage_raw.get("cache_creation_input_tokens") or 0)
    stop_reason = response.get("stop_reason")
    protocol_violations: list[str] = []
    if stop_reason == "tool_use" and not calls:
        protocol_violations.append("tool_use_stop_without_native_tool_use_block")
    if calls and stop_reason != "tool_use":
        protocol_violations.append("native_tool_use_block_without_tool_use_stop")
    incomplete_reason = stop_reason if stop_reason in {
        "max_tokens",
        "model_context_window_exceeded",
    } else None
    return ProviderResult(
        provider="anthropic",
        model=str(response.get("model") or ""),
        response_id=response.get("id"),
        text="\n".join(texts).strip(),
        reasoning_content="\n".join(reasoning).strip(),
        tool_calls=calls,
        usage=Usage(
            input_tokens=uncached_input + cached_input + cache_write_input,
            cached_tokens=cached_input,
            cache_write_tokens=cache_write_input,
            output_tokens=int(usage_raw.get("output_tokens") or 0),
            reasoning_tokens=int(output_details.get("thinking_tokens") or 0),
        ),
        status=None,
        incomplete_reason=incomplete_reason,
        finish_reason=stop_reason,
        latency_seconds=latency,
        retry_count=retries,
        raw=response,
        protocol_violations=protocol_violations,
    )


def call_model(
    *,
    model_label: str,
    api_key: str,
    system_prompt: str,
    user_prompt: str,
    tool: dict[str, Any] | None,
    max_output_tokens: int,
    max_retries: int,
) -> ProviderResult:
    config = MODEL_CONFIGS[model_label]
    if config["provider"] != "anthropic":
        raise ValueError(f"Unknown provider: {config['provider']}")
    _validate_url(ANTHROPIC_URL, "api.anthropic.com", "/v1/messages")
    payload: dict[str, Any] = {
        "model": config["model"],
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_prompt}],
        "max_tokens": max_output_tokens,
        "thinking": {"type": config["thinking"]},
    }
    if tool:
        payload.update(
            {
                "tools": [_anthropic_tool(tool)],
                "tool_choice": {"type": "auto", "disable_parallel_tool_use": True},
            }
        )
    raw, retries, latency = _post_json(
        url=ANTHROPIC_URL,
        key=api_key,
        payload=payload,
        max_retries=max_retries,
        timeout_seconds=600,
    )
    return _extract_anthropic(raw, latency, retries)
