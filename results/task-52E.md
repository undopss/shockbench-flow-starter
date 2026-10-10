# Task 52E — rehearsal: final.zip on new Full roots

**Status: root 1310201536 done (RSS 0.8173, 0 fallback weeks); root 1368250166 started 19:07 UTC, expected ~19:37.**

Notes: the first launch (18:32 UTC) spent 1440 s building references, then was killed at 19:00 UTC by the session's 30-min background-task limit (my mistake: default timeout). References were cached on disk, so the relaunch at 19:01 reused them (1 s). The second root (1368250166) needs ~24 min of references plus play, so I estimated it might not fit; root 1 finished at 19:07, which left time, so root 2 was launched at 19:07.

Code: agents/mpc_final from origin/task-51-ideas (params.json = final.zip, safety_weeks 5). Variant file: `{"final": {"agent": "agents/mpc_final"}}`.
Machine: 4 cores, so n_jobs 4.

| root | RSS | L1 | L2 | L3 | L4 | episodes per level | fallback weeks |
|---|---|---|---|---|---|---|---|
| 1310201536 | 0.8173 | 0.805 | 0.824 | 0.837 | 0.826 | 12 / 5 / 2 / 1 | 0 |
