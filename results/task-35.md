Status: done. `agents/mpc_cq` (= mpc_jpow + cq_edges + cq_drain + cq_kappa) beats mpc_jpow on Full: devpick +0.0100, dev 20 +0.0079, fresh Full 20 (root 1730880025) +0.0176, every 90% interval above 0. Small dev 20 -0.0025 (interval holds 0). Real, below the +0.05 bar, and it should stack with mpc_combo.

Plan: agents/mpc_cq = mpc_jpow + three chip-LP options in chips.py (off by default): cq_edges (shared capacity rows on every later edge of chip routes, net of cargo already bound for it), cq_drain (queued chip cargo drains FIFO at min(next-edge, kappa_ct) shares, like jp_qedge), cq_kappa (routes share kappa_ct at each chokepoint). Static count: 29 (commodity, later edge) groups shared by chip routes with different first edges (matches Andrii). Smoke test on Full dev ep 3: options on solve every week, chip LP CPU 0.15 s mean / 0.23 max (same as off).

# Task 35: shared downstream edges and strait queues in the chip LP (`agents/mpc_cq`)

## Verdict
- **Confirmed and fixed.** The chip LP planned every route at its own minimum edge capacity, and shared only first edges.
  Routes with different first edges then over-booked the edge after a strait. On mpc_jpow, **95% of all container
  cargo-weeks queued at straits were waiting for a full next edge**: 273M unit-weeks per Full episode against 289M
  units dispatched. Most of it was chip_mat on Malacca -> Suez, which held a standing ~7-week queue.
- With all three options on, the queue falls by 94% (277M to 17M unit-weeks). Chip lost sales fall by 0.028 T/ep and
  J falls by 0.027 T/ep on devpick.
- **RSS vs mpc_jpow:** Full devpick +0.0100 [+0.0044, +0.0163], Full dev 20 +0.0079 [+0.0031, +0.0128], fresh Full 20
  +0.0176 [+0.0094, +0.0279]. Small dev 20 is -0.0025 [-0.0057, +0.0005], which is no harm by the interval. Small is
  not a target.
- (a) `cq_edges` carries almost all of the gain. (b) `cq_drain` and (c) `cq_kappa` add little, within noise, but they
  never hurt on Full. I recommend all three (`cq_abk`), the best on the fresh seed and on devpick, and that is what
  `agents/mpc_cq/params.json` holds. If someone wants the minimal port, `cq_edges` alone gives about 85-95% of the gain.
- `sbf check` (on this container, `cq_abk`):
  - Small: median act 0.072 s, max 0.097 s per week (budget 2 s).
  - Full: median 0.206 s, max 0.272 s (budget 4 s).
  - The chip LP's CPU is unchanged by the options: smoke test 0.148 s on vs 0.140 s off, max 0.225 s.
- No fallback weeks in any run.

## What was built (`agents/mpc_cq`, copied from `agents/mpc_jpow`; every new option is off in PARAMS)
- `cq_edges` (chips.py): each edge at position >= 1 of a chip route (an out-edge of a strait) gets one row per week t.
  The row is: sum over slots j and positions with that edge of x[j, t - off_j] <= u_e - (container cargo already
  bound for e in week t). Here off_j is the travel time of the earlier legs. The cargo already bound includes pipeline
  shipments still to pass e, and queued lots (released at once, or per `cq_drain`'s schedule).
- `cq_drain` (chips.py `ChipPlanner._drain`): queued container lots no longer arrive all at once. They drain FIFO by
  arrival cohort, at most the next edge's capacity left (eta_u, pro rata) and then kappa_ct (eta_k), as
  `chokepoint.release` does. This is the container copy of `jp_qedge`. Fixed arrivals and the edge loads both use the
  schedule.
- `cq_kappa` (chips.py): routes through a chokepoint share its `graph_now.kappa.ct` at the week they reach it (net of
  cargo already bound). It rarely binds (0.1% of the queue was kappa-bound).
- Checks:
  - With the options off (`cq_off` = mpc_jpow's params.json), every devpick episode has the same J as mpc_jpow.
  - The smoke test (`outputs/task-35/smoke35.py`) calls the LP with the options on every week. It had 0 failures,
    which matters because the agent swallows exceptions.

**Port to mpc_combo (one line):** copy `agents/mpc_cq/chips.py` over mpc_combo's chips.py. mpc_combo is mpc_jpow plus
mpc_final, and its chips.py should be mpc_jpow's: check with a diff. Then add the 3 PARAMS
`"cq_edges"/"cq_drain"/"cq_kappa": False`, pass them to `ChipPlanner(...)` in agent.py, and set all three to true in
params.json.

## Choices made without asking
- The kappa_ct rows (`cq_kappa`) are a third option, not part of (a). The task listed kappa only in (b), and the
  measurement showed it is rarely binding.
- Fresh seed: the runner's `random` picked root 1730880025, episodes 0..19. Level 4 was not drawn on that seed.
- Small dev was run on jpow, cq_a and cq_abk only.
 (Full devpick:2,2,1,1, root 0, agents/mpc_jpow; `outputs/task-35/meas35.py`, log `meas_jpow.log`)
Container cargo (wafer + chips) still queued at a chokepoint at the end of a week, unit-weeks per episode (mean of 6):
```
closed 3,843,676  edgefull 273,186,547  kappa 301,308   (dispatched container units per episode: 288,700,114)
by_chk: chk_malacca 183.3M, chk_taiwan 55.1M, chk_cape 16.8M, chk_hormuz 11.4M, chk_suez 10.6M
by_edge (next edge full): sea.ct.chk_malacca.chk_suez 151.7M, sea.ct.chk_taiwan.sink_cn 28.3M, sea.ct.chk_malacca.sink_in 20.2M,
  cape.ct.chk_cape.chk_malacca 16.4M, sea.ct.chk_hormuz.chk_malacca 11.3M, sea.ct.chk_taiwan.sink_jp 10.3M, sea.ct.chk_suez.sink_eu 9.8M
by_k: chip_mat 225.6M, wafer 30.5M, chip_mat_raw 14.9M, chip_le_raw 6.3M
```
- The queue is almost all "next edge full" (99.9%); kappa_ct almost never binds; closures are small.
- Average delay ≈ 0.95 week per dispatched unit; the Malacca -> Suez container edge (u0 215k/wk) carries a standing
  chip_mat queue of ~1.5M units (~7 weeks of its capacity) on average, i.e. mature chips to EU / ROW arrive ~7 weeks late.
- Queue holding cost is negligible (0.001-0.005 T/ep). The price is lateness / lost sales (chip lost sales 1.4-2.4 T/ep
  per episode on these 6), which only the build can measure.
- After the fix (`cq_abk`, `meas_cq_abk.log`): closed 2.0M, edgefull 15.4M, kappa 0.005M unit-weeks/ep. The biggest
  remaining queue is Malacca -> Suez at 7.4M. Per episode, J (T) for jpow -> cq_abk: ep2 4.780->4.768,
  ep5 4.289->4.205, ep0 4.843->4.806, ep1 7.253->7.222, ep53 5.983->5.972, ep26 10.544->10.556.
- Static: 29 (commodity, later edge) groups shared by chip routes with >= 2 different first edges (same count as Andrii).

## 2. Funnel vs `{"agent": "agents/mpc_jpow"}` (variants `outputs/task-35/v35*.json`, results in `outputs/task-35/res/`)
`cq_off` = mpc_cq with mpc_jpow's params.json: same J on every episode as mpc_jpow (exact reproduction check).

Full devpick:2,2,1,1, root 0 (`v35a`):
```
variant                      RSS     L1     L2     L3     L4     diff  interval               better%  fallb
jpow                      0.8669  0.866  0.872  0.866  0.844  +0.0000  [+0.0000, +0.0000]     nan%      0
cq_off                    0.8669  0.866  0.872  0.866  0.844  +0.0000  [+0.0000, +0.0000]     0.0%      0
cq_a                      0.8756  0.881  0.877  0.870  0.833  +0.0087  [+0.0067, +0.0109]   100.0%      0  <-- better
cq_b                      0.8711  0.874  0.871  0.873  0.840  +0.0042  [-0.0015, +0.0106]    94.8%      0
cq_ab                     0.8765  0.882  0.881  0.868  0.837  +0.0096  [+0.0038, +0.0161]   100.0%      0  <-- better
cq_abk                    0.8769  0.881  0.882  0.868  0.840  +0.0100  [+0.0044, +0.0163]   100.0%      0  <-- better
```

Full dev 20, root 0 (`v35b`):
```
variant                      RSS     L1     L2     L3     L4     diff  interval               better%  fallb
jpow                      0.8319  0.840  0.853  0.797  0.759  +0.0000  [+0.0000, +0.0000]     nan%      0
cq_a                      0.8397  0.851  0.859  0.802  0.757  +0.0078  [+0.0033, +0.0125]    99.8%      0  <-- better
cq_ab                     0.8399  0.850  0.861  0.801  0.759  +0.0081  [+0.0031, +0.0133]    99.8%      0  <-- better
cq_abk                    0.8398  0.852  0.859  0.799  0.760  +0.0079  [+0.0031, +0.0128]    99.8%      0  <-- better
```

Fresh Full seed, root **1730880025** (picked by the runner's `random`), episodes 0..19 (`v35b`; no harm level 4 drawn):
```
variant                      RSS     L1     L2     L3     L4     diff  interval               better%  fallb
jpow                      0.8364  0.829  0.844  0.845      -  +0.0000  [+0.0000, +0.0000]     nan%      0
cq_a                      0.8516  0.848  0.857  0.855      -  +0.0152  [+0.0081, +0.0248]   100.0%      0  <-- better
cq_ab                     0.8524  0.847  0.860  0.855      -  +0.0161  [+0.0083, +0.0261]   100.0%      0  <-- better
cq_abk                    0.8540  0.848  0.865  0.854      -  +0.0176  [+0.0094, +0.0279]   100.0%      0  <-- better
```

Small dev 20, root 0 (`v35c`, no-harm check only):
```
variant                      RSS     L1     L2     L3     L4     diff  interval               better%  fallb
jpow                      0.7994  0.840  0.756  0.806  0.676  +0.0000  [+0.0000, +0.0000]     nan%      0
cq_a                      0.7976  0.837  0.756  0.804  0.672  -0.0018  [-0.0043, +0.0004]     8.5%      0
cq_abk                    0.7969  0.839  0.754  0.800  0.670  -0.0025  [-0.0057, +0.0005]     8.8%      0
```
