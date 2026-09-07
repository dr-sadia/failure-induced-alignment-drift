# Anthropic model-scale pilot v8.1

This directory contains the frozen protocol, direct Anthropic Messages API
adapter, runner, analysis, and tests for the Haiku 4.5 / Sonnet 5 / Opus 5
extension.

No live v8 subject has been sampled yet.

## Safe run sequence

From this directory:

```bash
python3 -m unittest discover -s . -p 'test_*.py' -v

python3 run_experiment.py \
  --run-id anthropic_v8_manifest_r1 \
  --dry-run

python3 run_experiment.py \
  --run-id anthropic_v8_preflight_r1 \
  --preflight-only

python3 run_experiment.py \
  --run-id anthropic_v8_pilot_r1
```

The two live commands require `ANTHROPIC_API_KEY` in the process environment.
Do not put a key in a command, source file, transcript, or committed `.env`
file. The preflight uses its own run ID because a preflight-only manifest is a
terminal compatibility artifact, not the scientific run.

For an interrupted scientific run, repeat the exact original command with
`--resume`. Do not reuse a completed or differently configured run ID.

See [`protocol.md`](protocol.md) for the preregistration and inference limits.
