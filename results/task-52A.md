# Task 52A: rehearsal of final.zip (agents/mpc_final from task-51-ideas) on new Full roots

Status: both assigned roots done: 1573653351 RSS 0.7985, 1707488080 RSS 0.8760 (mean 0.8373), 0 fallback weeks. Extra root 2053228721 (fresh, SystemRandom) started 19:23 UTC, killed at 19:52 UTC if unfinished.

Code: `agents/mpc_final` from origin/task-51-ideas (params.json = final.zip, safety_weeks 5, buffer_skip off).
Command: `uv run python outputs/variants.py full <root> 20 outputs/v52.json 4` (machine has 4 cores, so 4 jobs).

| root | RSS | L1 | L2 | L3 | L4 | episodes per level | fallback weeks |
|------|-----|----|----|----|----|--------------------|----------------|
| 1573653351 | 0.7985 | 0.905 | 0.846 | 0.745 | - | 4 / 6 / 10 / 0 | 0 |
| 1707488080 | 0.8760 | 0.861 | 0.922 | 0.869 | 0.688 | 10 / 5 / 4 / 1 | 0 |

Notes / choices:
- Root 1573653351: references took 1306 s (not cached for a new root), the agent played 20 episodes in 264 s with 4 jobs.
- Episodes per level are read from `EpisodeSet.build('full', 20, entropy=root).references` (the runner does not print them).
- No level-4 episodes were drawn in 20 episodes on this root (L4 = '-').
- Root 1707488080: references 395 s, play 265 s. Its single L4 episode gives the L4 column alone.
- Both roots finished by 19:12 UTC, so with ~30 min left I drew one extra fresh root (2053228721, random.SystemRandom) in the spirit of 'as many new roots as possible'; it runs under a hard kill so the last push still lands before 19:55 UTC.
