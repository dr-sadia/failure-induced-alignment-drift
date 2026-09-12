# Gemini Flash susceptibility pilot (v11.0)

This isolated package reuses the frozen v10.2 impossible-add-two scaffold without editing or interrupting its active run. It compares three Gemini product tiers under the same task, pressure, memory, tool-execution, and scoring rules.

## Models and planned sample

| Tier label | Exact API model | Thinking | Subjects |
|---|---|---|---:|
| small | `gemini-3.5-flash-lite` | low | 72 |
| middle | `gemini-3.8-flash` | low | 72 |
| large | `gemini-3.1-pro-preview` | low | 72 |
| **Total** |  |  | **216** |

The labels are Google product tiers, not public parameter counts. The comparison is exploratory and does not by itself identify a causal effect of parameter scale.

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

The run is safely resumable with the same command. Outputs go under `runs/gemini_v11_pilot_r1/`; `status.json` is the live checkpoint and `report.md` plus `summary.json` are written at completion.

## Offline verification

```bash
python3 -m unittest -v test_gemini_v11.py
python3 run_gemini_experiment.py --run-id gemini_v11_sim --chains-per-cell 3 --subjects-per-chain 4 --cost-cap-usd 20 --simulate
```

Simulation output is only a pipeline test and is explicitly marked invalid for scientific inference.

