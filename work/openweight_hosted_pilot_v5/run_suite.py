#!/usr/bin/env python3
"""Run the four hosted open-weight pilot conditions sequentially."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

from chat_adapter import KEY_ENVIRONMENTS
from study_core import ARMS, SYSTEM_INSTRUCTIONS, SYSTEM_INSTRUCTIONS_SHA256, atomic_write


SAFE_SEGMENT = re.compile(r"^[A-Za-z0-9._-]+$")
BASE_URL_ENVIRONMENTS = {"zai": "ZAI_BASE_URL"}


def load_conditions(path: Path) -> list[dict[str, Any]]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, list) or not value:
        raise ValueError("conditions.json must contain a non-empty list")
    labels: set[str] = set()
    for condition in value:
        required = {
            "label",
            "provider",
            "model",
            "thinking",
            "currency",
            "input_price_per_million",
            "cached_input_price_per_million",
            "output_price_per_million",
            "cost_cap",
            "pricing_source",
        }
        missing = required - set(condition)
        if missing:
            raise ValueError(f"Condition is missing fields: {sorted(missing)}")
        label = condition["label"]
        if label in labels or not SAFE_SEGMENT.fullmatch(label):
            raise ValueError(f"Duplicate or unsafe condition label: {label}")
        if condition["provider"] not in KEY_ENVIRONMENTS:
            raise ValueError(f"Unsupported provider: {condition['provider']}")
        if condition["thinking"] not in {"enabled", "disabled"}:
            raise ValueError(f"Invalid thinking mode in {label}")
        labels.add(label)
    return value


def report_markdown(suite: dict[str, Any]) -> str:
    lines = [
        "# Hosted open-weight pilot v5: suite status",
        "",
        f"Suite ID: `{suite['suite_id']}`  ",
        f"Conditions completed: {suite['completed_conditions']}/{suite['planned_conditions']}  ",
        f"Mode: `{'preflight_only' if suite['preflight_only'] else 'pilot'}`",
        "",
        "| Condition | Provider | Model | Thinking | Preflight | Trajectory shortcut | Subject shortcut | Unsupported choice | Refusal | Subjects | Estimated cost |",
        "|---|---|---|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for condition in suite["conditions"]:
        preflight = condition.get("preflight") or condition.get("summary", {}).get("preflight")
        preflight_text = "passed" if preflight and preflight.get("ok") else "failed/missing"
        summary = condition.get("summary")
        if not summary:
            lines.append(
                f"| {condition['label']} | {condition['provider']} | {condition['model']} | "
                f"{condition['thinking']} | {preflight_text} | — | — | — | — | — | "
                f"{condition.get('estimated_cost', 0.0):.6f} {condition['currency']} |"
            )
            continue
        for arm, values in summary["arms"].items():
            lines.append(
                f"| {condition['label']} / {arm} | {condition['provider']} | {condition['model']} | "
                f"{condition['thinking']} | {preflight_text} | "
                f"{values['trajectory_shortcut_attempts']}/{values['trajectories']} | "
                f"{values['subject_shortcut_attempts']}/{values['subjects']} | "
                f"{values['unsupported_final_choices']}/{values['subjects']} | "
                f"{values['refusals_or_underdetermination']}/{values['subjects']} | "
                f"{values['subjects']} | {values['estimated_cost']:.6f} {condition['currency']} |"
            )
    lines.extend(["", "## Estimated provider charges by billing currency", ""])
    for currency, cost in sorted(suite["estimated_cost_by_currency"].items()):
        lines.append(f"- **{cost:.6f} {currency}**")
    lines.extend(
        [
            "",
            "Costs are reported in the provider's native billing currency. "
            "The Z.AI dashboard remains authoritative for actual billing.",
            "",
            "This is a small pilot for compatibility and effect direction. It is not sized for confirmatory inference.",
            "",
        ]
    )
    return "\n".join(lines)


def parse_args(conditions: list[dict[str, Any]]) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--conditions", nargs="*", choices=[item["label"] for item in conditions])
    parser.add_argument("--trajectories", type=int, default=5)
    parser.add_argument("--generations", type=int, default=3)
    parser.add_argument("--arms", nargs="+", choices=ARMS, default=list(ARMS))
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--request-min-interval-seconds", type=float, default=2.0)
    parser.add_argument("--seed", type=int, default=20260825)
    parser.add_argument("--task-max-tokens", type=int, default=16384)
    parser.add_argument("--memory-max-tokens", type=int, default=16384)
    parser.add_argument("--suite-id")
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    root = Path(__file__).resolve().parent
    try:
        conditions = load_conditions(root / "conditions.json")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Invalid condition configuration: {exc}", file=sys.stderr)
        return 2
    args = parse_args(conditions)
    if min(
        args.trajectories,
        args.generations,
        args.workers,
        args.task_max_tokens,
        args.memory_max_tokens,
    ) <= 0:
        print("sample sizes, workers, and token limits must be positive", file=sys.stderr)
        return 2
    if args.request_min_interval_seconds < 0:
        print("request-min-interval-seconds must be non-negative", file=sys.stderr)
        return 2
    suite_id = args.suite_id or dt.datetime.now(dt.timezone.utc).strftime(
        "openweight_hosted_v5_%Y%m%dT%H%M%SZ"
    )
    if not SAFE_SEGMENT.fullmatch(suite_id):
        print("suite-id may contain only letters, digits, dots, underscores, and hyphens", file=sys.stderr)
        return 2
    selected_labels = set(args.conditions or [item["label"] for item in conditions])
    selected = [item for item in conditions if item["label"] in selected_labels]
    suite_dir = root / "runs" / suite_id
    suite_manifest = {
        "suite_id": suite_id,
        "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "conditions": selected,
        "trajectories_per_arm": args.trajectories,
        "generations_per_trajectory": args.generations,
        "arms": args.arms,
        "subjects_per_condition": len(args.arms) * args.trajectories * args.generations,
        "planned_subjects": len(selected) * len(args.arms) * args.trajectories * args.generations,
        "workers_per_condition": args.workers,
        "request_min_interval_seconds": args.request_min_interval_seconds,
        "seed": args.seed,
        "task_max_tokens": args.task_max_tokens,
        "memory_max_tokens": args.memory_max_tokens,
        "execution": "sequential_conditions",
        "preflight_only": args.preflight_only,
        "system_instructions": SYSTEM_INSTRUCTIONS,
        "system_instructions_sha256": SYSTEM_INSTRUCTIONS_SHA256,
        "native_tool_call_preflight_required": True,
        "prohibited_tool_is_never_executed": True,
    }
    atomic_write(
        suite_dir / "suite_manifest.json",
        json.dumps(suite_manifest, indent=2, sort_keys=True),
    )

    if not args.dry_run:
        missing = sorted(
            {
                KEY_ENVIRONMENTS[item["provider"]]
                for item in selected
                if len(os.environ.get(KEY_ENVIRONMENTS[item["provider"]], "").strip()) < 8
            }
        )
        if missing:
            print(
                "Missing provider credential environment variable(s): "
                + ", ".join(missing)
                + ". No API calls were made.",
                file=sys.stderr,
            )
            return 2

    condition_results: list[dict[str, Any]] = []
    exit_code = 0
    for condition in selected:
        child_run_id = f"{suite_id}/{condition['label']}"
        command = [
            sys.executable,
            str(root / "run_model.py"),
            "--provider",
            condition["provider"],
            "--model",
            condition["model"],
            "--thinking",
            condition["thinking"],
            "--trajectories",
            str(args.trajectories),
            "--generations",
            str(args.generations),
            "--arms",
            *args.arms,
            "--workers",
            str(args.workers),
            "--request-min-interval-seconds",
            str(args.request_min_interval_seconds),
            "--seed",
            str(args.seed),
            "--currency",
            condition["currency"],
            "--input-price-per-million",
            str(condition["input_price_per_million"]),
            "--cached-input-price-per-million",
            str(condition["cached_input_price_per_million"]),
            "--output-price-per-million",
            str(condition["output_price_per_million"]),
            "--cost-cap",
            str(condition["cost_cap"]),
            "--task-max-tokens",
            str(args.task_max_tokens),
            "--memory-max-tokens",
            str(args.memory_max_tokens),
            "--run-id",
            child_run_id,
        ]
        base_url = os.environ.get(BASE_URL_ENVIRONMENTS[condition["provider"]], "").strip()
        if base_url:
            command.extend(["--endpoint", base_url])
        if args.preflight_only:
            command.append("--preflight-only")
        if args.dry_run:
            command.append("--dry-run")
        completed = subprocess.run(command, check=False)
        item: dict[str, Any] = {**condition, "exit_code": completed.returncode}
        child_dir = root / "runs" / child_run_id
        summary_path = child_dir / "summary.json"
        preflight_path = child_dir / "preflight.json"
        if summary_path.exists():
            item["summary"] = json.loads(summary_path.read_text(encoding="utf-8"))
            item["estimated_cost"] = item["summary"][
                "total_estimated_cost_including_preflight"
            ]
        elif preflight_path.exists():
            item["preflight"] = json.loads(preflight_path.read_text(encoding="utf-8"))
            item["estimated_cost"] = item["preflight"].get("estimated_cost", 0.0)
        else:
            item["estimated_cost"] = 0.0
        condition_results.append(item)
        if completed.returncode != 0:
            exit_code = completed.returncode
            break

    costs: defaultdict[str, float] = defaultdict(float)
    for item in condition_results:
        costs[item["currency"]] += float(item.get("estimated_cost", 0.0))
    completed_conditions = sum(
        item["exit_code"] == 0 and (args.dry_run or "summary" in item or "preflight" in item)
        for item in condition_results
    )
    suite_summary = {
        "suite_id": suite_id,
        "planned_conditions": len(selected),
        "completed_conditions": completed_conditions,
        "planned_subjects": suite_manifest["planned_subjects"],
        "preflight_only": args.preflight_only,
        "dry_run": args.dry_run,
        "estimated_cost_by_currency": dict(sorted(costs.items())),
        "conditions": condition_results,
        "exit_code": exit_code,
    }
    atomic_write(
        suite_dir / "suite_summary.json",
        json.dumps(suite_summary, indent=2, sort_keys=True),
    )
    atomic_write(suite_dir / "suite_report.md", report_markdown(suite_summary))
    print(
        json.dumps(
            {
                "complete": exit_code == 0,
                "suite_dir": str(suite_dir),
                "completed_conditions": completed_conditions,
                "estimated_cost_by_currency": dict(costs),
            },
            sort_keys=True,
        )
    )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
