Status: done. `agents/mpc_nodisp` (= mpc_cq + `nd_open`) beats mpc_cq on Full dev 20 (+0.0057 [+0.0023, +0.0094]) and on a fresh Full seed (root 910653604 ×20: +0.0025 [+0.0005, +0.0047]); Small dev 20 +0.0058 [-0.0002, +0.0122] (no harm). Real, but small (well under +0.05): most disposal is transport-bound and cannot be sold.

# Task 37: chips made and thrown away (`agents/mpc_nodisp`)

## 1. Measurement on mpc_cq (Full devpick:2,2,1,1, root 0)
`outputs/task-37/diag37.py` plays the agent the scorer's way (RSS 0.8769 = task 35's cq_abk) and records, per chip slot
and week, the disposal, the out-edge use, whether a route had room and its sink lost sales, and the chip LP's own plan
for that week. `an37.py` prints the tables (`meas_cq.txt`; `meas_open.txt` after the fix).

- Disposal: 16.4 M units/ep (0.35 T at pi). The LP itself planned 15.1 M of it at t=0, so it knew.
- Route-level reason (every lane or direct edge out of the slot, all edges, sink losing sales on arrival):
  - **(i) every route full: ~13.9 M** (85%). Top: fab_us_mature_1 raw mat 3.0 M, osat_tw mat 1.7 M, osat_kr le 1.25 M,
    fab_eu_mature_1 raw 1.1 M, osat_my le 1.0 M, fab_us_leading_3 raw le 0.74 M. These can't be sold. Not making them only
    saves the disposal cost (≤ 0.014 T/ep in the task-34 map). Fab power is freed only where the grid is short.
  - **(iii) a route had room and its sink lost sales: ~2.2 M chip_mat** (osat_cn→sink_sea 0.98 M, osat_my→sink_kr
    0.57 M, osat_sg/osat_ph→kr/row 0.35 M). Root cause (episode 0, `probe_cn.py`, `probe_sink.py`): chk_taiwan is 14%
    open for the whole episode. The chip LP **multiplies each lane's capacity by the chokepoint's open fraction**: the
    osat_cn→chk_taiwan→sink_sea lane was capped at 9.1k/wk, 14% of its 64k edge. Meanwhile sink_sea lost 30-67k mature
    chips a week and osat_cn sat at its storage cap, throwing chips away. In the simulator the open fraction only scales
    the strait's throughput (kappa = kappa0·mu·o, `marks.py` (9)), which here was 177k/wk, of which ~90k was used. The
    edge capacities are not scaled. `cq_kappa` already shares that kappa_ct in the LP, so the open factor double-counts.
  - (ii) spare out-capacity but no sink wanted them: ~0 once judged by routes, not first edges.
- Fab starts: the LP plans few starts at t=0 (it keeps the wafer buffer) while the simulator starts every wafer on hand.
  For example, fab_us_mature_1 runs 6.45 M real lots against 0.11 M planned at t=0. But the raw chips then appear as
  fixed WIP and the LP routes them optimally, so it only matters through fab power. Tasks 19, 29 and 32 already showed
  that lever is small, and sell_buffer is negative again here.

## 2. What was built (`agents/mpc_nodisp`, copy of mpc_cq; new options off in PARAMS)
- `nd_open` (chips.py): lanes through a partly open chokepoint keep their edge capacity. A fully closed one (o = 0)
  still closes them. Use it only with `cq_kappa` on, since that row is what limits the strait's throughput.
- `nd_openq` (chips.py): queued chip cargo at a partly open strait (0 < o < 0.5) counts as draining. No gain, kept off.
- `nd_open_e` (agent.py): the same as nd_open for the energy LP's tanker lanes. **Harmful** (-0.016), kept off.
- `sell_buffer` / `sell_frac` wired to PARAMS (task 19's option): negative or neutral, kept off.
- chips.py keeps `self.last` (the LP solution and layout) for the diagnostics. It stores references only, so no CPU cost.
- params.json = mpc_cq's + `"nd_open": true`. With `nd_open` off (`nd_off`), every devpick episode has J identical to mpc_cq.

## 3. Funnel vs `{"agent": "agents/mpc_cq"}` (variants `outputs/task-37/v37*.json`, results `res_v37*.json`)

Full devpick:2,2,1,1, root 0 (v37a):
```
full, entropy 0, 6 episodes; diff = variant - cq, 90% paired interval
variant                      RSS     L1     L2     L3     L4     diff  interval               better%  fallb
cq                        0.8769  0.881  0.882  0.868  0.840  +0.0000  [+0.0000, +0.0000]     nan%      0
nd_off                    0.8769  0.881  0.882  0.868  0.840  +0.0000  [+0.0000, +0.0000]     0.0%      0
open                      0.8841  0.885  0.899  0.868  0.844  +0.0073  [+0.0002, +0.0153]   100.0%      0  <-- better
open_e                    0.8609  0.852  0.875  0.868  0.825  -0.0160  [-0.0332, -0.0007]     0.0%      0  <-- worse
open_both                 0.8715  0.859  0.897  0.868  0.843  -0.0054  [-0.0188, +0.0095]    23.4%      0
sellbuf                   0.8729  0.875  0.882  0.864  0.831  -0.0040  [-0.0079, -0.0006]     0.0%      0  <-- worse
open_sellbuf              0.8839  0.886  0.902  0.864  0.837  +0.0071  [-0.0003, +0.0154]    94.8%      0
```
Full devpick, round 2 (v37c):
```
full, entropy 0, 6 episodes; diff = variant - cq, 90% paired interval
variant                      RSS     L1     L2     L3     L4     diff  interval               better%  fallb
cq                        0.8769  0.881  0.882  0.868  0.840  +0.0000  [+0.0000, +0.0000]     nan%      0
open                      0.8841  0.885  0.899  0.868  0.844  +0.0073  [+0.0002, +0.0153]   100.0%      0  <-- better
openq                     0.8725  0.875  0.878  0.868  0.835  -0.0044  [-0.0091, -0.0002]     0.0%      0  <-- worse
open_q                    0.8841  0.884  0.902  0.868  0.843  +0.0072  [+0.0001, +0.0152]   100.0%      0  <-- better
open_q_sellbuf            0.8809  0.881  0.898  0.864  0.841  +0.0040  [-0.0018, +0.0104]    76.1%      0
```
Full dev 20, root 0 (v37b):
```
full, entropy 0, 20 episodes; diff = variant - cq, 90% paired interval
variant                      RSS     L1     L2     L3     L4     diff  interval               better%  fallb
cq                        0.8398  0.852  0.859  0.799  0.760  +0.0000  [+0.0000, +0.0000]     nan%      0
open                      0.8456  0.855  0.872  0.802  0.764  +0.0057  [+0.0023, +0.0094]   100.0%      0  <-- better
open_sellbuf              0.8459  0.853  0.876  0.801  0.765  +0.0061  [+0.0019, +0.0106]    99.5%      0  <-- better
```
Fresh Full seed, root **910653604** (runner's `random`), episodes 0..19 (v37d):
```
full, entropy 910653604, 20 episodes; diff = variant - cq, 90% paired interval
variant                      RSS     L1     L2     L3     L4     diff  interval               better%  fallb
cq                        0.8445  0.814  0.891  0.840  0.780  +0.0000  [+0.0000, +0.0000]     nan%      0
open                      0.8470  0.815  0.893  0.844  0.787  +0.0025  [+0.0005, +0.0047]    98.2%      0  <-- better
open_sellbuf              0.8449  0.816  0.892  0.839  0.771  +0.0005  [-0.0019, +0.0030]    61.7%      0
```
Small dev 20, root 0 (v37e, no-harm check):
```
small, entropy 0, 20 episodes; diff = variant - cq, 90% paired interval
variant                      RSS     L1     L2     L3     L4     diff  interval               better%  fallb
cq                        0.7969  0.839  0.754  0.800  0.670  +0.0000  [+0.0000, +0.0000]     nan%      0
open                      0.8026  0.836  0.759  0.829  0.683  +0.0058  [-0.0002, +0.0122]    94.2%      0
```

## 4. Disposal and lost sales before/after (Full devpick, per episode; `before_after.txt`)
```
Full devpick:2,2,1,1, per episode. Disposal (M units), mpc_cq -> nd_open, slots with >= 0.05 M either side:
  fab_us_mature_1/chip_mat_raw      3.023 ->  3.005
  osat_cn/chip_mat                  1.825 ->  0.924
  osat_tw/chip_mat                  1.711 ->  1.567
  osat_kr/chip_le                   1.247 ->  1.404
  fab_eu_mature_1/chip_mat_raw      1.100 ->  0.695
  fab_cn_mature_1/wafer             0.901 ->  1.064
  osat_my/chip_le                   1.037 ->  1.037
  fab_us_mature_2/chip_mat_raw      0.837 ->  0.834
  osat_my/chip_mat                  0.814 ->  0.186
  fab_us_leading_3/chip_le_raw      0.744 ->  0.744
  osat_tw/chip_le                   0.659 ->  0.645
  fab_sea_mature_1/wafer            0.312 ->  0.312
  fab_us_leading_2/chip_le_raw      0.283 ->  0.283
  osat_ph/chip_le                   0.256 ->  0.233
  fab_eu_mature_1/wafer             0.196 ->  0.226
  fab_jp_memory_1/chip_le_raw       0.222 ->  0.175
  osat_sg/chip_mat                  0.208 ->  0.044
  osat_ph/chip_mat                  0.176 ->  0.045
  fab_us_leading_1/chip_le_raw      0.169 ->  0.169
  fab_tw_leading_1/wafer            0.157 ->  0.118
  fab_eu_leading_1/chip_le_raw      0.123 ->  0.067
  osat_vn/chip_le                   0.105 ->  0.123
  fab_us_mature_2/wafer             0.058 ->  0.089
  fab_us_mature_1/wafer             0.000 ->  0.076
  TOTAL                            16.354 -> 14.277
Lost sales (T USD at pi), sinks with >= 0.01 T:
  sink_us/chip_le      0.6698 -> 0.6721  (+0.0023)
  sink_sea/chip_le     0.2082 -> 0.2006  (-0.0076)
  sink_cn/chip_mat     0.1679 -> 0.1536  (-0.0142)
  sink_eu/chip_le      0.1654 -> 0.1675  (+0.0021)
  sink_row/chip_le     0.1626 -> 0.1614  (-0.0011)
  sink_jp/chip_le      0.1230 -> 0.1222  (-0.0008)
  sink_us/chip_mat     0.1157 -> 0.1153  (-0.0004)
  sink_kr/chip_le      0.1037 -> 0.1035  (-0.0002)
  sink_eu/chip_mat     0.0864 -> 0.0848  (-0.0016)
  sink_row/chip_mat    0.0669 -> 0.0604  (-0.0065)
  sink_sea/chip_mat    0.0603 -> 0.0568  (-0.0035)
  sink_in/chip_le      0.0374 -> 0.0387  (+0.0013)
  sink_jp/chip_mat     0.0250 -> 0.0231  (-0.0019)
  sink_kr/chip_mat     0.0183 -> 0.0155  (-0.0028)
  sink_in/chip_mat     0.0099 -> 0.0104  (+0.0005)
  TOTAL                2.0204 -> 1.9860  (-0.0343)
```
nd_open throws away 2.1 M fewer chips (mostly mature chips at osat_cn, osat_my, osat_sg, osat_ph and fab_eu_mature_1) and
loses 0.034 T/ep less in sales (sink_cn, sink_sea, sink_row mature). The transport-bound disposal (US fabs, osat_kr,
osat_tw, osat_my le) is unchanged.

## 5. sbf check (agents/mpc_nodisp, this cloud machine)
- Small: all checks passed; week 1 0.116 s, median 0.092 s, max 0.135 s per week (budget 2 s).
- Full: all checks passed; week 1 0.349 s, median 0.277 s, max 0.352 s per week (budget 4 s).
- 0 fallback weeks in every run.

## Verdict
- **Keep `nd_open`.** It fixes a real modelling bug and passes the bar: the interval is above 0 on Full dev 20 and on a
  fresh Full seed. It also helps on devpick and does no harm on Small. The size is +0.003 to +0.006, about 0.1-0.2 T/ep
  less than hoped. "Chips made and thrown away" is mostly not a leak: 85% of the disposed units had every route out
  full. The chip LP knows this and plans the disposal. The value at pi (0.27 T) is not reachable by routing or by
  making fewer chips. That agrees with task 19's 0.10 T ceiling with foresight.
- Dead: sell_buffer (again), nd_openq, and nd_open_e (the energy LP's version; I did not look into why it hurts).

## Port note (to mpc_combo + cq)
One change in `chips.py`, in `plan()`, where a lane's `cap` is multiplied by the open fraction:
`cap *= (1.0 if o_min > 1e-9 else 0.0) if self.nd_open else o_min`, where o_min is the existing min open fraction over
the lane's chokepoints. Add `nd_open=False` to `ChipPlanner.__init__` (`self.nd_open = bool(nd_open)`) and
`"nd_open": False` to PARAMS. Pass it in `agent.py`'s `ChipPlanner(...)` call and set `"nd_open": true` in params.json.
It needs `cq_kappa: true` (task 35). The `self.last` diagnostic block is not needed.

## Choices made without asking
- Full dev references were rebuilt on this machine (1348 s), because the tgz cache key does not match here (as task 34 found).
- I judged "why" by route, not by first out-edge (task 20's disp20 class). The first-edge view called 5.5 M "unused",
  but most of those routes were full at a later edge (Malacca→Suez) or banned (osat_cn→sink_us is sanctioned all episode).
- The fresh seed was drawn by the runner's `random`: root 910653604. No level-4-heavy check was done beyond its own draw.
- Small dev was run on cq vs open only.
