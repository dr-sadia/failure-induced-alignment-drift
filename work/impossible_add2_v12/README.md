# Reduced same-level instruction study v12.1

This follow-up addresses the main construct-validity criticism of the earlier impossible-task study: the previous “at all costs” directive appeared at system level while the prohibition appeared at user level. V12 gives every cell the same neutral system prompt and puts all substantive instructions together in the user prompt.

V12.0 specified a complete 24-cell factorial but was never run. The reduced v12.1 design retains the prespecified comparisons needed to address the criticism: six primary failure-by-persistence cells, two priority-clarification cells, two feasible-task cells, and three validation controls. With 30 independent subjects per cell and three focal models, the live run contains 1,170 subjects. Persistent memory is deliberately excluded and should be studied separately.

See [protocol.md](protocol.md) for the exact design, prompts, outcomes, interpretation boundary, and resume rules.

## Offline verification

From this directory:

```bash
python3 -m unittest -v test_v12.py
python3 run_experiment.py --run-id v121_manifest_check --dry-run
python3 run_experiment.py --run-id v121_simulation --subjects-per-cell 1 --simulate --cost-cap-usd 5
```

## Live preflight

The environment must contain `OPENAI_API_KEY`, `ZAI_API_KEY`, and `GEMINI_API_KEY`. Never place keys in source files, shell history, logs, or the repository.

```bash
python3 run_experiment.py \
  --run-id v121_three_model_preflight_r1 \
  --subjects-per-cell 30 \
  --cost-cap-usd 30 \
  --preflight-only
```

Use a fresh run ID for the scientific run after inspecting the preflight. A preflight-only run is not resumable as a scientific run because its frozen directory already exists.

## Live pilot

```bash
python3 run_experiment.py \
  --run-id v121_three_model_pilot_r1 \
  --subjects-per-cell 30 \
  --cost-cap-usd 30
```

If paused, rerun the identical command with `--resume`. Do not change models, cells, sample size, token limit, retry count, seed, or cost cap.

The runner writes a frozen `manifest.json`, resumable status, raw per-attempt events, accepted subject records, `summary.json`, and `report.md`. The raw subject directory is excluded from Git until it is packaged as a checksummed audit archive.
