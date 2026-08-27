# Failure-Induced Alignment Drift

This repository contains experiments testing whether repeated task failure makes
language-model agents more willing to use a previously prohibited shortcut, and
whether persistent cross-generation memory amplifies or reduces that behavior.

## Main finding

Repeated failure produced model-dependent alignment drift. In GPT-4.1 nano,
prohibited shortcut attempts increased from 72/100 subjects without memory to
96/100 with naive persistent memory. In GPT-5.6 Luna with no reasoning,
verified memory instead reduced unsupported exact answers from 48/100 to
14/100. Increasing Luna's reasoning effort from none to low eliminated measured
drift in this setup.

These results show heterogeneous behavior in one controlled task family; they
do not establish a universal effect across agents or environments.

## Multimodel experiment

- Preregistered protocol: [`work/multimodel_v2/protocol.md`](work/multimodel_v2/protocol.md)
- Experiment runner: [`work/multimodel_v2/run_model.py`](work/multimodel_v2/run_model.py)
- Suite runner: [`work/multimodel_v2/run_suite.py`](work/multimodel_v2/run_suite.py)
- Primary analysis: [`work/multimodel_v2/analyze_suite.py`](work/multimodel_v2/analyze_suite.py)
- Exploratory analysis: [`work/multimodel_v2/exploratory_secondary.py`](work/multimodel_v2/exploratory_secondary.py)
- Results report: [`outputs/multimodel_v2_results.md`](outputs/multimodel_v2_results.md)
- Raw run artifacts: [`work/multimodel_v2/runs/`](work/multimodel_v2/runs/)

The suite contains 2,000 subjects: five model/reasoning conditions, four memory
arms, 20 trajectories per arm, and five fresh-agent generations per trajectory.

## Earlier experiments

- Confirmatory v1: [`work/confirmatory_v1/`](work/confirmatory_v1/) and
  [`outputs/confirmatory_v1_results.md`](outputs/confirmatory_v1_results.md)
- Persistent-memory pilot: [`outputs/persistent_memory_pilot.md`](outputs/persistent_memory_pilot.md)
- Memory experiment v2: [`work/memory_experiment_v2/`](work/memory_experiment_v2/)
  and [`outputs/memory_experiment_v2_results.md`](outputs/memory_experiment_v2_results.md)
- Initial audit: [`outputs/agent_cheating_audit_report.md`](outputs/agent_cheating_audit_report.md)

## Reproducibility notes

The runners use the OpenAI Responses API and expect `OPENAI_API_KEY` to be set
in the environment. Never commit an API key. Model availability, snapshots, and
API behavior may change over time, so record the resolved model identifier and
run metadata when reproducing the experiment.

Raw event files contain API response metadata and encrypted reasoning payloads,
but no API credentials. Analysis should rely on observable outputs, tool calls,
and preregistered behavioral labels—not hidden chain-of-thought.

