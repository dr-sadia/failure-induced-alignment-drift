"""Offline checks for the v12 frozen design."""

from __future__ import annotations

import argparse
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import config
import run_experiment


class DesignTests(unittest.TestCase):
    def test_factorial_and_controls_are_complete(self) -> None:
        factorial = [cell for cell in config.CELL_SPECS.values() if cell["cell_type"] == "factorial"]
        controls = [cell for cell in config.CELL_SPECS.values() if cell["cell_type"] == "validation"]
        self.assertEqual(len(factorial), 24)
        self.assertEqual(len(controls), 3)
        self.assertEqual(len(config.CELL_IDS), 27)
        combinations = {
            (c["feasibility"], c["feedback"], c["persistence"], c["priority"])
            for c in factorial
        }
        self.assertEqual(len(combinations), 24)

    def test_substantive_pressure_is_not_in_system_prompt(self) -> None:
        lowered = config.SYSTEM_PROMPT.casefold()
        self.assertNotIn("at all costs", lowered)
        self.assertNotIn("highest-priority goal", lowered)
        cell = config.CELL_SPECS["impossible__failure__at_all_costs__explicit_priority"]
        task = config.task_prompt(cell)
        self.assertIn("at all costs", task)
        self.assertIn("takes priority", task)
        no_pressure = config.task_prompt(
            config.CELL_SPECS["impossible__failure__none__explicit_priority"]
        )
        bounded = config.task_prompt(
            config.CELL_SPECS["impossible__failure__bounded__explicit_priority"]
        )
        self.assertNotIn("at all costs", no_pressure.casefold())
        self.assertNotIn("at all costs", bounded.casefold())

    def test_feasible_and_impossible_tasks_differ_only_in_target_within_cell_pair(self) -> None:
        impossible = config.CELL_SPECS["impossible__neutral__none__explicit_priority"]
        feasible = config.CELL_SPECS["feasible__neutral__none__explicit_priority"]
        self.assertEqual(impossible["start"], feasible["start"])
        self.assertEqual(impossible["target"], 7)
        self.assertEqual(feasible["target"], 8)
        self.assertEqual(impossible["tool_mode"], feasible["tool_mode"])

    def test_validation_tool_semantics(self) -> None:
        absent = config.CELL_SPECS["control__tool_absent"]
        authorized = config.CELL_SPECS["control__explicit_authorization"]
        self.assertEqual([tool["name"] for tool in config.tools_for_cell(absent)], ["add_two"])
        self.assertNotIn("set_value", config.task_prompt(absent))
        self.assertEqual({tool["name"] for tool in config.tools_for_cell(authorized)}, {"add_two", "set_value"})
        self.assertIn("explicitly authorized", config.task_prompt(authorized))

    def test_default_manifest_has_2430_independent_jobs(self) -> None:
        args = argparse.Namespace(
            run_id="unit", subjects_per_cell=30, seed=config.DEFAULT_SEED, task_max_tokens=8192,
            max_decision_rounds=4, max_add_two_calls=8, models=list(config.MODEL_LABELS),
            cells=list(config.CELL_IDS), max_retries=6, cost_cap_usd=60.0,
            preflight_only=False, dry_run=True, simulate=False, resume=False,
        )
        manifest = run_experiment.make_manifest(args)
        self.assertEqual(len(manifest["randomized_jobs"]), 2430)
        self.assertEqual(len({job["job_id"] for job in manifest["randomized_jobs"]}), 2430)
        self.assertEqual(manifest["analysis"]["unit"], "independent fresh API context")


class PipelineTests(unittest.TestCase):
    def test_small_simulation_completes_with_integrity(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            argv = [
                "run_experiment.py", "--run-id", "sim", "--subjects-per-cell", "1",
                "--models", "openai_gpt41_nano", "--simulate", "--cost-cap-usd", "5",
            ]
            with mock.patch.object(run_experiment, "RUNS_ROOT", Path(directory)), mock.patch("sys.argv", argv):
                self.assertEqual(run_experiment.main(), 0)
            summary = Path(directory) / "sim" / "summary.json"
            self.assertTrue(summary.exists())


if __name__ == "__main__":
    unittest.main()
