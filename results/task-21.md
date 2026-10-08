Status: done

# Task 21: our chip LP vs the oracle's chip decisions (Full devpick:2,2,1,1 = episodes 2, 5, 0, 1, 53, 26)

**Verdict: the chip LP is not where the gap is.** Even with perfect foresight of everything, the most that better chip
decisions could save is **0.156 T USD/episode** (routing 0.094 + which fab starts when 0.062), right at the 0.15 T bar.
Our chip LP fed perfect information (true demand, true future capacities, true fab starts, horizon 52, true material
supply, strait throughput, value-weighted or bigger wafer buffer, all at once) recovers only **0.02-0.04 T** of
shortage and **+0.002 to +0.006 RSS** on these 6 episodes. Every single cause is far below the bar. The chip LP's
model is accurate: it expects 56% (pi-weighted) fill over its window and gets 53%. The other part of the chip gap to
the oracle on these episodes (**0.180 T**: JP memory, SEA and CN fabs, eps 5/53/26) is **fab power**, not chip planning.
That is task 18's lever, and it is still the biggest one.

## How it was measured
- `outputs/task-21/diag21.py play <tag> <opts>` plays a hooked copy of `agents/mpc_fab3sell` (`outputs/task-21/ag`,
  same params.json; the hooks are off unless `chips.ORACLE`/`OPTS` are set by the script) on Full devpick the way
  cost_breakdown does, and records per week: lots/energy/wafers per fab, G_av of every grid (wrapped
  `sim.allocate_energy`), lost/served/demand, chip flows by stage, chip stock/disposal/queues, and the chip LP's own
  plan. CPU guards (`pp_deadline`, `chip_time_limit`, `time_limit`) set to 100 s in every test so CPU doesn't confound
  the tests; the baseline with guards off (`nolim`) gives exactly the same J as with guards on (`base`), RSS 0.8500.
  0 fallback weeks everywhere; the chip LP solved 104/104 weeks in every test.
- `diag21.py bound nolim` solves the package's oracle LP 3 ways on the same episodes:
  **free** (the clairvoyant plan), **avail** (each grid's weekly fab energy <= what the agent's grid had left after
  homes, G_av - min(y_bar, G_av); everything else free: wafers, starts, routing, with perfect foresight) and
  **capped** (each fab's weekly starts <= the agent's: the routing ceiling).
  agent - avail = the ceiling of everything the chip side (chip LP + wafer buffer) controls; avail - free = power.
- Tables: `report21.py`, `lpview21.py`, `routes21.py`, `timing21.py`, `wafer21.py`, `tests21.py` (outputs in `*.txt`;
  per-episode costs of every play and bound in `summary21.json`; the raw play JSONs are 16-28 MB each, not committed).

## 1. The decomposition (T USD/episode, chip shortage)
```
## 1. Shortage (lost sales) per episode, T USD: agent vs oracle LPs on the agent's trajectory
   capped = oracle with each fab's weekly starts <= the agent's (routing ceiling)
   avail  = oracle with each grid's weekly fab energy <= what the agent's grid had left after homes (G_av - y)
   free   = the clairvoyant plan
  ep   agent  capped   avail    free | a-capped  a-avail avail-free | lots M agent/capped/avail/free
   2   2.319   2.300   2.300   2.300 |    0.019    0.019      0.000 | 111.8/69.2/69.2/69.2
   5   2.015   1.894   1.843   1.457 |    0.121    0.172      0.386 | 93.5/84.5/84.2/100.8
   0   2.319   2.095   1.977   1.923 |    0.225    0.342      0.053 | 92.5/72.7/69.1/74.3
   1   1.404   1.340   1.299   1.235 |    0.064    0.105      0.064 | 102.2/90.1/91.4/95.6
  53   2.037   1.967   1.919   1.563 |    0.071    0.118      0.356 | 88.4/77.3/78.7/96.5
  26   2.438   2.375   2.258   2.038 |    0.063    0.180      0.220 | 62.9/53.8/55.5/59.3
mean   2.089   1.995   1.933   1.753 |    0.094    0.156      0.180
   shed T/ep: agent 4.163, capped 3.975, avail 3.972, free 4.005
```
Total gap to the clairvoyant plan on these 6 episodes: 0.536 T/episode (shortage 0.336, the rest mostly shed).
So: chip side 0.156 (0.094 routing given the agent's own starts + 0.062 which fab starts when), power side 0.180.
The chip-side part only appears after week ~56 (weeks 1-56: ~0 per 8-week block; 57-104: 0.02-0.03 per block),
mostly in episodes 0 (0.34), 26 (0.18), 5 (0.17) (`timing21.txt`).

## 2. Offline tests: what fixing each suspected cause gives (paired vs the baseline, same 6 episodes)
```
test         RSS     dRSS  d shortage   d shed  d total  min/max dRSS per ep   what
nolim     0.8500  +0.0000     +0.0000  +0.0000  +0.0000  +0.0000/+0.0000   baseline (mpc_fab3sell, CPU guards off)
tdem      0.8502  +0.0003     -0.0053  +0.0032  -0.0022  -0.0015/+0.0015   true future demand
tcap      0.8536  +0.0036     -0.0049  -0.0049  -0.0100  -0.0002/+0.0017   true future edge caps / open / prohibitions
tsup      0.8509  +0.0009     -0.0029  +0.0013  -0.0016  -0.0002/+0.0007   true future material supply
tfab      0.8561  +0.0061     -0.0174  -0.0074  -0.0250  -0.0005/+0.0027   true fab starts (the baseline's realized lots as fab cap)
h52       0.8517  +0.0017     -0.0098  -0.0009  -0.0107  -0.0011/+0.0018   chip_H 52 instead of 24
all       0.8556  +0.0057     -0.0232  +0.0000  -0.0218  -0.0015/+0.0028   tdem + tcap + tfab + H52
kshare    0.8536  +0.0037     -0.0103  +0.0015  -0.0090  -0.0006/+0.0020   strait container throughput (kappa_ct) in the chip LP
knet      0.8475  -0.0025     +0.0055  +0.0067  +0.0113  -0.0038/+0.0037   same, net of the queue's drain
lew5      0.8512  +0.0012     -0.0077  +0.0034  -0.0042  -0.0006/+0.0014   wafer buffer cost x5 at leading-edge/memory fabs
buf5tk    0.8502  +0.0003     -0.0134  +0.0079  -0.0046  -0.0035/+0.0019   wafer buffer 5 weeks at TW/KR fabs
buf5      0.8512  +0.0012     -0.0161  +0.0059  -0.0079  -0.0036/+0.0024   wafer buffer 5 weeks everywhere
mega      0.8534  +0.0035     -0.0381  +0.0207  -0.0144  -0.0024/+0.0028   everything above at once (+buffer 5, le x5, kappa share, true supply)
nobuf     0.7290  -0.1210     +0.5951  -0.1283  +0.4464  -0.0341/-0.0068   no wafer buffer (reference)
```
(d = test - baseline, T USD/episode; negative cost = better. `min/max dRSS per ep` = the RSS change when only that
episode is swapped.)
- **Demand forecast: not a cause.** The forecast the LP uses is unbiased (assumed/true 0.99, |error| 8-9% at every
  look-ahead); true demand: -0.005 T shortage.
- **Horizon / end of window: not a cause.** chip_H 52: -0.010 T.
- **Capacity assumptions (`fab_cap_mode`): the biggest single one, still small.** The LP's week-0 fab cap is right on
  average, but it plans to start only ~20% of what the fabs really start (`lpview21.txt`: e.g. kr_memory_1 plans 27k/week,
  starts 164k): fabs start every wafer they hold, the LP thinks downstream is full. Giving it the exact future starts:
  -0.017 T shortage, -0.025 T total, +0.006 RSS.
- **Future capacities / prohibitions / material outages: small.** -0.005 / -0.003 T.
- **Wafer buffer:** essential (no buffer: -0.121 RSS), but its size or a value weight barely matter (+0.000 to +0.001 RSS,
  less shortage paid for with more shed).
- **Strait container throughput:** chips do queue at the straits (1.65M chip_mat at Malacca on average, 0.33M at Taiwan;
  up to 8M chips+wafers queued in ep 0), and the chip LP treats queued cargo as arriving at once and ignores kappa_ct.
  Modelling it (lanes through a strait share kappa_ct, queued lots drain FIFO): +0.004 RSS; "net of the queue's drain"
  is worse (-0.003).
- **All at once (`mega`): -0.038 T shortage but +0.021 T shed, +0.0035 RSS.**

## 3. Where our decisions differ from the oracle's (devpick 6, M per episode)
Lots per fab and the deficit split (vs the free oracle; 'wafer' = the agent's fab had fewer wafers than the oracle
started that week, 'power' = it had the wafers):
```
## 2. Lots started per fab (M per episode, mean) and where the agent's fab-weeks fall short of the oracle's
   deficit weeks: oracle starts more than the agent. Reason of the agent's week: 'wafer' = its wafers on hand
   (end of last week) were below the oracle's starts; 'power' = otherwise (it had wafers, so power or R cut it)
fab                   agent   free  avail | deficit  wafer  power | excess | agent run% oracle run%
fab_tw_leading_1       7.18   7.17   6.46 |    2.36   0.88   1.48 |   2.37 |    50%    50%
fab_tw_mature_1        5.36   4.26   4.17 |    1.61   0.33   1.27 |   2.71 |    44%    35%
fab_us_leading_1       1.22   0.94   1.02 |    0.07   0.04   0.03 |   0.35 |    67%    51%
fab_kr_leading_1       2.30   1.36   1.87 |    0.30   0.09   0.21 |   1.23 |    62%    37%
fab_kr_memory_1       17.08  15.16  16.41 |    3.80   1.95   1.85 |   5.72 |    54%    48%
fab_us_leading_2       0.82   0.58   0.67 |    0.19   0.16   0.03 |   0.43 |    45%    31%
fab_jp_memory_1        3.38   5.92   2.36 |    4.53   0.00   4.53 |   2.00 |    23%    40%
fab_us_leading_3       1.16   0.40   0.41 |    0.03   0.02   0.01 |   0.79 |    63%    22%
fab_eu_leading_1       1.00   0.73   0.72 |    0.25   0.00   0.25 |   0.52 |    39%    29%
fab_row_leading_1      0.60   0.61   0.50 |    0.28   0.04   0.24 |   0.27 |    38%    39%
fab_cn_mature_1       24.48  23.49  19.49 |    9.38   0.23   9.15 |  10.37 |    54%    52%
fab_us_mature_1        6.45   3.22   3.23 |    0.24   0.11   0.13 |   3.47 |    70%    35%
fab_eu_mature_1        7.77   4.17   6.07 |    1.23   0.01   1.22 |   4.83 |    41%    22%
fab_sea_mature_1       1.33   4.60   1.22 |    4.05   0.06   3.98 |   0.77 |     9%    32%
fab_tw_mature_2        4.99   4.20   4.27 |    1.79   0.85   0.95 |   2.57 |    41%    34%
fab_us_mature_2        6.77   5.80   5.80 |    0.18   0.07   0.12 |   1.15 |    73%    63%

```
- The power-limited deficits vs the free oracle are at fab_cn_mature_1 (9.2M), fab_jp_memory_1 (4.5M), fab_sea_mature_1
  (4.0M): power, as in tasks 17/18.
- Against the **avail** oracle (same power as the agent), the deficits are mostly wafer-limited weeks at TW/KR fabs
  (`wafer21.txt`: ep 0 10.2M lots, ep 53 5.7M, ep 1 3.9M, ep 26 3.6M; tw_mature_2, kr_memory_1, tw_leading_1), while the agent
  ships more wafers in total (93M vs the oracle's 80M) and starts more at US/EU mature fabs whose chips are disposed of.
  Value-weighting the buffer (x5 at leading/memory fabs) or making it 5 weeks didn't move the score, so this
  allocation isn't the reachable lever either.
- Routing (`routes21.txt`, agent vs the oracle capped at the agent's starts): the differences are spread thin (each edge <=
  ~1.5M units: osat_cn->sink_cn +1.2M chip_mat, chk_taiwan->sink_cn +1.1M, less chip_mat_raw via chk_taiwan to osat_my).
  No single route explains it.

## 4. Lost sales by sink (agent / avail oracle / free oracle, T USD/episode)
```
   sink_sea chip_le   demand  0.587  agent  0.223  avail  0.176  free  0.133  a-free  0.089
    sink_us chip_le   demand  1.211  agent  0.691  avail  0.654  free  0.631  a-free  0.060
    sink_cn chip_mat  demand  0.337  agent  0.178  avail  0.155  free  0.124  a-free  0.054
    sink_jp chip_le   demand  0.338  agent  0.134  avail  0.119  free  0.106  a-free  0.028
    sink_in chip_le   demand  0.194  agent  0.043  avail  0.026  free  0.018  a-free  0.025
   sink_row chip_le   demand  0.395  agent  0.168  avail  0.155  free  0.150  a-free  0.017
   sink_sea chip_mat  demand  0.137  agent  0.056  avail  0.057  free  0.039  a-free  0.017
    sink_kr chip_le   demand  0.246  agent  0.106  avail  0.093  free  0.091  a-free  0.015
    sink_eu chip_le   demand  0.439  agent  0.159  avail  0.180  free  0.149  a-free  0.010
    sink_jp chip_mat  demand  0.080  agent  0.031  avail  0.024  free  0.023  a-free  0.009
   sink_row chip_mat  demand  0.092  agent  0.067  avail  0.062  free  0.058  a-free  0.009
    sink_kr chip_mat  demand  0.058  agent  0.022  avail  0.015  free  0.015  a-free  0.007
    sink_in chip_mat  demand  0.045  agent  0.010  avail  0.013  free  0.008  a-free  0.002
    sink_cn chip_le   demand  0.000  agent  0.000  avail  0.000  free  0.000  a-free  0.000
    sink_eu chip_mat  demand  0.103  agent  0.088  avail  0.087  free  0.089  a-free -0.000
    sink_us chip_mat  demand  0.285  agent  0.113  avail  0.118  free  0.118  a-free -0.005

```

## Why perfect information doesn't recover the 0.094 T routing ceiling (my reading, not tested)
The oracle's routing gain needs things a weekly shipping plan can't do: (1) a fab starts every wafer it holds, so
"start fewer here and keep the wafers for another fab" can only be done by not shipping wafers, and the buffer (worth
+0.12 RSS) needs them there; (2) the oracle co-plans fuel and chips (its shed in the capped/avail runs is 3.97 T vs the
agent's 4.16 T); (3) container cargo is released FIFO at the straits with no override for containers.

## Recommendation
Stop working on the chip LP: every chip-side fix tested is <= +0.006 RSS here, and the full chip-side ceiling with
perfect foresight is about the bar. The remaining big lever is power to the JP/CN/SEA fabs (0.18 T/episode on these
episodes, mostly eps 5, 53, 26), so continue task 18's direction. If someone wants a small sure gain: `tfab`-like
better fab-start forecasts (+0.006) and `kshare` (strait throughput in the chip LP, +0.004) could each be tried on
Full dev 20. Neither is in the agent (no building in this task).

Not done: no Small run (the task is Full only); 6 episodes only (devpick), so every test number above is rough (each
one is within about ±0.003 RSS per episode).
