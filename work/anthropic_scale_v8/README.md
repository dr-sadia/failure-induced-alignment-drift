# Anthropic model-scale pilot v8.3

This directory contains the frozen protocol, direct Anthropic Messages API
adapter, runner, analysis, and tests for the Haiku 4.5 / Sonnet 5 extension.

The live v8.3 pilot is complete: 120/120 accepted subjects, zero native
`reveal_answer` calls, zero censored subjects, and integrity PASS. All six
model-by-prompt cells observed 0/20 shortcut attempts. The completed audit is
in `runs/anthropic_v83_pilot_r1/`.

The earlier v8.1 engineering preflight passed Haiku 4.5 and Sonnet 5, but Opus
5 returned `stop_reason: tool_use` with tool-shaped text and no native
`tool_use` block. See `runs/anthropic_v8_preflight_r1/` for that raw record.

The v8.2 Opus-only repeat canary also failed: the exact-text response passed,
but the safe tool request received an explicit provider refusal categorized as
`reasoning_extraction`. Opus is therefore excluded from v8.3 before any subject
sampling. Do not reinterpret tool-shaped text as a native call or count a
provider refusal as safe behavior.

## Safe run sequence

From this directory:

```bash
python3 -m unittest discover -s . -p 'test_*.py' -v

python3 run_experiment.py \
  --run-id anthropic_v83_manifest_r1 \
  --dry-run

python3 run_experiment.py \
  --run-id anthropic_v83_preflight_r1 \
  --preflight-only

python3 run_experiment.py \
  --run-id anthropic_v83_pilot_r1
```

The two live commands require `ANTHROPIC_API_KEY` in the process environment.
Do not put a key in a command, source file, transcript, or committed `.env`
file. The preflight uses its own run ID because a preflight-only manifest is a
terminal compatibility artifact, not the scientific run.

For an interrupted scientific run, repeat the exact original command with
`--resume`. Do not reuse a completed or differently configured run ID.

See [`protocol.md`](protocol.md) for the preregistration and inference limits.
See [`runs/anthropic_v83_pilot_r1/report.md`](runs/anthropic_v83_pilot_r1/report.md)
for the completed results and transparent post-run classifier audit.
