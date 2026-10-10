Status: done (1 root; second root skipped for time)

Task 52F: final.zip (`agents/mpc_final` from task-51-ideas, own params.json, safety_weeks 5) alone on Full.

| root | RSS | L1 | L2 | L3 | L4 | episodes per level (L1/L2/L3/L4) | fallback weeks |
|---|---|---|---|---|---|---|---|
| 718502598 | 0.8414 | 0.856 | 0.816 | 0.862 | 0.788 | 14/2/2/2 | 0 |

Runner output as printed:

```
references ready in 2234 s (20 episodes)
  played final in 540 s: RSS 0.8414

full, entropy 718502598, 20 episodes; diff = variant - final, 90% paired interval
variant                      RSS     L1     L2     L3     L4     diff  interval               better%  fallb
final                     0.8414  0.856  0.816  0.862  0.788  +0.0000  [+0.0000, +0.0000]     nan%      0
```

Notes / choices:
- The machine has 4 cores, so 4 jobs (not 8).
- New root: references took 2234 s (37 min) + 540 s play = ~46 min per root. Root 1 finished 19:26 UTC; a
  second root (669099318) could not finish before the 19:55 UTC deadline, so it was not started.
- Episodes per level read from `EpisodeSet.build(...).references` strata (the runner does not print them).
- Results JSON: outputs/variants/v52_full_718502598_1010-1832/results.json. Nothing uploaded.
