"""Frozen Gemini panel for the impossible add-two experiment v11.0."""

from __future__ import annotations


PROTOCOL_VERSION = "impossible-add-two-gemini-v11.0"

MODEL_CONFIGS = {
    "gemini35_flash_lite_low": {
        "provider": "gemini",
        "model": "gemini-3.5-flash-lite",
        "model_tier": "small",
        "thinking_level": "low",
        "thinking_summaries": "none",
        "request_gap_seconds": 0.5,
        "price_per_million": {
            "input": 0.30,
            "cached": 0.03,
            "cache_write": 0.30,
            "output": 2.50,
        },
    },
    "gemini38_flash_low": {
        "provider": "gemini",
        "model": "gemini-3.8-flash",
        "model_tier": "middle",
        "thinking_level": "low",
        "thinking_summaries": "none",
        "request_gap_seconds": 0.5,
        "price_per_million": {
            "input": 0.75,
            "cached": 0.075,
            "cache_write": 0.75,
            "output": 3.75,
        },
    },
    "gemini31_pro_low": {
        "provider": "gemini",
        "model": "gemini-3.1-pro-preview",
        "model_tier": "large",
        "thinking_level": "low",
        "thinking_summaries": "none",
        "request_gap_seconds": 0.75,
        "price_per_million": {
            "input": 2.00,
            "cached": 0.20,
            "cache_write": 2.00,
            "output": 12.00,
        },
    },
}

MODEL_LABELS = tuple(MODEL_CONFIGS)
MODEL_ORDER = tuple(MODEL_CONFIGS)

