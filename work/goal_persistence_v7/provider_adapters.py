#!/usr/bin/env python3
"""Minimal, auditable HTTP adapters for OpenAI Responses and Z.AI chat APIs."""

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


OPENAI_URL = "https://api.openai.com/v1/responses"
ZAI_URL = "https://api.z.ai/api/paas/v4/chat/completions"
RETRYABLE_HTTP = {408, 409, 429, 500, 502, 503, 504}


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
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
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
                raise ProviderError(f"HTTP {exc.code} after {attempt + 1} attempt(s): {body.replace(key, '[REDACTED]')}") from None
            retry_after = exc.headers.get("retry-after")
            if retry_after:
                try:
                    delay = min(45.0, max(0.0, float(retry_after)))
                except ValueError:
                    delay = 0.0
            else:
                delay = 0.0
            if not delay:
                try:
                    provider_code = str((json.loads(body).get("error") or {}).get("code") or "")
                except (AttributeError, json.JSONDecodeError):
                    provider_code = ""
                base = 5.0 if provider_code in {"1302", "1303", "1305", "1312"} else 1.5
                delay = min(45.0, base * (2**attempt))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            if attempt >= max_retries:
                safe_error = str(exc).replace(key, "[REDACTED]")
                raise ProviderError(f"Transport/JSON failure after {attempt + 1} attempt(s): {type(exc).__name__}: {safe_error}") from None
            delay = min(45.0, 1.5 * (2**attempt))
        # Keep each blocking interval below one minute; jitter avoids synchronized retries.
        time.sleep(delay + random.random() * 0.25)
    raise AssertionError("unreachable")


def _openai_tool(tool: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "function",
        "name": tool["name"],
        "description": tool["description"],
        "parameters": tool["parameters"],
        "strict": True,
    }


def _chat_tool(tool: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": tool["name"],
            "description": tool["description"],
            "parameters": tool["parameters"],
        },
    }


def _extract_openai(response: dict[str, Any], latency: float, retries: int) -> ProviderResult:
    texts: list[str] = []
    calls: list[dict[str, Any]] = []
    for item in response.get("output") or []:
        if item.get("type") == "function_call":
            calls.append(
                {
                    "name": item.get("name"),
                    "arguments": item.get("arguments"),
                    "call_id": item.get("call_id"),
                    "item_id": item.get("id"),
                }
            )
        if item.get("type") == "message":
            for content in item.get("content") or []:
                if content.get("type") in {"output_text", "text"} and content.get("text"):
                    texts.append(str(content["text"]))
    if response.get("output_text") and str(response["output_text"]) not in texts:
        texts.append(str(response["output_text"]))
    usage_raw = response.get("usage") or {}
    input_details = usage_raw.get("input_tokens_details") or {}
    output_details = usage_raw.get("output_tokens_details") or {}
    incomplete = response.get("incomplete_details") or {}
    return ProviderResult(
        provider="openai",
        model=str(response.get("model") or ""),
        response_id=response.get("id"),
        text="\n".join(texts).strip(),
        reasoning_content="",  # GPT-4.1 nano exposes no reasoning trace.
        tool_calls=calls,
        usage=Usage(
            input_tokens=int(usage_raw.get("input_tokens") or 0),
            cached_tokens=int(input_details.get("cached_tokens") or 0),
            cache_write_tokens=int(input_details.get("cache_write_tokens") or 0),
            output_tokens=int(usage_raw.get("output_tokens") or 0),
            reasoning_tokens=int(output_details.get("reasoning_tokens") or 0),
        ),
        status=response.get("status"),
        incomplete_reason=incomplete.get("reason"),
        finish_reason=None,
        latency_seconds=latency,
        retry_count=retries,
        raw=response,
    )


def _extract_zai(response: dict[str, Any], latency: float, retries: int) -> ProviderResult:
    choices = response.get("choices") or []
    if not choices or not isinstance(choices[0], dict):
        raise ProviderError("Z.AI response contained no completion choice")
    choice = choices[0] if choices else {}
    message = choice.get("message") or {}

    def content_text(value: Any) -> str:
        if isinstance(value, str):
            return value
        if isinstance(value, list):
            return "\n".join(
                item if isinstance(item, str) else str(item.get("text") or "")
                for item in value
                if isinstance(item, (str, dict))
            )
        return ""
    calls: list[dict[str, Any]] = []
    for call in message.get("tool_calls") or []:
        function = call.get("function") or {}
        calls.append(
            {
                "name": function.get("name"),
                "arguments": function.get("arguments"),
                "call_id": call.get("id"),
                "item_id": None,
            }
        )
    usage_raw = response.get("usage") or {}
    prompt_details = usage_raw.get("prompt_tokens_details") or {}
    completion_details = usage_raw.get("completion_tokens_details") or {}
    return ProviderResult(
        provider="zai",
        model=str(response.get("model") or ""),
        response_id=response.get("id"),
        text=content_text(message.get("content")).strip(),
        reasoning_content=content_text(message.get("reasoning_content")).strip(),
        tool_calls=calls,
        usage=Usage(
            input_tokens=int(usage_raw.get("prompt_tokens") or 0),
            cached_tokens=int(prompt_details.get("cached_tokens") or 0),
            cache_write_tokens=0,
            output_tokens=int(usage_raw.get("completion_tokens") or 0),
            reasoning_tokens=int(completion_details.get("reasoning_tokens") or 0),
        ),
        status=None,
        incomplete_reason=None,
        finish_reason=choice.get("finish_reason"),
        latency_seconds=latency,
        retry_count=retries,
        raw=response,
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
    provider = config["provider"]
    if provider == "openai":
        _validate_url(OPENAI_URL, "api.openai.com", "/v1/responses")
        payload: dict[str, Any] = {
            "model": config["model"],
            "instructions": system_prompt,
            "input": [{"role": "user", "content": [{"type": "input_text", "text": user_prompt}]}],
            "max_output_tokens": max_output_tokens,
            "store": False,
        }
        if tool:
            payload.update({"tools": [_openai_tool(tool)], "tool_choice": "auto"})
        if config.get("reasoning"):
            payload["reasoning"] = {"effort": config["reasoning"]}
        raw, retries, latency = _post_json(
            url=OPENAI_URL,
            key=api_key,
            payload=payload,
            max_retries=max_retries,
            timeout_seconds=180,
        )
        return _extract_openai(raw, latency, retries)
    if provider == "zai":
        _validate_url(ZAI_URL, "api.z.ai", "/api/paas/v4/chat/completions")
        payload = {
            "model": config["model"],
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": max_output_tokens,
            "thinking": {"type": "enabled"},
        }
        if tool:
            payload.update({"tools": [_chat_tool(tool)], "tool_choice": "auto"})
        raw, retries, latency = _post_json(
            url=ZAI_URL,
            key=api_key,
            payload=payload,
            max_retries=max_retries,
            timeout_seconds=600,
        )
        return _extract_zai(raw, latency, retries)
    raise ValueError(f"Unknown provider: {provider}")
