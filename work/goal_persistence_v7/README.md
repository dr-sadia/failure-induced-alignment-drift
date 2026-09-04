# Goal-persistence experiment v7.2

This isolated experiment tests whether persistence instructions increase attempts to use an explicitly prohibited answer-reveal function. It compares neutral, bounded-persistence, and at-all-costs prompts in pinned GPT-4.1 nano, pinned full GPT-4.1, medium-reasoning GPT-5.6 Sol, and reasoning-enabled GLM-4.7-Flash. The full design is in [protocol.md](protocol.md).

Nothing here executes `reveal_answer`. A tool call is the measured behavior.

## Files

- `study_core.py`: frozen prompts, matched puzzles, outcomes, cost, and statistics.
- `provider_adapters.py`: fixed-host OpenAI Responses and Z.AI chat adapters.
- `run_experiment.py`: randomized, checkpointed runner with exact-manifest resume.
- `analyze.py`: censoring-aware tables, contrasts, integrity checks, and cost.
- `run_with_private_keys.zsh`: hidden key prompts; keys are not written to disk.
- `test_v7.py`: offline unit and payload tests.

## Offline validation

From this directory:

```sh
python3 -m unittest -v test_v7.py
python3 run_experiment.py --run-id v7_dry_validation --dry-run
python3 run_experiment.py --run-id v7_offline_simulation --simulate
```

Simulation output is prominently marked invalid for scientific inference.

## Live staged run

First run only the eight provider preflight calls:

```sh
./run_with_private_keys.zsh \
  --run-id goal_persistence_v7_20260903_r1 \
  --preflight-only
```

After inspecting `runs/goal_persistence_v7_20260903_r1/preflight.jsonl`, launch the frozen 240-subject run:

```sh
./run_with_private_keys.zsh \
  --run-id goal_persistence_v7_20260903_r1 \
  --resume
```

If an infrastructure failure pauses the suite, rerun the exact same command. Accepted subjects are skipped; the failed subject is retried as a fresh attempt. Do not change sample size, models, prompts, seed, token cap, retry count, or cost cap during resume.

The final outputs are `summary.json`, `report.md`, per-subject `record.json`, and full per-round `events.json`. Raw provider responses and provider-exposed GLM reasoning are stored. OpenAI hidden reasoning is unavailable.
