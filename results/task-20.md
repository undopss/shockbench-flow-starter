Status: done

# Task 20: where does mpc_fab3sell still lose points? (the map)

Measure only, nothing built. Agent `agents/mpc_fab3sell` (its own params.json), dev episodes, root 0, 20 Full + 20 Small.
Runs: `outputs/task-17/gap17.py {full,small} 0 dev agents/mpc_fab3sell 4` (references reproduced exactly on 20/20,
0 fallback weeks on both). New scripts in `outputs/task-20/`: `map20.py` (why each fab misses the oracle's lots, gap by
time), `disp20.py` (why chips are disposed of), `flow20.py` / `fabs20.py` (task 17's, made task-agnostic). Raw outputs:
`outputs/task-20/*.txt`. One extra ablation: the same agent with every pulse off (`nopulse_params.json`:
`pulse_plan` false, `pulse_weeks` 0, `pp_direct` [], `pp_split` false), to split shed into "price of the pulse" vs the rest.

| | Full dev 20 | Small dev 20 |
|---|---|---|
| RSS (pooled) | **0.8099** (lvl 1-4: 0.800 / 0.854 / 0.790 / 0.739) | **0.7815** (0.810 / 0.750 / 0.795 / 0.670) |
| gap to clairvoyant, T USD/ep | 0.708 (naive's gap 3.418) | 0.223 (naive's gap 0.930) |
| 0.01 RSS = | 0.034 T/ep | 0.0093 T/ep |
| chip shortage gap | 0.471 (67%): chip_le 0.361, chip_mat 0.110 | 0.111 (50%): chip_le 0.095, chip_mat 0.015 |
| power shed gap | 0.197 (28%) | 0.102 (46%) |
| everything else | 0.04 (tariff 0.010, holding 0.015, disposal 0.012, freight 0.006) | 0.01 |
| same agent, pulses off | RSS 0.6385: shed gap 0.004, chip gap 1.274 | RSS 0.7095: shed gap 0.067, chip gap 0.207 |

## The list (biggest separate leaks, T USD per episode; RSS points = Full 0.034 T, Small 0.0093 T)

1. **Chips made but never sold: they overflow OSATs / fabs whose outbound routes are already at capacity.**
   Full ≈ 0.18-0.26 T (5-7 RSS points), Small ≈ 0.06-0.10 T (6-10 points; the biggest chip leak on Small).
   Evidence: on Full the agent starts only 2.0M fewer chip_le lots than the oracle (29.6M vs 31.6M) but serves
   **7.2M fewer** chip_le (33.8M vs 40.9M); on Small lots are equal (6.58M vs 6.61M) but it serves 1.9M fewer.
   It disposes of 3.5M chip_le per Full episode (oracle 0.12M; 0.177 T at pi) and 1.6M on Small (0.08 T).
   `disp20.py`: **85% (Small) to 95% (Full) of the chip_le disposal happens in weeks when the slot's permitted out-edges were already
   shipping ≥95% of their capacity** (Full: osat_kr 0.95M, fab_us_leading_1/2/3 raw 1.13M, osat_tw 0.51M, osat_my 0.41M;
   Small: osat_my 0.58M, osat_kr 0.38M, osat_tw 0.29M, fab_jp_memory_1 raw 0.26M), and some sink of that product was
   losing sales in every one of those weeks. So the fix is upstream: send raw chips (and wafers/lots) to OSATs/fabs
   whose outflow can take them, i.e. plan with the out-edge capacities. Biggest sink gap it shows up in: sink_sea
   chip_le 0.147 T (Full), sink_us chip_le 0.078 T (Small).
   **Reachable without foresight: yes, largely** — the oracle made the same number of lots (Small) and got them sold;
   capacities are visible in `graph_now.u` (task 19 says the chip LP reads them, so why it still overflows is **not
   verified**: candidates are shared pool capacity across edges, chokepoint legs, or the 24-week LP planning raw-chip
   flows the OSAT can't push out).
   chip_mat waste is smaller in value (Full 5.2M raw at fab_us_mature_1/eu_mature_1 + 2.6M packaged ≈ 0.08 T;
   part of it with spare out-capacity, i.e. nobody needed it).
2. **The pulses' price in home shed: Full ≈ 0.19 T (≈5.5 points), Small ≈ 0.035 T (≈4 points).**
   With every pulse off, Full shed is at the oracle's level (gap 0.004) but chips get 0.80 T worse; with pulses the
   shed gap is 0.197: TW +0.061, KR +0.056, CN +0.052 (pp_direct), EU +0.015, JP +0.012 vs no-pulse.
   Reachable: partly. The oracle gets the fab power without the extra shed, but with foresight. A pulse that only
   releases when it covers homes + fabs for the week (task 14's idea) is the lever; ceiling ~0.19 T on Full.
3. **JP memory fab still under-powered: Full net 3.55M lots short (≈0.18 T gross at chip_le pi), Small 0.5M (≈0.025 T).**
   fab_jp_memory_1 runs at 21% of cap (oracle 45%); 98% of its missing lots are in weeks when grid_jp shed
   **≥1% of base load** (77% of all Full weeks have JP shed). This is not the "tiny shortfall" case CN was: JP needs
   real extra fuel. Reachable: unknown — task 3's homes-first MILP said JP fab power is reachable with foresight.
   Gross value is an upper bound: chip_le lost-sales at sink_jp is only 0.033 T, but JP memory chips can serve other sinks.
4. **Structural shed not caused by the pulse: Small ≈ 0.067 T (7 points!), Full ≈ 0 net** (grid_in +0.033, offset by
   CN/KR/TW shedding less than the oracle when the pulses are off).
   Small no-pulse shed gap by grid: EU 0.026, JP 0.022, KR 0.010, TW 0.009; with pulses in it is spread over Q1
   (weeks 1-13: 0.040, half of it the pulse) and the last 8 weeks (0.020). Full: grid_in (no fabs) 0.033 either way.
   Reachable: unknown; the oracle knows energy shocks/closures ahead, so part of it is foresight. The end-of-episode
   part (Small last 8 weeks 0.020, Full 0.014) looks like an end-of-horizon effect in the energy LP (not verified).
5. **Lost chip sales in the last weeks: Small weeks 45-52 chip gap 0.042 T (4.5 points), Full weeks 97-104 0.053 T
   (1.5 points).** On Small the chip gap is ~0 until week 26 and then 0.045 / 0.064 per quarter. Cause not verified
   (end-of-window value in the chip LP, sell_end, or item 1's capacity overflow piling up late).
6. **SEA + CN mature fabs: Full ≈ 0.065 T (≈2 points).** fab_sea_mature_1 1.7M vs 4.6M lots, fab_cn_mature_1 19.3M vs
   22.7M (CN mostly fixed since task 17's 6.0M). Remaining CN gap is in episodes 7, 41, 80 (energy shocks, CN shed
   ≥3% of base load at times); SEA is short ≥1% of base load in its missed weeks. Both upper bounds; Full only.
7. **KR memory timing: gross 0.28 T, net only 0.056 T (Full).** The agent makes 4.5M lots at KR memory in weeks the
   oracle doesn't and misses 5.2M in other weeks (KR shed ≥1%). Net effect small.
8. **Everything else ≈ 0.04 T Full / 0.01 T Small** (tariff, holding, disposal cost, freight): too small.

**Small vs Full.** Full: chips 67% of the gap, shed 28% and all of that shed is the pulse's price. Small: shed 46%
(two thirds of it structural, at EU/JP), chips 50% and on Small the chip gap is **almost entirely routing/overflow**
(lots equal to the oracle's). So item 1 helps both boards; item 2 helps Full; item 4 is mostly a Small (board) thing.

**Harm levels (Full).** Gap per level 0.651 / 0.449 / 0.779 / 0.953 T. Level 1 (50% weight): chips 0.417, shed 0.178,
disposal 0.018, tariff 0.016; its shed gap comes from two episodes (ep 2: 0.319 T, ep 7: 0.264 T).
No disruption type separates high- and low-gap episodes (|corr| ≤ 0.45 with n = 20); worst: ep 41 (1.70 T, lvl 4,
energy shocks at 6 grids + 3 closures) and ep 7 (1.12 T, lvl 1, KR energy shock ×9, CN dead).

## Tables

### Full dev 20: cost components (USD per episode)

```
component              naive        agent      perfect  agent-perfect share of gap
freight           1.6226e+10   1.7818e+10   1.2011e+10     5.8071e+09         0.8%
war_risk          1.2879e+08   1.5726e+08   1.2312e+08     3.4144e+07         0.0%
tariff            1.2881e+10   2.0937e+10   1.0608e+10     1.0329e+10         1.5%
holding           3.3975e+10   3.2666e+10   1.7414e+10     1.5252e+10         2.2%
queue_holding     5.4134e+09   1.5031e+09   5.9548e+08     9.0763e+08         0.1%
shortage          3.6170e+12   2.3046e+12   1.8332e+12     4.7141e+11        66.6%
disposal          8.7890e+09   1.2762e+10   2.9916e+08     1.2463e+10         1.8%
shed              5.6589e+12   4.2527e+12   4.0556e+12     1.9714e+11        27.9%
salvage_credit   -5.7899e+09  -5.8206e+09  -3.1459e+08    -5.5061e+09        -0.8%
TOTAL             9.3476e+12   6.6373e+12   5.9295e+12     7.0784e+11       100.0%
per level (gap, of which shortage / shed, T): 1: 0.651 (0.417/0.178)  2: 0.449 (0.296/0.118)  3: 0.779 (0.530/0.216)  4: 0.953 (0.642/0.276)
```

### Small dev 20: cost components (USD per episode)

```
component              naive        agent      perfect  agent-perfect share of gap
freight           2.4439e+09   2.7961e+09   1.1423e+09     1.6539e+09         0.7%
tariff            7.7037e+09   1.2218e+10   7.7391e+09     4.4785e+09         2.0%
holding           7.8261e+09   7.7328e+09   6.4211e+09     1.3117e+09         0.6%
queue_holding     3.0061e+09   6.9599e+08   2.8373e+08     4.1226e+08         0.2%
shortage          1.1774e+12   9.3720e+11   8.2654e+11     1.1066e+11        49.7%
disposal          5.2577e+09   3.9126e+09   4.2292e+08     3.4896e+09         1.6%
shed              2.2840e+12   1.8160e+12   1.7136e+12     1.0243e+11        46.0%
salvage_credit   -2.4191e+09  -2.4332e+09  -7.5414e+08    -1.6790e+09        -0.8%
TOTAL             3.4853e+12   2.7782e+12   2.5554e+12     2.2277e+11       100.0%
per level (gap, of which shortage / shed, T): 1: 0.156 (0.085/0.064)  2: 0.255 (0.113/0.126)  3: 0.231 (0.111/0.114)  4: 0.249 (0.134/0.106)
```

### Chip shortage by sink × product (T USD/episode, agent − oracle)

```
FULL  sink                 product    demand  agent  oracle   a-o  agent fill  oracle fill
      sink_sea             chip_le     0.584  0.305  0.158  0.147     47.8%      73.0%
      sink_cn              chip_mat    0.338  0.195  0.124  0.070     42.4%      63.2%
      sink_us              chip_le     1.217  0.692  0.623  0.069     43.2%      48.8%
      sink_eu              chip_le     0.437  0.169  0.130  0.039     61.2%      70.2%
      sink_in              chip_le     0.194  0.054  0.021  0.033     72.0%      89.1%
      sink_jp              chip_le     0.340  0.146  0.113  0.033     57.1%      66.7%
      sink_sea             chip_mat    0.136  0.070  0.039  0.031     48.7%      71.6%
      sink_row             chip_le     0.390  0.209  0.188  0.020     46.4%      51.7%
      sink_kr              chip_le     0.245  0.128  0.109  0.019     47.6%      55.5%
      (rest < 0.01 each)   by region: SEA 0.178, CN 0.070, US 0.060, JP 0.042, IN 0.038, EU 0.033, KR 0.026, ROW 0.024
SMALL sink_us              chip_le     0.877  0.460  0.381  0.078     47.6%      56.5%
      sink_jp              chip_le     0.248  0.190  0.174  0.016     23.2%      29.8%
      sink_cn              chip_mat    0.061  0.049  0.042  0.007     19.8%      30.5%
      (rest < 0.005 each)
```

### Chip balance (M units/episode) — the routing leak

```
FULL   chip_le  agent lots 29.61 served 33.75 | oracle lots 31.58 served 40.91   disposed chip_le* agent 3.51, oracle 0.12
       chip_mat agent lots 51.27 served 51.90 | oracle lots 48.15 served 62.64   disposed chip_mat* agent 8.24, oracle 0.17
SMALL  chip_le  agent lots  6.58 served 11.91 | oracle lots  6.61 served 13.81   disposed chip_le* agent 1.62, oracle 0.19
       chip_mat agent lots  3.53 served  5.09 | oracle lots  2.77 served  6.56   disposed chip_mat* agent 1.54, oracle 0.10
```

`disp20.py` (agent only; disposal by the state of the slot's outflow that week; all weeks had lost sales somewhere):

```
FULL  slot                          disposed at full out-edges / with spare out-capacity (M)   value at pi (T)
      osat_kr/chip_le               0.949 / 0.005    0.048
      fab_us_mature_1/chip_mat_raw  3.405 / 0.021    0.036
      fab_us_leading_3/chip_le_raw  0.610 / 0.004    0.031
      osat_tw/chip_le               0.513 / 0.023    0.027
      osat_my/chip_le               0.405 / 0.036    0.022
      fab_eu_mature_1/chip_mat_raw  0.610 / 0.775    0.014
      osat_tw/chip_mat              0.005 / 1.370    0.014
      fab_us_leading_1/chip_le_raw  0.276 / 0.002    0.014
      TOTAL                         8.50 / 3.23 (blocked 0.01)   0.263 T
SMALL osat_my/chip_le               0.416 / 0.000 (+0.162 no permitted edge)   0.029
      osat_kr/chip_le               0.379 / 0.000    0.019
      osat_tw/chip_le               0.290 / 0.004    0.015
      fab_jp_memory_1/chip_le_raw   0.259 / 0.031    0.015
      fab_eu_mature_1/chip_mat_raw  0.335 / 0.480    0.009
      TOTAL                         1.72 / 1.20 (blocked 0.24)   0.098 T
```

### Lots per fab vs the oracle, and why the agent missed the oracle's lots (Full, M lots/episode)

`map20.py`: per fab-week the oracle's extra lots (oracle − agent > 0) are booked to the agent's state that week.
cap = agent ran ≥90% of cap0·R; wafer = <5% of a week's wafers left; homes<1% / homes≥1% = grid shed homes that week
(below/above 1% of base load); power = no shed but fab energy short. surplus = lots the agent made beyond the oracle's.

```
fab                    grid   agent  oracle   cap  wafer homes<1% homes>=1% power  surplus  deficit $T (gross)
fab_tw_leading_1       tw      6.87    6.40  0.00   0.19   0.01     1.57    0.13    2.37    0.096
fab_tw_mature_1        tw      5.25    4.27  0.00   0.12   0.00     1.14    0.06    2.32    0.014
fab_us_leading_1       us      1.22    0.93  0.00   0.11   0.00     0.02    0.00    0.42    0.006
fab_kr_leading_1       kr      1.72    0.74  0.00   0.03   0.00     0.14    0.02    1.17    0.010
fab_kr_memory_1        kr     12.99   14.11  0.05   0.35   0.02     4.86    0.32    4.48    0.282
fab_us_leading_2       us      0.96    0.72  0.00   0.12   0.00     0.01    0.00    0.36    0.006
fab_jp_memory_1        jp      3.21    6.77  0.00   0.02   0.04     4.74    0.04    1.29    0.244
fab_us_leading_3       us      1.15    0.54  0.00   0.04   0.00     0.01    0.00    0.65    0.002
fab_eu_leading_1       eu      0.95    0.76  0.00   0.06   0.00     0.18    0.00    0.44    0.013
fab_row_leading_1      eu      0.54    0.61  0.00   0.12   0.00     0.15    0.00    0.20    0.014
fab_cn_mature_1        cn     19.34   22.75  0.00   0.05   6.53     4.51    0.18    7.86    0.116
fab_us_mature_1        us      6.19    2.62  0.00   0.10   0.00     0.06    0.00    3.72    0.002
fab_eu_mature_1        eu      7.36    4.79  0.00   0.10   0.01     1.07    0.00    3.77    0.012
fab_sea_mature_1       sea     1.69    4.58  0.00   0.25   0.00     3.76    0.01    1.13    0.042
fab_tw_mature_2        tw      5.12    4.12  0.00   0.30   0.00     1.05    0.05    2.41    0.015
fab_us_mature_2        us      6.32    5.03  0.00   0.15   0.00     0.04    0.00    1.47    0.002
TOTAL M lots                           0.07   2.11   6.63    23.30    0.80   34.07
TOTAL T USD (lots x pi)                0.003  0.064  0.072    0.709    0.028  0.809
lots by grid (agent/oracle, M): tw 17.2/14.8, us 15.8/9.8, kr 14.7/14.8, jp 3.2/6.8, eu 8.9/6.2, cn 19.3/22.7, sea 1.7/4.6
```

Missed lots are almost never wafer-limited (2.1M of 32.9M) or capacity-limited; they are power-limited in weeks
with a **≥1% home shortfall** (23.3M), not the tiny-shortfall case (6.6M, mostly CN). The gross column double-counts
timing (the agent makes 34M surplus lots in other weeks); net lots × pi is ≈0.18 T at JP, 0.03-0.06 T at
KR/CN/SEA, negative at TW/US/EU.

Small (`map_small.txt`): agent/oracle lots tw_leading 1.63/1.36, tw_mature 0.96/0.91, kr_memory 4.00/3.79,
jp_memory 0.61/1.11, eu_leading 0.35/0.35, eu_mature 2.57/1.86: only JP memory is short.

### Shed by grid (T USD/episode, agent − oracle), with and without pulses

```
FULL   grid    with pulses  pulses off      SMALL  grid   with pulses  pulses off
       tw         0.054       -0.007               eu        0.029       0.026
       in         0.033        0.033               jp        0.028       0.022
       cn         0.030       -0.022               kr        0.023       0.010
       kr         0.030       -0.026               tw        0.022       0.009
       jp         0.027        0.015
       eu         0.022        0.007
       us         0.005        0.005
       sea       -0.004       -0.001
       total      0.197        0.004                total     0.102       0.067
```

### By time (agent − oracle, T USD/episode)

```
FULL     wk 1-26  wk 27-52  wk 53-78  wk 79-104 | last 8 (97-104)
chip_le    0.003     0.092     0.126     0.140  |  0.043
chip_mat   0.009     0.028     0.038     0.036  |  0.010
shed       0.046     0.038     0.048     0.065  |  0.014
SMALL    wk 1-13  wk 14-26  wk 27-39  wk 40-52  | last 8 (45-52)
chip_le   -0.003     0.004     0.039     0.056  |  0.037
chip_mat  -0.001     0.003     0.006     0.008  |  0.005
shed       0.040     0.011     0.022     0.029  |  0.020
```

Late lots that can't reach a sink are now small (Full: 0.10M chip_le + 0.37M chip_mat started in the last 8 weeks,
was 1.7M + 2.8M for mpc_buffer: `sell_end` works).

## Surprises / notes

- vs task 17's map (mpc_buffer): CN is mostly fixed (19.3M lots vs 6.0M), chip gap 0.76 → 0.47 T, but shed gap grew
  0.13 → 0.20 T (CN/EU direct pulses). The biggest chip leak is now **distribution, not production**: the agent
  makes ~94% of the oracle's chip_le lots but sells 82% as many.
- Small's chip gap is entirely after week 26 and has no production deficit at all except JP memory.
- The F_Q cache in `cache/sbf-cache.tgz` doesn't match this container's Python (3.13.16), so each worker rebuilt it
  (~25 min for the first Full run, as task 19 said). After that Full 20 takes 5 min, Small 20 under 1 min here.
- Not verified: why the chip LP routes raw chips into OSATs/fabs whose outflow is saturated (item 1). That is the
  first thing task 21 / a follow-up should look at.
