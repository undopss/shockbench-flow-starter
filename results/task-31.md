Status: measuring (level split done on task 20's data; the same split for mpc_imit_room is running)

# Task 31: the calm episodes (harm level 1)

## Step 1, first pass (task 20's per-episode data, `mpc_fab3sell`, Full dev 20; `outputs/task-31/levels31.py`)

**Level-1 episodes on Full are not calm.** Every one has 4-12 energy shocks, 1-4 militarised closures, 22-35 sanctions;
the naive rule's gap is 3.26 T/ep (level 2: 3.07, level 3: 3.70, level 4: 3.65). The harm level sorts episodes by the
damage to the *naive plan*, not by how many disruptions there are, so there is no calm regime to switch into.
Pulses are worth *more* at level 1 than elsewhere (pulses off: L1 RSS 0.800 → 0.582, L2 0.854 → 0.794).

| level | RSS | gap T/ep | shortage (LE / MAT) | shed | pulse shed price | other |
|---|---|---|---|---|---|---|
| 1 | 0.800 | 0.651 | 0.313 / 0.105 | 0.178 (KR 0.081, IN 0.064, EU 0.020, JP 0.020) | 0.206 | 0.056 |
| 2 | 0.854 | 0.449 | 0.183 / 0.114 | 0.118 | 0.114 | 0.035 |
| 3 | 0.790 | 0.779 | 0.430 / 0.100 | 0.216 | 0.255 | 0.033 |
| 4 | 0.739 | 0.953 | 0.519 / 0.124 | 0.276 | 0.197 | 0.035 |

Level 1 vs level 2: +0.13 T more chip_le shortage (eps 7, 5, 10), shed at KR (ep 5: 0.18 T) and at **grid_in** (ep 7:
0.32 T, a grid with no fabs, shedding ~1000 GWh *every week* for 30+ weeks while the oracle sheds 0). In a first replay
of ep 7 with `mpc_imit_room` that grid_in shed is gone (weeks 1-40: shed only in weeks 3-8 and 26), so the baseline
already fixed it (to be confirmed by the full split).
