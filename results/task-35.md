Status: sbf check + queue re-measure on cq_abk

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
