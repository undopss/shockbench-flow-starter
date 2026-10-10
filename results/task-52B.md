Status: done (both roots, 19:31 UTC)

final.zip = agents/mpc_final from task-51-ideas (params.json safety_weeks 5), variants `{"final": {"agent": "agents/mpc_final"}}`, Full, 20 episodes, 4 jobs.

| root | RSS | L1 | L2 | L3 | L4 | episodes L1/L2/L3/L4 | fallback weeks |
|---|---|---|---|---|---|---|---|
| 1223270889 | 0.8337 | 0.837 | 0.778 | 0.901 | 0.912 | 9/8/2/1 | 0 |
| 333249916 | 0.7999 | 0.833 | 0.769 | 0.744 | 0.804 | 7/7/1/5 | 0 |

Root 1 table as printed:
```
full, entropy 1223270889, 20 episodes; diff = variant - final, 90% paired interval
variant                      RSS     L1     L2     L3     L4     diff  interval               better%  fallb
final                     0.8337  0.837  0.778  0.901  0.912  +0.0000  [+0.0000, +0.0000]     nan%      0
```
Wall time: references 1726 s, play 444 s.

Root 2 table as printed:
```
full, entropy 333249916, 20 episodes; diff = variant - final, 90% paired interval
variant                      RSS     L1     L2     L3     L4     diff  interval               better%  fallb
final                     0.7999  0.833  0.769  0.744  0.804  +0.0000  [+0.0000, +0.0000]     nan%      0
```
Wall time: references 465 s, play 446 s.

Choices: n_jobs = 4 (nproc = 4, not 8). Episodes per level read from the cached references (EpisodeSet.build, stratum).
No third root started: finished at 19:31 UTC, and a new root (references 8-29 min + play ~7.5 min) could not be pushed safely before 19:55 UTC.
