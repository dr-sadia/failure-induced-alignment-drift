"""Native Gemini Interactions API adapter for the v11 experiment."""

from __future__ import annotations

import json
from typing import Any

from config import MODEL_CONFIGS
from provider_adapters import ProviderError, ProviderResult, _post_json, _validate_url
from study_core import Usage


GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/interactions"
API_REVISION = "2026-05-20"


def _gemini_tool(tool: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "function",
        "name": tool["name"],
        "description": tool["description"],
        "parameters": tool["parameters"],
    }


def _texts(content: Any) -> list[str]:
    if not isinstance(content, list):
        return []
    return [
        str(block["text"])
        for block in content
        if isinstance(block, dict) and block.get("type") == "text" and block.get("text")
    ]


def _extract_gemini(response: dict[str, Any], latency: float, retries: int) -> ProviderResult:
    texts: list[str] = []
    reasoning: list[str] = []
    calls: list[dict[str, Any]] = []
    for step in response.get("steps") or []:
        if not isinstance(step, dict):
            continue
        step_type = step.get("type")
        if step_type == "model_output":
            texts.extend(_texts(step.get("content")))
        elif step_type == "thought":
            reasoning.extend(_texts(step.get("summary")))
        elif step_type == "function_call":
            calls.append({
                "name": step.get("name"),
                "arguments": step.get("arguments"),
                "call_id": step.get("id"),
                "item_id": None,
            })

    status = str(response.get("status") or "") or None
    errors = response.get("errors") or []
    violations: list[str] = []
    if status == "requires_action" and not calls:
        violations.append("requires_action_without_native_function_call")
    if errors:
        violations.append("interaction_returned_errors")

    usage_raw = response.get("usage") or {}
    thought_tokens = int(usage_raw.get("total_thought_tokens") or 0)
    visible_output_tokens = int(usage_raw.get("total_output_tokens") or 0)
    incomplete_reason = None
    if status in {"incomplete", "failed", "cancelled"}:
        details = response.get("incomplete_details") or {}
        incomplete_reason = str(details.get("reason") or status)
    if errors and incomplete_reason is None:
        incomplete_reason = "; ".join(
            str(error.get("message") or error.get("code") or "provider error")
            for error in errors
            if isinstance(error, dict)
        ) or "provider error"

    return ProviderResult(
        provider="gemini",
        model=str(response.get("model") or ""),
        response_id=response.get("id"),
        text="\n".join(texts).strip(),
        reasoning_content="\n".join(reasoning).strip(),
        tool_calls=calls,
        usage=Usage(
            input_tokens=int(usage_raw.get("total_input_tokens") or 0),
            cached_tokens=int(usage_raw.get("total_cached_tokens") or 0),
            cache_write_tokens=0,
            # Gemini reports visible output and thought tokens separately. Pricing
            # bills both at the output rate, so the cost-bearing field includes both.
            output_tokens=visible_output_tokens + thought_tokens,
            reasoning_tokens=thought_tokens,
        ),
        status=status,
        incomplete_reason=incomplete_reason,
        finish_reason=status,
        latency_seconds=latency,
        retry_count=retries,
        raw=response,
        protocol_violations=violations,
    )


def call_model(
    *,
    model_label: str,
    api_key: str,
    system_prompt: str,
    user_prompt: str,
    tools: list[dict[str, Any]] | tuple[dict[str, Any], ...] | None,
    max_output_tokens: int,
    max_retries: int,
) -> ProviderResult:
    config = MODEL_CONFIGS[model_label]
    offered_tools = list(tools or [])
    _validate_url(
        GEMINI_URL,
        "generativelanguage.googleapis.com",
        "/v1beta/interactions",
    )
    generation_config: dict[str, Any] = {
        "max_output_tokens": max_output_tokens,
        "thinking_level": config["thinking_level"],
        "thinking_summaries": config["thinking_summaries"],
    }
    payload: dict[str, Any] = {
        "model": config["model"],
        "system_instruction": system_prompt,
        "input": user_prompt,
        "store": False,
        "generation_config": generation_config,
    }
    if offered_tools:
        payload["tools"] = [_gemini_tool(tool) for tool in offered_tools]
        generation_config["tool_choice"] = "auto"

    raw, retries, latency = _post_json(
        url=GEMINI_URL,
        key=api_key,
        payload=payload,
        max_retries=max_retries,
        timeout_seconds=600,
        extra_headers={
            "x-goog-api-key": api_key,
            "Api-Revision": API_REVISION,
        },
        bearer_authorization=False,
    )
    result = _extract_gemini(raw, latency, retries)
    if not result.model:
        raise ProviderError("Gemini response omitted the returned model identity")
    return result


def gemini_is_censored(provider_result: Any) -> bool:
    """Map Gemini terminal states into the frozen experiment's censoring rule."""
    if getattr(provider_result, "protocol_violations", []):
        return True
    status = (getattr(provider_result, "status", "") or "").lower()
    return status in {"incomplete", "failed", "cancelled"}

