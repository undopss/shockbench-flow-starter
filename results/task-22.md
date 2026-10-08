Status: done. Verdict: the joint LP (mpc_det family) is far below mpc_fab3sell on Full (0.42-0.50 vs 0.85 on Full 6). No component where it wins by >= 0.15 T, so no hybrid was built.

# Task 22: one joint LP (package `mpc_det`) vs our three planners (`agents/mpc_fab3sell`)

Run: `uv run python outputs/task-22/gap22.py full 0 2,5,0,1,53,26 4 agents/mpc_fab3sell policy:mpc_det "policy:mpc_det@L+8" "policy:mpc_det@max(26,2L)" policy:mpc_det_safety`
(episodes = `devpick:2,2,1,1` on root 0 = 2, 5 (level 1), 0, 1 (level 2), 53 (level 3), 26 (level 4); same as at home).
Played the same way as `cost_breakdown.py`'s `policy:` path (same worlds, seeds, fallback). The oracle detail comes from the
oracle LP solution. Tables: `outputs/task-22/report22.py` -> `report6.txt`. Wafer/power diagnostic: `diag22.py`,
`diag22_report.py` -> `diag6.txt`. Raw data: `gap22_full_0_2-5-0-1-53-26.json`, `diag22.json`.
L = 24 on Full, so the horizons are H = 24 (`mpc_det`), 32 (`L+8`), 48 (`max(26,2L)`, the biggest in `H_SWEEP`).
0 fallback weeks for every player, 0 internal LP failures for mpc_det.

## 1. RSS and CPU (Full devpick 6)

| player | RSS (pooled) | level 1 / 2 / 3 / 4 | CPU s/week max | median (of episode medians) |
|---|---|---|---|---|
| **mpc_fab3sell** | **0.850** | 0.843 / 0.869 / 0.838 / 0.845 | not recorded here (task 18: 0.37 max) | |
| mpc_det (H=24) | 0.416 | 0.473 / 0.403 / 0.365 / 0.174 | 1.31 | 0.40 |
| mpc_det H=32 | 0.447 | 0.488 / 0.451 / 0.400 / 0.223 | 2.40 | 0.51 |
| mpc_det H=48 | 0.502 | 0.514 / 0.543 / 0.459 / 0.319 | **7.45 (over the 4 s budget on this machine)** | 0.68 |
| mpc_det_safety | 0.416 | 0.474 / 0.404 / 0.362 / 0.173 | 1.29 | 0.38 |

(CPU on this cloud machine; the scorer's speed vs this machine is unknown.) A longer horizon helps mpc_det (+0.09 from 24 to
48 weeks) but it stays 0.35 below us, and H=48 already breaks the CPU budget in its worst weeks. The +10% demand safety
does nothing. This agrees with CONTEXT.md's home numbers (mpc_det 0.372 on Full dev 20; here rss_all 0.379).

Why it was close on Small (0.717 vs our 0.767) but not on Full: not measured here. My guess (not verified): Full has
more base_first grids with chronic small shortfalls (CN, JP, SEA, EU) where our pulses/buffer matter, and longer lead
times than a 24-week window.

## 2. Where the joint LP wins and loses (T USD per episode, mean of 6)

```
component                  oracle   mpc_fab3sell  mpc_det  H=32     H=48     safety
freight                    0.0119   0.0179   0.0114   0.0116   0.0118   0.0114
tariff                     0.0073   0.0160   0.0046   0.0047   0.0048   0.0046
holding                    0.0175   0.0336   0.0149   0.0150   0.0154   0.0149
queue_holding              0.0004   0.0020   0.0001   0.0001   0.0001   0.0001
shortage                   1.7529   2.0888   3.0029   2.9844   2.9826   3.0003
disposal                   0.0002   0.0151   0.0035   0.0035   0.0035   0.0036
shed                       4.0048   4.1634   4.9926   4.8824   4.6455   4.9947
salvage_credit            -0.0003  -0.0059  -0.0011  -0.0011  -0.0011  -0.0011
TOTAL                      5.7947   6.3312   8.0291   7.9007   7.6626   8.0286
gap to oracle                       0.536    2.234    2.106    1.868    2.234
```

**Joint LP wins (vs mpc_fab3sell), all small:**
- shed at grid_tw: 0.139 vs 0.187 T (−0.05 T). That is the price of our TW pulse, and the pulse buys far more chips
  (TW lots 17.5M vs 7.1M per episode).
- freight/tariff/holding/queue/disposal/salvage together: −0.045 T. Mostly the price of our wafer buffer (holding) and
  of making 2.5x more chips (freight, tariff, disposal).
- chip_mat lost sales at sink EU/ROW: −0.006 T.
- Total of everything it does better ≈ 0.10 T, scattered over 8 lines, and most of it is the cost of our own wins.
  **No single component reaches the 0.15 T bar.**

**Joint LP losses (vs mpc_fab3sell), big:**
- chip shortage +0.89 T (H=48: +0.89 T): it starts **36M lots per episode vs our 92M (oracle 83M)**; every fab is lower,
  e.g. CN 7.3M vs 24.5M (oracle 23.5M), KR memory 7.2M vs 17.1M (15.2M), TW leading 3.5M vs 7.2M (7.2M).
- shed +0.48 to +0.83 T: worse fuel planning too, mostly grid_us (+0.26 to +0.38 T), grid_eu (+0.20 to +0.34 T),
  grid_cn (+0.03 to +0.10 T). So the joint LP isn't even better at the power side; our energy LP + kappa_lp beat it.

Shed per grid (T USD/episode):
```
grid        oracle   fab3sell  mpc_det  H=32     H=48     safety
grid_tw     0.1791   0.1873   0.1387   0.1404   0.1402   0.1388
grid_kr     0.2121   0.2498   0.2408   0.2314   0.2233   0.2415
grid_jp     0.6368   0.6458   0.6878   0.6872   0.6771   0.6875
grid_cn     0.3873   0.4416   0.5422   0.5163   0.4722   0.5419
grid_us     0.6793   0.6871   1.0640   1.0262   0.9515   1.0640
grid_eu     0.4243   0.4607   0.7974   0.7589   0.6598   0.7994
grid_sea    1.4506   1.4556   1.4748   1.4750   1.4745   1.4748
grid_in     0.0354   0.0356   0.0469   0.0469   0.0469   0.0469
```

Fab lots started (millions per episode):
```
fab                  oracle  fab3sell  mpc_det  H=32   H=48   safety
fab_tw_leading_1      7.17    7.18     3.57    3.56   3.54   3.59
fab_tw_mature_1       4.26    5.36     1.24    1.52   1.53   1.23
fab_us_leading_1      0.94    1.22     0.88    0.86   0.80   0.88
fab_kr_leading_1      1.36    2.30     0.67    0.69   0.70   0.67
fab_kr_memory_1      15.16   17.08     7.09    7.24   7.23   7.15
fab_us_leading_2      0.58    0.82     0.46    0.47   0.47   0.46
fab_jp_memory_1       5.92    3.38     0.76    0.93   0.93   0.74
fab_us_leading_3      0.40    1.16     0.28    0.29   0.30   0.28
fab_eu_leading_1      0.73    1.00     0.33    0.34   0.35   0.32
fab_row_leading_1     0.61    0.60     0.24    0.25   0.25   0.24
fab_cn_mature_1      23.49   24.48     7.88    7.66   7.27   7.85
fab_us_mature_1       3.22    6.45     2.56    2.72   2.81   2.56
fab_eu_mature_1       4.17    7.77     2.38    2.42   2.54   2.38
fab_sea_mature_1      4.60    1.33     0.41    0.49   0.52   0.41
fab_tw_mature_2       4.20    4.99     2.14    1.93   2.05   2.14
fab_us_mature_2       5.80    6.77     4.79    4.80   5.01   4.79
TOTAL                82.61   91.89    35.68   36.15  36.29  35.69
```

Lost sales by product x sink (T USD/episode), biggest lines:
```
                oracle   fab3sell  mpc_det  H=32     H=48     safety
chip_le@us      0.6312   0.6914   0.9062   0.9001   0.9064   0.9071
chip_le@sea     0.1333   0.2228   0.3834   0.3705   0.3738   0.3836
chip_le@eu      0.1486   0.1588   0.2615   0.2424   0.2434   0.2599
chip_mat@cn     0.1243   0.1781   0.2573   0.2565   0.2553   0.2581
chip_le@row     0.1505   0.1678   0.2094   0.2338   0.2309   0.2081
chip_le@jp      0.1062   0.1340   0.2055   0.2048   0.2052   0.2063
chip_le@kr      0.0913   0.1061   0.1609   0.1585   0.1572   0.1601
chip_mat@us     0.1182   0.1128   0.1593   0.1607   0.1566   0.1597
chip_le@in      0.0179   0.0426   0.1063   0.1063   0.1004   0.1050
chip_mat@sea    0.0387   0.0556   0.1062   0.1048   0.1057   0.1062
chip_mat@eu     0.0886   0.0885   0.0831   0.0824   0.0827   0.0835
chip_mat@row    0.0583   0.0668   0.0626   0.0618   0.0617   0.0621
```
The joint LP is worse at every sink except chip_mat@eu/row (−0.001 / −0.004 T).

## 3. Why the joint LP's fabs run less (diag6.txt: % of fab-weeks, all 16 fabs, 6 episodes)

| | full (lots ≥ 90% cap0) | wafer-limited (end wafer stock < 10% cap0) | wafers left but not run (power/other) |
|---|---|---|---|
| mpc_fab3sell | 34% | 27% | 39% |
| mpc_det H=48 | 11% | 39% | 50% |

It loses on **both** things our "hacks" fix:
- **Wafers** (what our `wafer_buffer` fixes): at grid_us, which has no power cuts, mpc_det's fabs are wafer-limited in
  63-88% of weeks (fab_us_leading_3: 88%, mean wafer stock 0.05 weeks of capacity). It ships wafers just in time on a
  persistence forecast; any delay leaves the fab idle.
- **Power under base_first** (what our pulses fix): CN/JP/EU fabs have wafers but don't run in 61-83% of weeks; CN is
  full in 0% of weeks (ours 52%). Its planning rules model base_first correctly week by week, but a persistence
  forecast never plans the "bank fuel, then a fully supplied week" cycle, so a grid that is a little short stays short.
- Its fuel plan is also worse (US/EU shed +0.3 T each), so the "it knows power and chips together" advantage doesn't
  show up anywhere in the numbers.

## 4. Hybrid?

Not built: the bar was a joint-LP win ≥ 0.15 T on some component, and the largest is 0.05 T (TW shed, which is the
price of our pulse). Using its fab lots/energy as targets would lower ours (36M vs 92M lots). The only thing the
numbers say it does better is spend less on freight/tariff/holding/disposal (≈ 0.045 T together), and that is mostly
the cost of making 2.5x more chips.

What *did* move mpc_det: horizon (+0.09 RSS from 24 to 48 weeks). Our chip LP uses chip_H 24 on a 104-week episode;
task 21 is the right place to test whether a longer chip horizon helps us (not tested here).

## Choices made without asking
- Used the explicit episode list 2,5,0,1,53,26 (the `devpick:2,2,1,1` result, checked once: levels 1,1,2,2,3,4) so the
  runs don't redraw the dev split every time (10 min here).
- H sweep: L (24), L+8 (32), max(26,2L) (48); no H beyond `H_SWEEP`, since 48 is already over the CPU budget at peak.
- Did not run Full dev 20: nothing to confirm, the gap (0.35 RSS) is far outside episode noise.
- Our agent's CPU wasn't metered by this script (`_metered_shim` returned no week times); no new agent code, so no `sbf check`.
