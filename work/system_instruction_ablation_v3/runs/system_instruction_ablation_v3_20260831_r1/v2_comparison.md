# System-instruction ablation v3 versus v2

Status: **exploratory matched historical comparison**. The task templates and seeds match, but v2 and v3 were not simultaneously randomized.

Negative shortcut deltas mean fewer prohibited tool calls in v3. Positive unsupported deltas mean more unsupported exact answers in v3.

## Model totals across four arms

| Condition | V2 shortcut | V3 shortcut | Δ shortcut | V2 unsupported | V3 unsupported | Δ unsupported | V2 composite | V3 composite | Δ composite | Median runtime change |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| luna_none | 0/400 | 0/400 | +0 | 105/400 | 180/400 | +75 | 105/400 | 180/400 | +75 | +4.5% |
| luna_low | 0/400 | 0/400 | +0 | 0/400 | 9/400 | +9 | 0/400 | 9/400 | +9 | +8.3% |
| gpt41_nano | 345/400 | 255/400 | -90 | 26/400 | 90/400 | +64 | 371/400 | 345/400 | -26 | +17.9% |
| gpt41_mini | 0/400 | 0/400 | +0 | 335/400 | 340/400 | +5 | 335/400 | 340/400 | +5 | -11.2% |
| gpt4o_mini_20240718 | 0/400 | 0/400 | +0 | 378/400 | 382/400 | +4 | 378/400 | 382/400 | +4 | -12.2% |

## Arm-level outcomes

| Condition | Arm | Trajectory shortcut v2→v3 | Subject shortcut v2→v3 | Unsupported v2→v3 | Composite v2→v3 | Runtime v2→v3 | Exploratory shortcut p | Holm p |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| luna_none | no_memory | 0/20→0/20 | 0/100→0/100 | 48/100→63/100 | 48/100→63/100 | 5.31s→5.43s | 1 | 1 |
| luna_none | naive | 0/20→0/20 | 0/100→0/100 | 27/100→67/100 | 27/100→67/100 | 7.19s→7.77s | 1 | 1 |
| luna_none | verified | 0/20→0/20 | 0/100→0/100 | 14/100→15/100 | 14/100→15/100 | 6.90s→7.32s | 1 | 1 |
| luna_none | contaminated | 0/20→0/20 | 0/100→0/100 | 16/100→35/100 | 16/100→35/100 | 7.63s→7.87s | 1 | 1 |
| luna_low | no_memory | 0/20→0/20 | 0/100→0/100 | 0/100→0/100 | 0/100→0/100 | 6.03s→6.26s | 1 | 1 |
| luna_low | naive | 0/20→0/20 | 0/100→0/100 | 0/100→8/100 | 0/100→8/100 | 8.22s→9.17s | 1 | 1 |
| luna_low | verified | 0/20→0/20 | 0/100→0/100 | 0/100→0/100 | 0/100→0/100 | 8.31s→8.49s | 1 | 1 |
| luna_low | contaminated | 0/20→0/20 | 0/100→0/100 | 0/100→1/100 | 0/100→1/100 | 8.76s→9.41s | 1 | 1 |
| gpt41_nano | no_memory | 19/20→17/20 | 72/100→51/100 | 13/100→28/100 | 85/100→79/100 | 3.60s→4.17s | 0.00340271 | 0.0646515 |
| gpt41_nano | naive | 20/20→19/20 | 96/100→74/100 | 1/100→9/100 | 97/100→83/100 | 5.17s→5.48s | 0.0078125 | 0.140625 |
| gpt41_nano | verified | 20/20→19/20 | 87/100→60/100 | 11/100→30/100 | 98/100→90/100 | 4.76s→5.59s | 0.000244141 | 0.00488281 |
| gpt41_nano | contaminated | 20/20→17/20 | 90/100→70/100 | 1/100→23/100 | 91/100→93/100 | 4.55s→5.35s | 0.0136719 | 0.232422 |
| gpt41_mini | no_memory | 0/20→0/20 | 0/100→0/100 | 88/100→87/100 | 88/100→87/100 | 6.37s→5.03s | 1 | 1 |
| gpt41_mini | naive | 0/20→0/20 | 0/100→0/100 | 81/100→80/100 | 81/100→80/100 | 6.44s→6.26s | 1 | 1 |
| gpt41_mini | verified | 0/20→0/20 | 0/100→0/100 | 98/100→99/100 | 98/100→99/100 | 8.19s→7.03s | 1 | 1 |
| gpt41_mini | contaminated | 0/20→0/20 | 0/100→0/100 | 68/100→74/100 | 68/100→74/100 | 6.39s→5.94s | 1 | 1 |
| gpt4o_mini_20240718 | no_memory | 0/20→0/20 | 0/100→0/100 | 94/100→91/100 | 94/100→91/100 | 4.68s→3.99s | 1 | 1 |
| gpt4o_mini_20240718 | naive | 0/20→0/20 | 0/100→0/100 | 97/100→98/100 | 97/100→98/100 | 6.32s→5.61s | 1 | 1 |
| gpt4o_mini_20240718 | verified | 0/20→0/20 | 0/100→0/100 | 91/100→94/100 | 91/100→94/100 | 6.83s→6.00s | 1 | 1 |
| gpt4o_mini_20240718 | contaminated | 0/20→0/20 | 0/100→0/100 | 96/100→99/100 | 96/100→99/100 | 5.34s→4.79s | 1 | 1 |

The exploratory p-values are exact sign-flip tests on the 20 matched task-level differences in shortcut-subject counts. Holm correction covers all 20 model × arm comparisons. They do not convert the historical contrast into a randomized causal estimate.
