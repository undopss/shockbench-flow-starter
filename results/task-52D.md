# Task 52D: rehearsal, final.zip (agents/mpc_final from task-51-ideas) alone on new Full roots

**Status: done. Both roots played: 1268454195 RSS 0.8389, 1473186083 RSS 0.8716 (mean 0.855), 0 fallback weeks.**

| root | RSS | L1 | L2 | L3 | L4 | episodes per level | fallback weeks |
|---|---|---|---|---|---|---|---|
| 1268454195 | 0.8389 | 0.850 | 0.852 | 0.788 | 0.832 | 14 / 2 / 3 / 1 | 0 |
| 1473186083 | 0.8716 | 0.852 | 0.913 | 0.892 | 0.717 | 8 / 6 / 3 / 3 | 0 |

Notes / choices:
- Machine has 4 cores, so n_jobs = 4 (as in the task command).
- variants file: outputs/v52.json = `{"final": {"agent": "agents/mpc_final"}}`.
- Root 1268454195: references 1704 s, play 437 s (4 jobs). Results: outputs/variants/v52_full_1268454195_1010-1831/results.json (not committed, outputs/ gitignored).
- Root 1473186083: references 447 s (shorter than root 1, reason not investigated), play 424 s (4 jobs). Results: outputs/variants/v52_full_1473186083_1010-1910/results.json.
- Episodes per level were read from EpisodeSet.build(...).references["stratum"] after each run (cached, no rebuild).
- Nothing was uploaded.
