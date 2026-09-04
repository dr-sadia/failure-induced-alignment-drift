# Hosted GLM-4.7-Flash reasoning pilot

This directory implements the frozen pilot in `protocol.md`. It calls Z.AI's
general API directly while preserving the evaluator-trust v4 puzzle, pressure
sequence, four memory arms, and coding boundary.

The first run contains one model condition: `glm-4.7-flash` with reasoning
enabled. Five trajectories × three generations × four arms produce 60 subjects.

## Validate without credentials or API calls

```bash
python3 -m unittest -v test_chat_adapter.py
python3 run_suite.py --dry-run --suite-id glm47_reasoning_dry_validation
```

## Credential

The runner reads only `ZAI_API_KEY`. Never paste the key into chat, a command
argument, source code, or committed shell history. `ZAI_BASE_URL` may override
the base URL, but the adapter refuses to send a key to any host other than
`api.z.ai`.

## Safe staged execution

Run the two-call capability preflight first. The helper requests the key
silently, passes it only through the child process environment, and clears it
on exit:

```bash
zsh run_with_private_key.zsh --preflight-only --suite-id glm47_reasoning_preflight_r1
```

If the preflight passes, run the frozen 60-subject pilot with a new suite ID:

```bash
zsh run_with_private_key.zsh --suite-id glm47_reasoning_pilot_r4
```

Before the valid pilot, run a three-generation `naive`-memory canary using the
same reasoning-aware token limits:

```bash
zsh run_with_private_key.zsh --suite-id glm47_reasoning_canary_r5 --trajectories 1 --generations 3 --arms naive
```

The valid restart uses one worker, a two-second minimum gap between request
starts, and 16,384-token task and memory limits. These conservative defaults
address Z.AI errors `1302`/`1305` and prevent provider reasoning from consuming
the entire completion budget. The partial `glm47_reasoning_pilot_r1` and
`glm47_reasoning_pilot_r2`, `glm47_reasoning_smoke_r3`, and
`glm47_reasoning_pilot_r3` are retained as excluded infrastructure-failure
audit artifacts and must not be included in behavioral analysis. The runner
now returns a nonzero status if any subject errors, truncations, or memory JSON
parse errors remain, and sampling stops automatically at the first such error.

The prohibited function is never executed. Z.AI currently lists
`glm-4.7-flash` API inference as free, but the runner still records usage and
the frozen price configuration; the provider dashboard remains authoritative.

Infrastructure-invalid attempts are enumerated in `excluded_runs.json`; their
raw artifacts are preserved, but their behavioral outcomes are not analyzed.
