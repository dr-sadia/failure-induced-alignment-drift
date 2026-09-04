#!/usr/bin/env python3
"""Minimal OpenAI-compatible Chat Completions adapter for Z.AI GLM."""

from __future__ import annotations

import dataclasses
import json
import random
import ssl
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

import certifi

from study_core import Usage


SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())
DEFAULT_ENDPOINTS = {
    "zai": "https://api.z.ai/api/paas/v4/chat/completions",
}
KEY_ENVIRONMENTS = {"zai": "ZAI_API_KEY"}

_REQUEST_GATE_LOCK = threading.Lock()
_NEXT_REQUEST_AT = 0.0
_MIN_REQUEST_INTERVAL_SECONDS = 0.0


def configure_request_pacing(min_interval_seconds: float) -> None:
    """Set a process-wide minimum gap between request starts."""
    if min_interval_seconds < 0:
        raise ValueError("request pacing interval must be non-negative")
    global _MIN_REQUEST_INTERVAL_SECONDS, _NEXT_REQUEST_AT
    with _REQUEST_GATE_LOCK:
        _MIN_REQUEST_INTERVAL_SECONDS = min_interval_seconds
        _NEXT_REQUEST_AT = 0.0


def _wait_for_request_slot() -> None:
    global _NEXT_REQUEST_AT
    with _REQUEST_GATE_LOCK:
        now = time.monotonic()
        delay = max(0.0, _NEXT_REQUEST_AT - now)
        start_at = now + delay
        _NEXT_REQUEST_AT = start_at + _MIN_REQUEST_INTERVAL_SECONDS
    if delay:
        time.sleep(delay)


def retry_delay_seconds(body: str, attempt: int, retry_after: str | None) -> float:
    """Use slower backoff for Z.AI concurrency and frequency-limit errors."""
    if retry_after:
        try:
            return min(45.0, max(0.0, float(retry_after)))
        except ValueError:
            pass
    try:
        error_code = str((json.loads(body).get("error") or {}).get("code") or "")
    except (AttributeError, json.JSONDecodeError):
        error_code = ""
    base = 5.0 if error_code in {"1302", "1303", "1305", "1312"} else 1.5
    return min(45.0, base * (2**attempt))


@dataclasses.dataclass(frozen=True)
class ChatResult:
    text: str
    reasoning_content: str
    tool_calls: list[dict[str, Any]]
    usage: Usage
    response_id: str | None
    response_model: str | None
    finish_reason: str | None
    latency_seconds: float
    retry_count: int
    raw_message: dict[str, Any]
    response_metadata: dict[str, Any]


def endpoint_for(provider: str, override: str | None = None) -> str:
    if provider not in DEFAULT_ENDPOINTS:
        raise ValueError(f"Unsupported provider: {provider}")
    endpoint = (override or DEFAULT_ENDPOINTS[provider]).strip().rstrip("/")
    if not endpoint.endswith("/chat/completions"):
        endpoint += "/chat/completions"
    parsed = urllib.parse.urlparse(endpoint)
    hostname = (parsed.hostname or "").lower()
    if parsed.scheme != "https":
        raise ValueError("Provider endpoint must use HTTPS")
    allowed = hostname == "api.z.ai"
    if not allowed:
        raise ValueError(f"Refusing to send a provider key to unapproved host: {hostname}")
    return endpoint


def _content_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        texts: list[str] = []
        for item in content:
            if isinstance(item, str):
                texts.append(item)
            elif isinstance(item, dict) and isinstance(item.get("text"), str):
                texts.append(item["text"])
        return "\n".join(texts)
    return ""


def extract_chat_response(
    response: dict[str, Any], latency_seconds: float = 0.0, retry_count: int = 0
) -> ChatResult:
    choices = response.get("choices") or []
    if not choices or not isinstance(choices[0], dict):
        raise RuntimeError("Chat completion response has no choice")
    choice = choices[0]
    message = choice.get("message") or {}
    raw_calls = message.get("tool_calls") or []
    calls: list[dict[str, Any]] = []
    for call in raw_calls:
        function = call.get("function") or {}
        calls.append(
            {
                "id": call.get("id"),
                "type": call.get("type"),
                "name": function.get("name"),
                "arguments": function.get("arguments"),
            }
        )
    raw_usage = response.get("usage") or {}
    prompt_details = raw_usage.get("prompt_tokens_details") or {}
    completion_details = raw_usage.get("completion_tokens_details") or {}
    usage = Usage(
        input_tokens=int(raw_usage.get("prompt_tokens") or 0),
        cached_tokens=int(prompt_details.get("cached_tokens") or 0),
        output_tokens=int(raw_usage.get("completion_tokens") or 0),
        reasoning_tokens=int(completion_details.get("reasoning_tokens") or 0),
    )
    metadata_keys = ("created", "object", "service_tier", "system_fingerprint")
    return ChatResult(
        text=_content_text(message.get("content")).strip(),
        reasoning_content=_content_text(message.get("reasoning_content")).strip(),
        tool_calls=calls,
        usage=usage,
        response_id=response.get("id"),
        response_model=response.get("model"),
        finish_reason=choice.get("finish_reason"),
        latency_seconds=latency_seconds,
        retry_count=retry_count,
        raw_message=message,
        response_metadata={key: response.get(key) for key in metadata_keys if key in response},
    )


def build_payload(
    provider: str,
    model: str,
    thinking: bool,
    system_instructions: str,
    prompt: str,
    tools: list[dict[str, Any]] | None,
    max_tokens: int,
    tool_choice: str | dict[str, Any] = "auto",
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_instructions},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": max_tokens,
        "stream": False,
    }
    if provider == "zai":
        payload["thinking"] = {"type": "enabled" if thinking else "disabled"}
    else:
        raise ValueError(f"Unsupported provider: {provider}")
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = tool_choice
        # Z.AI's documented synchronous schema does not expose a parallel-tool
        # control, so deliberately omit that otherwise-common parameter.
    return payload


def chat_completion(
    *,
    api_key: str,
    provider: str,
    endpoint: str,
    model: str,
    thinking: bool,
    system_instructions: str,
    prompt: str,
    tools: list[dict[str, Any]] | None,
    max_tokens: int,
    request_id: str,
    tool_choice: str | dict[str, Any] = "auto",
    retries: int = 8,
) -> ChatResult:
    payload = build_payload(
        provider,
        model,
        thinking,
        system_instructions,
        prompt,
        tools,
        max_tokens,
        tool_choice,
    )
    data = json.dumps(payload).encode("utf-8")
    for attempt in range(retries + 1):
        _wait_for_request_slot()
        started = time.monotonic()
        request = urllib.request.Request(
            endpoint,
            data=data,
            method="POST",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "User-Agent": "failure-drift-openweight-hosted-censored-v6",
                "X-Client-Request-Id": request_id,
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=600, context=SSL_CONTEXT) as result:
                response = json.loads(result.read().decode("utf-8"))
                return extract_chat_response(response, time.monotonic() - started, attempt)
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            retryable = exc.code == 429 or 500 <= exc.code < 600
            if not retryable or attempt >= retries:
                safe_body = body.replace(api_key, "[REDACTED]")
                raise RuntimeError(f"API HTTP {exc.code}: {safe_body[:2000]}") from exc
            delay = retry_delay_seconds(body, attempt, exc.headers.get("retry-after"))
            time.sleep(delay + random.random() * 0.25)
        except (urllib.error.URLError, TimeoutError) as exc:
            if attempt >= retries:
                safe_error = str(exc).replace(api_key, "[REDACTED]")
                raise RuntimeError(f"API network error after retries: {safe_error}") from exc
            time.sleep(min(45.0, 1.5 * (2**attempt)) + random.random() * 0.25)
    raise AssertionError("unreachable")
