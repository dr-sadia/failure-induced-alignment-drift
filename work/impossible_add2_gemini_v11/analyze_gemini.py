#!/usr/bin/env python3
"""Add pre-registered Gemini tier comparisons to the base v10.2 report."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from config import MODEL_CONFIGS, MODEL_ORDER


def _aggregate_model(cells: dict[str, Any]) -> dict[str, Any]:
    selected = [
        cell
        for condition in cells.values()
        for cell in condition.values()
    ]
    subjects = sum(int(cell["subjects"]) for cell in selected)
    censored = sum(int(cell["censored_for_primary"]) for cell in selected)
    observed = subjects - censored
    prohibited = sum(int(cell["prohibited_tool_calls"]) for cell in selected)
    return {
        "subjects": subjects,
        "observed": observed,
        "censored": censored,
        "prohibited_tool_calls": prohibited,
        "prohibited_rate_complete_case": prohibited / observed if observed else None,
        "prohibited_rate_lower_bound": prohibited / subjects if subjects else None,
    }


def _difference(left: float | None, right: float | None) -> float | None:
    return left - right if left is not None and right is not None else None


def _format_rate(value: float | None) -> str:
    return "NA" if value is None else f"{100 * value:.1f}%"


def _format_pp(value: float | None) -> str:
    return "NA" if value is None else f"{100 * value:+.1f} pp"


def add_tier_analysis(run_dir: Path) -> None:
    summary_path = run_dir / "summary.json"
    if not summary_path.exists():
        return
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    aggregate = {
        model: _aggregate_model(summary["cells"][model])
        for model in MODEL_ORDER
        if model in summary["cells"]
    }

    pairs = (
        ("gemini35_flash_lite_low", "gemini38_flash_low"),
        ("gemini35_flash_lite_low", "gemini31_pro_low"),
        ("gemini38_flash_low", "gemini31_pro_low"),
    )
    pairwise: list[dict[str, Any]] = []
    for smaller, larger in pairs:
        if smaller not in aggregate or larger not in aggregate:
            continue
        pairwise.append({
            "smaller_model": smaller,
            "larger_model": larger,
            "complete_case_risk_difference": _difference(
                aggregate[smaller]["prohibited_rate_complete_case"],
                aggregate[larger]["prohibited_rate_complete_case"],
            ),
            "lower_bound_risk_difference": _difference(
                aggregate[smaller]["prohibited_rate_lower_bound"],
                aggregate[larger]["prohibited_rate_lower_bound"],
            ),
        })

    stratified: list[dict[str, Any]] = []
    if all(model in summary["cells"] for model in MODEL_ORDER):
        conditions = summary["cells"][MODEL_ORDER[0]].keys()
        for condition in conditions:
            memory_modes = summary["cells"][MODEL_ORDER[0]][condition].keys()
            for memory_mode in memory_modes:
                rates = {
                    model: summary["cells"][model][condition][memory_mode]["prohibited_rate_complete_case"]
                    for model in MODEL_ORDER
                }
                stratified.append({
                    "condition": condition,
                    "memory_mode": memory_mode,
                    "complete_case_rates": rates,
                    "small_minus_large": _difference(
                        rates["gemini35_flash_lite_low"], rates["gemini31_pro_low"]
                    ),
                })

    tier_analysis = {
        "ordered_descriptive_tiers": [
            {"model_label": model, "tier": MODEL_CONFIGS[model]["model_tier"]}
            for model in MODEL_ORDER
        ],
        "aggregate_by_model": aggregate,
        "pairwise_descriptive_contrasts": pairwise,
        "stratified_small_minus_large": stratified,
        "interpretation_limit": (
            "This is an ordered product-tier comparison, not an identified parameter-scale effect. "
            "Google does not publish parameter counts here, and the models also differ by generation, "
            "training, and preview/stable status. The clustered pilot is descriptive."
        ),
    }
    summary["gemini_tier_analysis"] = tier_analysis
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    report_path = run_dir / "report.md"
    report = report_path.read_text(encoding="utf-8")
    lines = [
        "",
        "## Gemini product-tier comparison",
        "",
        "| Product tier | Model | N | Native `set_value` calls | Complete-case rate | Censored |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for model in MODEL_ORDER:
        if model not in aggregate:
            continue
        row = aggregate[model]
        lines.append(
            f"| {MODEL_CONFIGS[model]['model_tier']} | {model} | {row['subjects']} | "
            f"{row['prohibited_tool_calls']} | {_format_rate(row['prohibited_rate_complete_case'])} | "
            f"{row['censored']} |"
        )
    lines += [
        "",
        "| Smaller tier − larger tier | Complete-case risk difference |",
        "|---|---:|",
    ]
    for row in pairwise:
        lines.append(
            f"| {row['smaller_model']} − {row['larger_model']} | "
            f"{_format_pp(row['complete_case_risk_difference'])} |"
        )
    lines += [
        "",
        tier_analysis["interpretation_limit"],
    ]
    report_path.write_text(report.rstrip() + "\n" + "\n".join(lines) + "\n", encoding="utf-8")

