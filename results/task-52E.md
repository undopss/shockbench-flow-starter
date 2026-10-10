# Task 52E — rehearsal: final.zip on new Full roots

**Status: playing root 1310201536 (restarted 19:01 UTC).**

Notes: the first launch (18:32 UTC) spent 1440 s building references, then was killed at 19:00 UTC by the session's 30-min background-task limit (my mistake: default timeout). References were cached on disk, so the relaunch at 19:01 reused them (1 s). The second root (1368250166) needs ~24 min of references plus play, so it likely cannot finish before 19:55 UTC.

Code: agents/mpc_final from origin/task-51-ideas (params.json = final.zip, safety_weeks 5). Variant file: `{"final": {"agent": "agents/mpc_final"}}`.
Machine: 4 cores, so n_jobs 4.

| root | RSS | L1 | L2 | L3 | L4 | episodes per level | fallback weeks |
|---|---|---|---|---|---|---|---|
