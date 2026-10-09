Status: done. `agents/mpc_jpow` (qedge + arrfb 0.2) beats mpc_imit_room on every set: Full dev 20 +0.0091, fresh Full 12 +0.0061, devpick +0.0134, Small dev 20 +0.0171. Every 90% interval is above 0. It is real, but below the +0.05 bar.

# Task 30: more power for the JP / SEA / CN fabs (`agents/mpc_jpow`)

## Verdict
- **There is no supply lever of 0.1 T or more.** The oracle gets about the same fuel into JP / CN / SEA / EU as we do
  (JP crude +9%, every other fuel within 1%). It also lifts *less* crude and LNG at the sources than we do. Its extra
  JP/SEA fab power comes from timing (plus the base_first relaxation), not from more fuel. Stocking crude or LNG ahead
  did nothing (crude safety 6 weeks: +0.001 on devpick, -0.0006 on dev 20; LNG safety 5 weeks: -0.0001).
- **A real bug was the lever.** The tanker-queue drain forecast (`pplan.queue_release`, used by the energy LP and the
  pulse planner when `kappa_lp` is on) ignored the simulator's next-edge capacity cap (`chokepoint.py` release:
  `eta_u = min(1, u_e / queued onto e)`, applied before kappa). When an edge after a strait is cut (ep 5:
  Taiwan -> term_jp 1080 -> ~270/wk, Taiwan -> term_cn 1556 -> ~389), the planner saw ~1,800 GWh of JP crude "arriving
  next week" every week. So it never held crude to make a full week, and JP fabs stayed dark for 40+ weeks while the
  oracle ran them every week. Fixed as `jp_qedge`. A second option, `jp_arrfb`, corrects the rest of the planner's
  optimism from what actually arrived.
- Candidate: `agents/mpc_jpow` with its `params.json` (= mpc_imit_room's params + `"jp_qedge": true, "jp_arrfb": 0.2`).
  In `PARAMS` the new options are off by default. `jpow_off` (the same params as the baseline) reproduces the baseline
  exactly (0.8535 devpick). The change is in the energy-side forecast only and leaves pplan's valuation alone, so it
  should stack with task 29 (not tested).

## 1. Measurement (Full devpick:2,2,1,1, root 0, baseline mpc_imit_room)
Scripts are in `outputs/task-30/`:
- `diag30.py`: per grid, fuel and week, books each segment's shortfall to a cause.
- `src30.py`: sources and lanes.
- `oracle30.py`: the oracle LP's plan, about 15-130 s per episode.
- `cmp30.py`: agent vs oracle.
- `ppdbg30.py`: the planner's inputs at one grid.

Shortfall per segment (GWh/episode). Causes are booked in order ration > fuel held at the terminal > queued at a strait > source threw supply away > other:
```
grid      fuel     weeks    short   ration     held   queued  srclost lanefull    other
grid_jp   lng       36.3   121521   121521        0        0        0        0        0
grid_jp   crude     65.3    39867        0    24243    15624        0        0        0
grid_sea  lng       41.0   302994   302994        0        0        0        0        0
grid_sea  crude     82.7    61378        0     3567    42751    15061        0        0
grid_cn   lng       27.0    69889    69889        0        0        0        0        0
grid_cn   crude     45.8    54880        0    44801     9657      422        0        0
grid_eu   lng       22.0    45249    45249        0        0        0        0        0
grid_eu   crude     58.3    53073        0    33408        0     6542        0    13124
grid_kr   lng       34.8    65561    65414      147        0        0        0        0
grid_tw   lng       44.5    57818    57772       46        0        0        0        0
fab dark weeks (<50% of the best week): JP 79.7 (crude 65.7, lng ration 36.0), SEA 93.3 (crude 82.7), CN 46.7, EU 59.5
```
Agent vs oracle (GWh/episode; `cmp30.py`):
```
grid      fuel        need |   out ag   out or | shortwk ag    or
grid_jp   lng       558651 |   437129   437641 |       36.3  44.3
grid_jp   crude      93108 |    53241    57849 |       65.3  69.3
   grid_jp: fab energy agent 4398 oracle 7456 | home shed agent 156900 oracle 155290 | fab weeks >50% agent 24.3 oracle 63.2
grid_cn   crude     187200 |   132320   138479 |       45.8 103.2
   grid_cn: fab energy agent 22037 oracle 21191 | home shed agent 106358 oracle 92982 | fab weeks agent 57.2 oracle 78.0
grid_sea  lng/crude same fuel out as the oracle; fab energy agent 1197 oracle 4118 (base_first relaxation, task 18)
grid_eu   fab energy agent 10150 oracle 6434 | home shed agent 111627 oracle 102830
grid_kr   fab energy agent 26126 oracle 21824 | home shed agent  59400 oracle  51430
sources, supply / oracle lift / our lift per week: gulf crude 3298 / 1639 / 1811, us crude 3374 / 1385 / 1586, au lng 19982 / 9926 / 11393
```
- **JP:** same fuel and the same home shed as the oracle, but 63 fab weeks vs our 24. This gap is timing.
  Crude is the binding fuel. JP's crude segment (900/wk) is 5x its fab headroom (181), so any crude gap darkens the
  fab. In ep 5, JP crude arrives at only ~30-43% of need for 70 weeks. A homes-first agent can still run the fab about
  1 week in 3 by holding crude for two weeks, but our planner never did. Cause: the queue bug above.
- **CN / EU / KR:** we already match or beat the oracle's fab energy. The oracle sheds 8-13k GWh less there. That
  gap is the price of the pulses (task 29's domain).
- **SEA:** physically limited (task 18). The oracle's SEA fab power is the relaxation.
- "held" (fuel at the terminal while the grid is short) is the pulse working, not waste. `jp_fill` (never hold crude)
  costs **-0.039** on devpick.

## 2. What was built (`agents/mpc_jpow`, from mpc_imit_room; every option off by default in PARAMS)
- `jp_qedge` (bool): `queue_release(..., edge_cap=True)`. Each week, each strait's queued tanker cohorts release FIFO
  onto each next edge at most that edge's capacity left (eta_u), and only then share kappa_tb (eta_k), exactly as
  `chokepoint.release`. The energy LP's fixed arrivals and the pulse planner's arrivals both use it.
- `jp_arrfb` (EMA weight; 0.2 chosen): in `PulsePlanner.arrivals`, per destination (node, fuel), a running ratio of
  what arrived this week vs what was forecast a week earlier. Arrivals from week + 1 on are scaled by it, clipped to
  [0.2, 1]. This catches the optimism left after qedge (cargo still in the pipeline that will queue behind a cut edge).
- `jp_safety` (fuel -> safety weeks in the energy LP's floor at fab grids), `jp_fill` (release at least what fills this
  week's segment), `jp_grids`: measured and rejected. Left in, off.

## 3. Runner tables (`outputs/variants.py`; baseline `{"agent": "agents/mpc_imit_room"}` with its own params.json)
Full devpick:2,2,1,1, root 0 (`v30a`, `v30b`, `v30e`):
```
variant                      RSS     L1     L2     L3     L4     diff  interval               better%  fallb
base                      0.8535  0.845  0.875  0.842  0.846  +0.0000  [+0.0000, +0.0000]     nan%      0
jpow_off                  0.8535  0.845  0.875  0.842  0.846  +0.0000  [+0.0000, +0.0000]     0.0%      0
fill_crude                0.8149  0.816  0.822  0.811  0.779  -0.0386  [-0.0412, -0.0358]     0.0%      0  <-- worse
safe6_crude               0.8545  0.840  0.873  0.868  0.826  +0.0010  [-0.0012, +0.0030]    81.8%      0
fill_safe6                0.8221  0.817  0.829  0.840  0.758  -0.0314  [-0.0394, -0.0226]     0.0%      0  <-- worse
fill_safe6_lng5           0.8263  0.822  0.827  0.847  0.779  -0.0272  [-0.0355, -0.0179]     0.0%      0  <-- worse
safe_lng5                 0.8534  0.844  0.877  0.842  0.842  -0.0001  [-0.0016, +0.0015]    23.4%      0
qedge                     0.8645  0.860  0.875  0.864  0.843  +0.0110  [+0.0038, +0.0190]   100.0%      0  <-- better
qedge_safe6               0.8624  0.860  0.869  0.865  0.830  +0.0089  [+0.0017, +0.0170]   100.0%      0  <-- better
qedge_fb2                 0.8669  0.866  0.872  0.866  0.844  +0.0134  [+0.0028, +0.0253]   100.0%      0  <-- better
qedge_fb5                 0.8668  0.866  0.875  0.861  0.843  +0.0133  [+0.0021, +0.0260]   100.0%      0  <-- better
fb2                       0.8612  0.862  0.873  0.844  0.844  +0.0077  [-0.0010, +0.0174]    76.5%      0
```
Full dev 20, root 0 (`v30c`, `v30f`):
```
base                      0.8228  0.821  0.858  0.791  0.755  +0.0000  [+0.0000, +0.0000]     nan%      0
qedge                     0.8278  0.831  0.856  0.793  0.760  +0.0051  [+0.0007, +0.0096]    97.8%      0  <-- better
qedge_safe6               0.8222  0.821  0.853  0.796  0.755  -0.0006  [-0.0142, +0.0107]    49.8%      0
qedge_fb2                 0.8319  0.840  0.853  0.797  0.759  +0.0091  [+0.0033, +0.0149]    99.9%      0  <-- better
```
Fresh Full seed, **root 213168154** (picked at random by the runner), 12 episodes (`v30d`, `v30f`):
```
base                      0.8401  0.853  0.868  0.735  0.807  +0.0000  [+0.0000, +0.0000]     nan%      0
qedge                     0.8429  0.853  0.868  0.745  0.833  +0.0028  [-0.0058, +0.0098]    71.9%      0
qedge_fb2                 0.8462  0.858  0.868  0.748  0.840  +0.0061  [+0.0008, +0.0113]    97.5%      0  <-- better
```
Small dev 20, root 0 (no-harm check, `v30g`; qedge_fb2 = `agents/mpc_jpow` with its params.json):
```
base                      0.7823  0.811  0.751  0.795  0.670  +0.0000  [+0.0000, +0.0000]     nan%      0
qedge_fb2                 0.7994  0.840  0.756  0.806  0.676  +0.0171  [+0.0051, +0.0283]    99.6%      0  <-- better
```

## 4. sbf check (this cloud machine, 1 dev episode, `agents/mpc_jpow` with its params.json): all checks pass
- Small: week 1 0.105 s, median act 0.078 s, **max 0.119 s** (budget 2 s)
- Full: week 1 0.215 s, median act 0.203 s, **max 0.287 s** (budget 4 s). That is about the same as mpc_imit_room
  (task 26: median 0.230, max 0.302).

## Choices made without asking (nobody could be asked)
- `agents/mpc_jpow/params.json` turns the two winning options on, so `{"agent": "agents/mpc_jpow"}` is the candidate.
  `PARAMS` keeps every new option off, as the rule asks.
- I picked `jp_arrfb` 0.2 over 0.5 because they are equal on devpick and 0.2 is the smoother estimate. 0.5 was not run
  on dev 20 / fresh.
- The oracle comparison uses the clairvoyant LP itself (base_first relaxed), not `reachable_bound.py`'s MILP. Its fuel
  totals answer the "more fuel?" question directly. For the reachable fab power, CONTEXT's homes-first MILP result
  (≤ 0.003 T loss at JP/CN/KR) still applies.
- Measurement plays (`diag30`, `src30`) build the world without the naive fallback, as task 28 did. Every run had 0
  fallback weeks.

## Surprising
- The biggest JP lever was not fuel at all: a forecast that ignored one line of the simulator (eta_u) made the planner
  wait for crude that never came. The same bug also affected the energy LP's fixed arrivals.
- `jp_qedge` without the feedback is noisy on the fresh seed (+0.0028, interval includes 0). With `jp_arrfb` it holds
  on every set, and on Small it is the biggest gain (+0.017, L1 +0.029).
- Every agent-side "more fuel" idea failed. The Gulf crude source spills ~1,500 GWh/wk at its cap, and the oracle
  spills even more.
