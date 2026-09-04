#!/usr/bin/env python3
"""Exploratory matched historical comparison of v3 with multimodel v2."""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path
from typing import Any


ARMS = ("no_memory", "naive", "verified", "contaminated")


def atomic_write(path: Path, text: str) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)


def exact_signflip(differences: list[int]) -> float:
    nonzero = [value for value in differences if value]
    if not nonzero:
        return 1.0
    observed = abs(sum(nonzero))
    extreme = 0
    total = 1 << len(nonzero)
    for bits in range(total):
        permuted = sum(
            value if (bits >> index) & 1 else -value
            for index, value in enumerate(nonzero)
        )
        extreme += abs(permuted) >= observed
    return extreme / total


def holm_adjust(rows: list[dict[str, Any]], key: str, destination: str) -> None:
    order = sorted(range(len(rows)), key=lambda index: rows[index][key])
    running = 0.0
    for rank, index in enumerate(order):
        adjusted = min(1.0, (len(rows) - rank) * rows[index][key])
        running = max(running, adjusted)
        rows[index][destination] = running


def records(suite: Path, condition: str, model: str, arm: str) -> list[dict[str, Any]]:
    paths = sorted((suite / condition / model / arm).glob("T*/G*/record.json"))
    return [json.loads(path.read_text(encoding="utf-8")) for path in paths]


def trajectory_counts(items: list[dict[str, Any]], outcome: str) -> list[int]:
    counts = {trajectory: 0 for trajectory in range(1, 21)}
    for item in items:
        if outcome == "shortcut":
            selected = item["outcome"] == "shortcut_attempt"
        elif outcome == "unsupported":
            selected = item["outcome"] == "unsupported_final_choice"
        elif outcome == "composite":
            selected = item["outcome"] in {"shortcut_attempt", "unsupported_final_choice"}
        else:
            raise ValueError(outcome)
        counts[item["trajectory"]] += int(selected)
    return [counts[index] for index in range(1, 21)]


def report_markdown(output: dict[str, Any]) -> str:
    lines = [
        "# System-instruction ablation v3 versus v2",
        "",
        "Status: **exploratory matched historical comparison**. The task templates and seeds match, but v2 and v3 were not simultaneously randomized.",
        "",
        "Negative shortcut deltas mean fewer prohibited tool calls in v3. Positive unsupported deltas mean more unsupported exact answers in v3.",
        "",
        "## Model totals across four arms",
        "",
        "| Condition | V2 shortcut | V3 shortcut | Δ shortcut | V2 unsupported | V3 unsupported | Δ unsupported | V2 composite | V3 composite | Δ composite | Median runtime change |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in output["model_totals"]:
        lines.append(
            f"| {row['condition']} | {row['v2_shortcut']}/400 | {row['v3_shortcut']}/400 | {row['delta_shortcut']:+d} | "
            f"{row['v2_unsupported']}/400 | {row['v3_unsupported']}/400 | {row['delta_unsupported']:+d} | "
            f"{row['v2_composite']}/400 | {row['v3_composite']}/400 | {row['delta_composite']:+d} | "
            f"{row['runtime_percent_change']:+.1f}% |"
        )
    lines.extend(
        [
            "",
            "## Arm-level outcomes",
            "",
            "| Condition | Arm | Trajectory shortcut v2→v3 | Subject shortcut v2→v3 | Unsupported v2→v3 | Composite v2→v3 | Runtime v2→v3 | Exploratory shortcut p | Holm p |",
            "|---|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in output["arm_comparisons"]:
        lines.append(
            f"| {row['condition']} | {row['arm']} | {row['v2_trajectory_shortcut']}/20→{row['v3_trajectory_shortcut']}/20 | "
            f"{row['v2_subject_shortcut']}/100→{row['v3_subject_shortcut']}/100 | "
            f"{row['v2_unsupported']}/100→{row['v3_unsupported']}/100 | "
            f"{row['v2_composite']}/100→{row['v3_composite']}/100 | "
            f"{row['v2_median_runtime']:.2f}s→{row['v3_median_runtime']:.2f}s | "
            f"{row['shortcut_signflip_p']:.6g} | {row['shortcut_holm_p']:.6g} |"
        )
    lines.extend(
        [
            "",
            "The exploratory p-values are exact sign-flip tests on the 20 matched task-level differences in shortcut-subject counts. Holm correction covers all 20 model × arm comparisons. They do not convert the historical contrast into a randomized causal estimate.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("v3_suite", type=Path)
    parser.add_argument(
        "--v2-suite",
        type=Path,
        default=Path(__file__).resolve().parents[1]
        / "multimodel_v2"
        / "runs"
        / "multimodel_v2_20260825_small_old_r1",
    )
    args = parser.parse_args()
    v2_suite = args.v2_suite.resolve()
    v3_suite = args.v3_suite.resolve()
    v2_summary = json.loads((v2_suite / "suite_summary.json").read_text(encoding="utf-8"))
    v3_summary = json.loads((v3_suite / "suite_summary.json").read_text(encoding="utf-8"))
    v2_conditions = {item["label"]: item for item in v2_summary["conditions"]}
    v3_conditions = {item["label"]: item for item in v3_summary["conditions"]}
    if set(v2_conditions) != set(v3_conditions):
        raise ValueError("v2 and v3 condition labels do not match")

    rows: list[dict[str, Any]] = []
    model_totals: list[dict[str, Any]] = []
    for condition in v3_conditions:
        v2_condition = v2_conditions[condition]
        v3_condition = v3_conditions[condition]
        model = v3_condition["summary"]["model"]
        v2_all: list[dict[str, Any]] = []
        v3_all: list[dict[str, Any]] = []
        for arm in ARMS:
            v2_items = records(v2_suite, condition, model, arm)
            v3_items = records(v3_suite, condition, model, arm)
            if len(v2_items) != 100 or len(v3_items) != 100:
                raise ValueError(f"Expected 100 records for {condition}/{arm}")
            v2_all.extend(v2_items)
            v3_all.extend(v3_items)
            v2_shortcut = trajectory_counts(v2_items, "shortcut")
            v3_shortcut = trajectory_counts(v3_items, "shortcut")
            v2_unsupported = trajectory_counts(v2_items, "unsupported")
            v3_unsupported = trajectory_counts(v3_items, "unsupported")
            v2_composite = trajectory_counts(v2_items, "composite")
            v3_composite = trajectory_counts(v3_items, "composite")
            shortcut_differences = [new - old for old, new in zip(v2_shortcut, v3_shortcut)]
            composite_differences = [new - old for old, new in zip(v2_composite, v3_composite)]
            rows.append(
                {
                    "condition": condition,
                    "model": model,
                    "arm": arm,
                    "v2_trajectory_shortcut": sum(value > 0 for value in v2_shortcut),
                    "v3_trajectory_shortcut": sum(value > 0 for value in v3_shortcut),
                    "v2_subject_shortcut": sum(v2_shortcut),
                    "v3_subject_shortcut": sum(v3_shortcut),
                    "delta_subject_shortcut": sum(shortcut_differences),
                    "v2_unsupported": sum(v2_unsupported),
                    "v3_unsupported": sum(v3_unsupported),
                    "delta_unsupported": sum(v3_unsupported) - sum(v2_unsupported),
                    "v2_composite": sum(v2_composite),
                    "v3_composite": sum(v3_composite),
                    "delta_composite": sum(composite_differences),
                    "v2_median_runtime": statistics.median(item["subject_elapsed_seconds"] for item in v2_items),
                    "v3_median_runtime": statistics.median(item["subject_elapsed_seconds"] for item in v3_items),
                    "shortcut_improved_tasks": sum(value < 0 for value in shortcut_differences),
                    "shortcut_worse_tasks": sum(value > 0 for value in shortcut_differences),
                    "shortcut_tied_tasks": sum(value == 0 for value in shortcut_differences),
                    "shortcut_signflip_p": exact_signflip(shortcut_differences),
                    "composite_signflip_p": exact_signflip(composite_differences),
                }
            )
        v2_runtime = statistics.median(item["subject_elapsed_seconds"] for item in v2_all)
        v3_runtime = statistics.median(item["subject_elapsed_seconds"] for item in v3_all)
        v2_shortcut_total = sum(item["outcome"] == "shortcut_attempt" for item in v2_all)
        v3_shortcut_total = sum(item["outcome"] == "shortcut_attempt" for item in v3_all)
        v2_unsupported_total = sum(item["outcome"] == "unsupported_final_choice" for item in v2_all)
        v3_unsupported_total = sum(item["outcome"] == "unsupported_final_choice" for item in v3_all)
        model_totals.append(
            {
                "condition": condition,
                "model": model,
                "v2_shortcut": v2_shortcut_total,
                "v3_shortcut": v3_shortcut_total,
                "delta_shortcut": v3_shortcut_total - v2_shortcut_total,
                "v2_unsupported": v2_unsupported_total,
                "v3_unsupported": v3_unsupported_total,
                "delta_unsupported": v3_unsupported_total - v2_unsupported_total,
                "v2_composite": v2_shortcut_total + v2_unsupported_total,
                "v3_composite": v3_shortcut_total + v3_unsupported_total,
                "delta_composite": (v3_shortcut_total + v3_unsupported_total) - (v2_shortcut_total + v2_unsupported_total),
                "v2_median_runtime": v2_runtime,
                "v3_median_runtime": v3_runtime,
                "runtime_percent_change": 100 * (v3_runtime / v2_runtime - 1),
            }
        )
    holm_adjust(rows, "shortcut_signflip_p", "shortcut_holm_p")
    holm_adjust(rows, "composite_signflip_p", "composite_holm_p")
    output = {
        "status": "exploratory_matched_historical_comparison",
        "v2_suite": v2_summary["suite_id"],
        "v3_suite": v3_summary["suite_id"],
        "instruction_change": "Removed the evaluator-feedback-evidence sentence and the study-hypothesis sentence.",
        "model_totals": model_totals,
        "arm_comparisons": rows,
    }
    atomic_write(v3_suite / "v2_comparison.json", json.dumps(output, indent=2, sort_keys=True))
    atomic_write(v3_suite / "v2_comparison.md", report_markdown(output))
    print(json.dumps({"complete": True, "output": str(v3_suite / "v2_comparison.json")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
