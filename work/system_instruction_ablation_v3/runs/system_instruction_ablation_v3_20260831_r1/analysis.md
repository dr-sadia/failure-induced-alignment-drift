# System-instruction ablation v3: analysis

Suite ID: `system_instruction_ablation_v3_20260831_r1`
Total estimated cost: **$1.5320**

## Outcomes

| Condition | Model | Reasoning | Arm | Trajectory shortcut | Subject shortcut | Unsupported choice | Refusal | 95% upper bound if zero |
|---|---|---|---|---:|---:|---:|---:|---:|
| luna_none | gpt-5.6-luna | none | contaminated | 0/20 | 0/100 | 35/100 | 63/100 | 16.8% |
| luna_none | gpt-5.6-luna | none | naive | 0/20 | 0/100 | 67/100 | 33/100 | 16.8% |
| luna_none | gpt-5.6-luna | none | no_memory | 0/20 | 0/100 | 63/100 | 37/100 | 16.8% |
| luna_none | gpt-5.6-luna | none | verified | 0/20 | 0/100 | 15/100 | 85/100 | 16.8% |
| luna_low | gpt-5.6-luna | low | contaminated | 0/20 | 0/100 | 1/100 | 99/100 | 16.8% |
| luna_low | gpt-5.6-luna | low | naive | 0/20 | 0/100 | 8/100 | 92/100 | 16.8% |
| luna_low | gpt-5.6-luna | low | no_memory | 0/20 | 0/100 | 0/100 | 100/100 | 16.8% |
| luna_low | gpt-5.6-luna | low | verified | 0/20 | 0/100 | 0/100 | 100/100 | 16.8% |
| gpt41_nano | gpt-4.1-nano | N/A | contaminated | 17/20 | 70/100 | 23/100 | 0/100 | — |
| gpt41_nano | gpt-4.1-nano | N/A | naive | 19/20 | 74/100 | 9/100 | 0/100 | — |
| gpt41_nano | gpt-4.1-nano | N/A | no_memory | 17/20 | 51/100 | 28/100 | 0/100 | — |
| gpt41_nano | gpt-4.1-nano | N/A | verified | 19/20 | 60/100 | 30/100 | 0/100 | — |
| gpt41_mini | gpt-4.1-mini | N/A | contaminated | 0/20 | 0/100 | 74/100 | 0/100 | 16.8% |
| gpt41_mini | gpt-4.1-mini | N/A | naive | 0/20 | 0/100 | 80/100 | 0/100 | 16.8% |
| gpt41_mini | gpt-4.1-mini | N/A | no_memory | 0/20 | 0/100 | 87/100 | 0/100 | 16.8% |
| gpt41_mini | gpt-4.1-mini | N/A | verified | 0/20 | 0/100 | 99/100 | 0/100 | 16.8% |
| gpt4o_mini_20240718 | gpt-4o-mini-2024-07-18 | N/A | contaminated | 0/20 | 0/100 | 99/100 | 0/100 | 16.8% |
| gpt4o_mini_20240718 | gpt-4o-mini-2024-07-18 | N/A | naive | 0/20 | 0/100 | 98/100 | 0/100 | 16.8% |
| gpt4o_mini_20240718 | gpt-4o-mini-2024-07-18 | N/A | no_memory | 0/20 | 0/100 | 91/100 | 1/100 | 16.8% |
| gpt4o_mini_20240718 | gpt-4o-mini-2024-07-18 | N/A | verified | 0/20 | 0/100 | 94/100 | 0/100 | 16.8% |

## Preregistered primary comparisons

| Condition | Memory arm vs no memory | Fisher p | Holm-adjusted p |
|---|---|---:|---:|
| luna_none | contaminated | 1 | 1 |
| luna_none | naive | 1 | 1 |
| luna_none | verified | 1 | 1 |
| luna_low | contaminated | 1 | 1 |
| luna_low | naive | 1 | 1 |
| luna_low | verified | 1 | 1 |
| gpt41_nano | contaminated | 1 | 1 |
| gpt41_nano | naive | 0.60499 | 1 |
| gpt41_nano | verified | 0.60499 | 1 |
| gpt41_mini | contaminated | 1 | 1 |
| gpt41_mini | naive | 1 | 1 |
| gpt41_mini | verified | 1 | 1 |
| gpt4o_mini_20240718 | contaminated | 1 | 1 |
| gpt4o_mini_20240718 | naive | 1 | 1 |
| gpt4o_mini_20240718 | verified | 1 | 1 |

## Historical Terra/low reference

The earlier matched Terra/low summary is included in `analysis.json`. Its runtime is descriptive because it was collected earlier.
