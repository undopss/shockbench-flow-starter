Status: running Full dev 20 (jpow, cq_a, cq_ab, cq_abk)

Plan: agents/mpc_cq = mpc_jpow + three chip-LP options in chips.py (off by default): cq_edges (shared capacity rows on every later edge of chip routes, net of cargo already bound for it), cq_drain (queued chip cargo drains FIFO at min(next-edge, kappa_ct) shares, like jp_qedge), cq_kappa (routes share kappa_ct at each chokepoint). Static count: 29 (commodity, later edge) groups shared by chip routes with different first edges (matches Andrii). Smoke test on Full dev ep 3: options on solve every week, chip LP CPU 0.15 s mean / 0.23 max (same as off).

## 1. Measurement (Full devpick:2,2,1,1, root 0, agents/mpc_jpow; `outputs/task-35/meas35.py`, log `meas_jpow.log`)
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
