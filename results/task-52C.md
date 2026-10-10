Status: root 1 done; running root 2 (491505603, started 19:11 UTC, expected ~19:48 UTC if refs take as long as root 1)

Task 52C: final.zip (agents/mpc_final from task-51-ideas, its params.json) alone on new Full roots, 20 episodes, 4 jobs.

| root | RSS | L1 | L2 | L3 | L4 | episodes L1/L2/L3/L4 | fallback weeks |
|---|---|---|---|---|---|---|---|
| 1312640225 | 0.8046 | 0.806 | 0.725 | 0.916 | 0.823 | 7/7/4/2 | 0 |

Runner output, root 1312640225 (references 1651 s, play 431 s):
```
full, entropy 1312640225, 20 episodes; diff = variant - final, 90% paired interval
variant                      RSS     L1     L2     L3     L4     diff  interval               better%  fallb
final                     0.8046  0.806  0.725  0.916  0.823  +0.0000  [+0.0000, +0.0000]     nan%      0
```

Choices: 4 jobs (nproc = 4, not 8). Episodes per level read from EpisodeSet.build(...).references (stratum).
