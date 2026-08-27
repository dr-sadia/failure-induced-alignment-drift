#!/usr/bin/env python3
"""Apply the preregistered cross-condition analysis after a v2 suite run."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any


def atomic_write(path: Path, text: str) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)


def holm_adjust(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ordered = sorted(enumerate(items), key=lambda pair: pair[1]["p_value"])
    adjusted_by_index: dict[int, float] = {}
    running = 0.0
    count = len(items)
    for rank, (original_index, item) in enumerate(ordered):
        adjusted = min(1.0, (count - rank) * item["p_value"])
        running = max(running, adjusted)
        adjusted_by_index[original_index] = running
    return [
        {**item, "holm_adjusted_p": adjusted_by_index[index]}
        for index, item in enumerate(items)
    ]


def zero_event_upper_two_sided_95(n: int) -> float | None:
    return 1.0 - math.pow(0.025, 1.0 / n) if n > 0 else None


def report_markdown(analysis: dict[str, Any]) -> str:
    lines = [
        "# Small/older-model persistent-memory experiment v2: analysis",
        "",
        f"Suite ID: `{analysis['suite_id']}`  ",
        f"Total estimated cost: **${analysis['total_estimated_cost_usd']:.4f}**",
        "",
        "## Outcomes",
        "",
        "| Condition | Model | Reasoning | Arm | Trajectory shortcut | Subject shortcut | Unsupported choice | Refusal | 95% upper bound if zero |",
        "|---|---|---|---|---:|---:|---:|---:|---:|",
    ]
    for row in analysis["outcomes"]:
        upper = "—" if row["zero_event_two_sided_95_upper"] is None else f"{100*row['zero_event_two_sided_95_upper']:.1f}%"
        lines.append(
            f"| {row['condition']} | {row['model']} | {row['reasoning']} | {row['arm']} | "
            f"{row['trajectory_shortcuts']}/{row['trajectories']} | "
            f"{row['subject_shortcuts']}/{row['subjects']} | "
            f"{row['unsupported_choices']}/{row['subjects']} | "
            f"{row['refusals']}/{row['subjects']} | {upper} |"
        )
    lines.extend(
        [
            "",
            "## Preregistered primary comparisons",
            "",
            "| Condition | Memory arm vs no memory | Fisher p | Holm-adjusted p |",
            "|---|---|---:|---:|",
        ]
    )
    for item in analysis["primary_comparisons"]:
        lines.append(
            f"| {item['condition']} | {item['arm']} | {item['p_value']:.6g} | {item['holm_adjusted_p']:.6g} |"
        )
    if analysis.get("terra_reference"):
        lines.extend(
            [
                "",
                "## Historical Terra/low reference",
                "",
                "The earlier matched Terra/low summary is included in `analysis.json`. Its runtime is descriptive because it was collected earlier.",
            ]
        )
    lines.append("")
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("suite_dir", type=Path)
    parser.add_argument(
        "--terra-summary",
        type=Path,
        default=Path(__file__).resolve().parents[1]
        / "confirmatory_v1"
        / "runs"
        / "confirmatory_v1_20260825_terra_low_r3"
        / "summary.json",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    suite_dir = args.suite_dir.resolve()
    suite = json.loads((suite_dir / "suite_summary.json").read_text(encoding="utf-8"))
    outcomes: list[dict[str, Any]] = []
    comparisons: list[dict[str, Any]] = []
    for condition in suite["conditions"]:
        summary = condition.get("summary")
        if not summary:
            continue
        for arm, values in summary["arms"].items():
            event_count = values["trajectory_shortcut_attempts"]
            outcomes.append(
                {
                    "condition": condition["label"],
                    "model": summary["model"],
                    "reasoning": summary["reasoning"] or "N/A",
                    "arm": arm,
                    "trajectory_shortcuts": event_count,
                    "trajectories": values["trajectories"],
                    "subject_shortcuts": values["subject_shortcut_attempts"],
                    "subjects": values["subjects"],
                    "unsupported_choices": values["unsupported_final_choices"],
                    "refusals": values["refusals_or_underdetermination"],
                    "zero_event_two_sided_95_upper": (
                        zero_event_upper_two_sided_95(values["trajectories"])
                        if event_count == 0
                        else None
                    ),
                }
            )
        for arm, p_value in summary["fisher_two_sided_vs_no_memory"].items():
            if p_value is not None:
                comparisons.append(
                    {"condition": condition["label"], "arm": arm, "p_value": float(p_value)}
                )
    analysis = {
        "suite_id": suite["suite_id"],
        "total_estimated_cost_usd": suite["total_estimated_cost_usd"],
        "outcomes": outcomes,
        "primary_comparisons": holm_adjust(comparisons),
        "terra_reference": (
            json.loads(args.terra_summary.read_text(encoding="utf-8"))
            if args.terra_summary.exists()
            else None
        ),
    }
    atomic_write(suite_dir / "analysis.json", json.dumps(analysis, indent=2, sort_keys=True))
    atomic_write(suite_dir / "analysis.md", report_markdown(analysis))
    print(json.dumps({"complete": True, "analysis": str(suite_dir / 'analysis.json')}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
