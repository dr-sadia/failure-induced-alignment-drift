# GLM-5.3 goal-persistence pilot v9.1

This directory contains the frozen protocol, isolated runner, tests, raw run
artifacts, and censoring-aware analysis for the GLM-5.3 max-reasoning extension
of goal-persistence v7.2.

The preflight-time code and protocol hashes are recorded in
[`FROZEN_SHA256.txt`](FROZEN_SHA256.txt).

## Completed pilot

The live run `glm53_v91_pilot_r1` completed all 60 preregistered subjects with
zero infrastructure-error records. No subject emitted the prohibited
`reveal_answer` call. Across the three conditions, 20 subjects made an
unsupported final choice, 20 preserved underdetermination, and 20 were
reasoning-censored. All integrity checks passed. Total estimated cost,
including preflight, was $1.111586.

- [Result report](runs/glm53_v91_pilot_r1/report.md)
- [Machine-readable summary](runs/glm53_v91_pilot_r1/summary.json)
- [Run manifest](runs/glm53_v91_pilot_r1/manifest.json)
- [Raw subject-record archive](runs/glm53_v91_pilot_r1/subjects.tar.gz)
- [Archive SHA-256](runs/glm53_v91_pilot_r1/subjects.tar.gz.sha256)

## Safe validation

```bash
python work/glm53_goal_persistence_v9/test_v9.py
python work/glm53_goal_persistence_v9/run_experiment.py \
  --run-id glm53_v91_manifest_check \
  --dry-run
```

## Live preflight

The process must receive `ZAI_API_KEY` from its environment. Do not place the
key in a command, file, shell history, or repository artifact.

```bash
python work/glm53_goal_persistence_v9/run_experiment.py \
  --run-id glm53_v91_pilot_r1 \
  --preflight-only
```

## Live pilot

Use a fresh run ID after a standalone preflight, so the scientific run retains
its own exact preflight audit:

```bash
python work/glm53_goal_persistence_v9/run_experiment.py \
  --run-id glm53_v91_pilot_r1
```

If the runner pauses after subject sampling because of an infrastructure
failure, rerun the identical command with `--resume`. Do not resume a failed
preflight without first auditing and documenting the cause.
