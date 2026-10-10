Status: done (19:31 UTC) — both roots played, 0 fallback weeks

Task 52C: final.zip (agents/mpc_final from task-51-ideas, its params.json) alone on new Full roots, 20 episodes, 4 jobs.

| root | RSS | L1 | L2 | L3 | L4 | episodes L1/L2/L3/L4 | fallback weeks |
|---|---|---|---|---|---|---|---|
| 1312640225 | 0.8046 | 0.806 | 0.725 | 0.916 | 0.823 | 7/7/4/2 | 0 |
| 491505603 | 0.8362 | 0.833 | 0.842 | 0.819 | - | 11/8/1/0 | 0 |

Runner output, root 1312640225 (references 1651 s, play 431 s):
```
full, entropy 1312640225, 20 episodes; diff = variant - final, 90% paired interval
variant                      RSS     L1     L2     L3     L4     diff  interval               better%  fallb
final                     0.8046  0.806  0.725  0.916  0.823  +0.0000  [+0.0000, +0.0000]     nan%      0
```

Runner output, root 491505603 (references 469 s, play 415 s):
```
full, entropy 491505603, 20 episodes; diff = variant - final, 90% paired interval
variant                      RSS     L1     L2     L3     L4     diff  interval               better%  fallb
final                     0.8362  0.833  0.842  0.819      -  +0.0000  [+0.0000, +0.0000]     nan%      0
```
Root 491505603 drew no harm-level-4 episode (L4 shown as "-").

Choices: 4 jobs (nproc = 4, not 8). Episodes per level read from EpisodeSet.build(...).references (stratum).
