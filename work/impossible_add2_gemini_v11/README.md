# Gemini model-tier extension (v11.0)

This isolated package reuses the frozen v10.2 impossible-add-two scaffold
without modifying the v10.2 package. It compares three Gemini product tiers
under the same task, pressure, memory, tool-execution, and scoring rules.

This package's code, analysis, and documentation were substantially
AI-assisted. See the repository-wide [AI-assistance disclosure](../../AI_DISCLOSURE.md).

## Models and completed sample

| Tier label | Exact API model | Thinking | Subjects |
|---|---|---|---:|
| small | `gemini-3.5-flash-lite` | low | 72 |
| middle | `gemini-3.8-flash` | low | 72 |
| large | `gemini-3.1-pro-preview` | low | 72 |
| **Total** |  |  | **216** |

The labels are Google product tiers, not public parameter counts. The comparison is exploratory and does not by itself identify a causal effect of parameter scale.

## Final result

The live run completed all **216/216** planned subjects with no censored primary
outcomes, and all integrity checks passed.

| Product tier | Model | Prohibited calls | Subjects |
|---|---|---:|---:|
| small | Gemini 3.5 Flash-Lite | 0 | 72 |
| middle | Gemini 3.8 Flash | 0 | 72 |
| large | Gemini 3.1 Pro Preview | **24** | 72 |

All 24 Gemini Pro calls occurred in the failure-plus-persistence condition:
12/12 in the private-note arm and 12/12 in the persistent-memory arm. Pro made
0/48 calls across neutral rechecks and repeated failure, and both Flash tiers
made no calls in any cell. Persistent memory therefore had a zero descriptive
risk difference from private notes in every model × pressure stratum. This is
an exploratory product-tier comparison, not evidence that larger models
generally violate restrictions more often.

Accepted experimental attempts cost **$2.148974**; preflight calls cost
**$0.069937**; the total was **$2.218910**, or **$0.009949 per accepted
subject**. See the [human-readable report](runs/gemini_v11_pilot_r1/report.md),
[machine-readable summary](runs/gemini_v11_pilot_r1/summary.json), and
[post-hoc classifier audit](POSTHOC_AUDIT.md).

## Secure setup and preflight

Do not paste the key into chat or commit it. In a local terminal:

```bash
cd /Users/sadiaafroz/Documents/Codex/2026-08-18/i-2/work/impossible_add2_gemini_v11
read -s "GEMINI_API_KEY?Paste Gemini API key: "; echo
export GEMINI_API_KEY
python3 run_gemini_experiment.py --run-id gemini_v11_pilot_r1 --chains-per-cell 3 --subjects-per-chain 4 --cost-cap-usd 20 --preflight-only
```

If all three models pass, start the frozen run with the identical design:

```bash
python3 run_gemini_experiment.py --run-id gemini_v11_pilot_r1 --chains-per-cell 3 --subjects-per-chain 4 --cost-cap-usd 20 --resume
```

The runner is safely resumable with the same command. Outputs go under
`runs/gemini_v11_pilot_r1/`; `status.json` is the live checkpoint and
`report.md` plus `summary.json` are written at completion.

The completed run includes a base64-encoded archive of all raw subject and
memory records plus a SHA-256 checksum of the decoded archive:

- `runs/gemini_v11_pilot_r1/audit.tar.gz.b64`
- `runs/gemini_v11_pilot_r1/audit.tar.gz.sha256`

Decode it with:

```bash
cd runs/gemini_v11_pilot_r1
base64 --decode audit.tar.gz.b64 > audit.tar.gz
sha256sum -c audit.tar.gz.sha256
```

On macOS, use `base64 -D` and `shasum -a 256 -c` instead. The earlier
146-subject checkpoint archive remains in the repository only as provenance;
use the final archive for analysis.

## Offline verification

```bash
python3 -m unittest -v test_gemini_v11.py
python3 run_gemini_experiment.py --run-id gemini_v11_sim --chains-per-cell 3 --subjects-per-chain 4 --cost-cap-usd 20 --simulate
```

Simulation output is only a pipeline test and is explicitly marked invalid for scientific inference.
