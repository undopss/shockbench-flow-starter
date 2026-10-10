# Task 52A: rehearsal of final.zip (agents/mpc_final from task-51-ideas) on new Full roots

Status: root 1573653351 done (RSS 0.7985); root 1707488080 running (started 19:02 UTC).

Code: `agents/mpc_final` from origin/task-51-ideas (params.json = final.zip, safety_weeks 5, buffer_skip off).
Command: `uv run python outputs/variants.py full <root> 20 outputs/v52.json 4` (machine has 4 cores, so 4 jobs).

| root | RSS | L1 | L2 | L3 | L4 | episodes per level | fallback weeks |
|------|-----|----|----|----|----|--------------------|----------------|
| 1573653351 | 0.7985 | 0.905 | 0.846 | 0.745 | - | 4 / 6 / 10 / 0 | 0 |

Notes / choices:
- Root 1573653351: references took 1306 s (not cached for a new root), the agent played 20 episodes in 264 s with 4 jobs.
- Episodes per level are read from `EpisodeSet.build('full', 20, entropy=root).references` (the runner does not print them).
- No level-4 episodes were drawn in 20 episodes on this root (L4 = '-').
