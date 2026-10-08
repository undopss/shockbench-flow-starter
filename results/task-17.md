Status: done

# Task 17: where is mpc_buffer's remaining gap on Full?

Run: `uv run python outputs/task-17/gap17.py full 0 dev agents/mpc_buffer 4` (all 20 Full dev episodes, root 0; `episode()` is
`outputs/cost_breakdown.py`'s plus oracle per-fab lots / per-grid shed / per-sink lost from the LP solution, weekly
records, OSAT packaging and the omega events). References reproduced exactly on 20/20, 0 fallback weeks,
**RSS 0.7363** (level 1/2/3/4: 0.712 / 0.798 / 0.720 / 0.689), same as the team's number. Tables: `report17.py`,
`flow17.py`, `fabs17.py` on `outputs/task-17/gap17v2_full_0_dev_mpc_buffer.json`; raw outputs in `outputs/task-17/*.txt`.
Nothing was built (measure-only task).

## Where the next 0.1 RSS is (≈ 0.33 T USD/episode)

Gap to clairvoyant: **0.93 T USD/episode** (naive's gap 3.42 T). Chip shortage 0.76 T (82%), power shed 0.13 T (14%),
everything else 0.04 T (freight, tariff, holding, disposal: too small to chase).

1. **CN, JP and SEA fabs are switched off by tiny home shortfalls (biggest lever, ceiling ≈ 0.3 T ≈ +0.09 RSS).**
   At grid_cn / grid_jp / grid_sea the agent's fabs run under 5% of capacity in **80% / 87% / 90% of all
   episode-weeks**, and every one of those weeks is a week with home shed (base_first: fabs get nothing). They are never
   short of wafers (0.0% of weeks). The shortfall is tiny: median 706 GWh/week at CN = **0.4% of CN's 180k GWh base
   load**, while CN's fab draw at full capacity is only 393 GWh/week. The oracle starts 4x the lots there:
   fab_cn_mature_1 22.7M vs 6.0M, fab_jp_memory_1 6.8M vs 1.7M, fab_sea_mature_1 4.6M vs 0.8M per episode.
   72-87% of the oracle's fab energy at these grids is given in weeks where the oracle itself sheds homes (the
   base_first relaxation), so a real agent can only get it by moving fuel between weeks (pulses), which
   `outputs/reachable_bound.py` says is possible with foresight.
   CN is bimodal: in 5/20 episodes (0, 2, 10, 14, 69) CN isn't chronically short and the agent's CN fab runs like
   the oracle's (15-27M lots); in the other 15 it makes ~1M lots (oracle 15-30M; in ep 3 the oracle can't run it either).
   Value, rough: gross chips CN 16.7M × 10.4k + JP 5.0M × 50.5k + SEA 3.7M × 10.4k ≈ 0.46 T, minus the extra home
   shed it costs under homes-first (24.7k GWh × VOLL 4.1M ≈ 0.10 T) ≈ **0.36 T upper bound**; capped by the
   lost-sales gap these chips would fill (SEA le 0.20, CN mat 0.14, JP le 0.07, SEA mat 0.06, IN 0.07, ...).
   **Design hint (inference, not tested):** the pulse should be sized to *shortfall + fab draw* (≈ 0.5-1% of load
   at CN), not to `pulse_weeks` × the weekly burn. At CN, 1.5 weeks of burn is ~270k GWh held back, which is my best
   guess for why task 14's plain pulse at CN cost −0.15 RSS. Task 16 (planned pulses at CN/JP/SEA) is aimed right at this.
2. **Chips that are made but never sold (ceiling ≤ 0.2 T, realistic part unknown).** The agent disposes of
   **10.3M chips per episode** (chip_mat_raw 5.8M, mostly at fab_us_mature_1 3.6M and fab_eu_mature_1 1.4M;
   chip_le_raw 1.4M at US fabs; packaged chip_le 1.5M / chip_mat 1.5M at OSATs kr/tw/my), the oracle ~0.3M, and it
   ends with 4.0M chips in stock. At pi that is ≤ 0.15 T (chip_le) + 0.08 T (chip_mat). It also over-starts US fabs
   (17.4M lots vs the oracle's 9.8M) and TW (17.1M vs 14.8M): output their OSAT routes can't take. Fixes: cap
   lots at fabs whose raw-chip outflow is blocked (sanctioned fab→OSAT edges), route raw chips before they overflow.
   The cost of the disposal itself is small (0.011 T); the value is in the chips.
3. **Shed (ceiling ≈ 0.13 T).** By grid (agent − oracle): TW 0.056, KR 0.034, IN 0.033, JP 0.020 T. TW/KR is the
   pulse's price (task 14); IN has no fabs (fuel routing). Worth ≤ +0.04 RSS even if perfect.
4. **Timing:** the chip gap is ~0 in weeks 1-26 (the pipeline start is the same for both) and grows to
   0.27 T per quarter afterwards. The agent also starts 2.1M chip_le + 3.5M chip_mat lots in the last 10 weeks that
   can't reach a sink in time (the oracle starts none): wafers wasted, no lost sales.
5. **Disruption events explain little.** All 20 episodes have sanctions and tariffs; no event type separates
   high-gap from low-gap episodes (|corr| ≤ 0.4 with n = 20: energy_shock +0.39, piracy +0.30). The gap is
   structural (chronic small fuel shortfalls at CN/JP/SEA) and as large in calm level-1 episodes (0.94 T) as in
   level 4 (1.13 T). Biggest single episodes: 41 (lvl 4, 1.84 T, also 0.74 T of shed: energy shocks at 6 grids,
   Malacca/Taiwan/Hormuz/Suez closures) and 7 (lvl 1, 1.72 T: CN dead, JP and KR fabs short, KR energy shock x9).

## 1. Cost components, overall and per harm level (USD per episode)

```
ALL: 20 episodes (USD per episode, mean)
component              naive        agent      perfect  agent-perfect share of gap
freight           1.6226e+10   1.7719e+10   1.2011e+10     5.7077e+09         0.6%
war_risk          1.2879e+08   1.5692e+08   1.2312e+08     3.3801e+07         0.0%
tariff            1.2881e+10   1.9387e+10   1.0608e+10     8.7783e+09         0.9%
holding           3.3975e+10   3.2168e+10   1.7414e+10     1.4754e+10         1.6%
queue_holding     5.4134e+09   2.8500e+09   5.9548e+08     2.2545e+09         0.2%
shortage          3.6170e+12   2.5972e+12   1.8332e+12     7.6398e+11        82.0%
disposal          8.7890e+09   1.0996e+10   2.9916e+08     1.0697e+10         1.1%
shed              5.6589e+12   4.1864e+12   4.0556e+12     1.3086e+11        14.0%
salvage_credit   -5.7899e+09  -5.8343e+09  -3.1459e+08    -5.5197e+09        -0.6%
TOTAL             9.3476e+12   6.8610e+12   5.9295e+12     9.3154e+11       100.0%

harm level 1: 5 episodes (USD per episode, mean)
component              naive        agent      perfect  agent-perfect share of gap
freight           1.8669e+10   2.0069e+10   1.2786e+10     7.2832e+09         0.8%
war_risk          1.6081e+08   1.9429e+08   9.2510e+07     1.0178e+08         0.0%
tariff            1.5559e+10   2.1127e+10   6.5107e+09     1.4617e+10         1.6%
holding           3.8065e+10   3.5826e+10   1.6994e+10     1.8832e+10         2.0%
queue_holding     1.1072e+10   4.9977e+09   2.2013e+08     4.7776e+09         0.5%
shortage          3.5259e+12   2.3736e+12   1.5902e+12     7.8343e+11        83.6%
disposal          1.0931e+10   1.3886e+10   1.9221e+08     1.3694e+10         1.5%
shed              3.8572e+12   2.6900e+12   2.5885e+12     1.0155e+11        10.8%
salvage_credit   -7.5150e+09  -7.4618e+09  -5.1699e+08    -6.9448e+09        -0.7%
TOTAL             7.4701e+12   5.1522e+12   4.2149e+12     9.3734e+11       100.0%
  level 1: gap 0.937 T/ep

harm level 2: 5 episodes (USD per episode, mean)
component              naive        agent      perfect  agent-perfect share of gap
freight           1.5859e+10   1.7447e+10   1.2002e+10     5.4449e+09         0.9%
war_risk          1.1244e+08   1.7092e+08   1.4103e+08     2.9891e+07         0.0%
tariff            1.4505e+10   2.1145e+10   1.5379e+10     5.7658e+09         0.9%
holding           3.2678e+10   3.1328e+10   1.7250e+10     1.4078e+10         2.3%
queue_holding     3.5440e+09   4.2760e+09   3.0588e+08     3.9701e+09         0.6%
shortage          3.3931e+12   2.3260e+12   1.7917e+12     5.3424e+11        86.3%
disposal          6.4837e+09   8.9746e+09   1.7311e+08     8.8015e+09         1.4%
shed              6.0501e+12   4.6581e+12   4.6064e+12     5.1661e+10         8.3%
salvage_credit   -5.3776e+09  -5.5128e+09  -3.3564e+08    -5.1772e+09        -0.8%
TOTAL             9.5110e+12   7.0619e+12   6.4431e+12     6.1881e+11       100.0%
  level 2: gap 0.619 T/ep

harm level 3: 5 episodes (USD per episode, mean)
component              naive        agent      perfect  agent-perfect share of gap
freight           1.5964e+10   1.7629e+10   1.2374e+10     5.2543e+09         0.5%
war_risk          1.1911e+08   1.5528e+08   1.2714e+08     2.8137e+07         0.0%
tariff            7.9255e+09   1.2681e+10   7.8211e+09     4.8599e+09         0.5%
holding           3.3381e+10   3.1606e+10   1.7766e+10     1.3841e+10         1.3%
queue_holding     1.8369e+09   1.0324e+09   7.4174e+08     2.9069e+08         0.0%
shortage          3.7522e+12   2.7593e+12   1.8817e+12     8.7761e+11        84.7%
disposal          9.4831e+09   1.1653e+10   3.7164e+08     1.1281e+10         1.1%
shed              5.4693e+12   3.7917e+12   3.6637e+12     1.2802e+11        12.4%
salvage_credit   -5.3047e+09  -5.4131e+09  -2.3112e+08    -5.1819e+09        -0.5%
TOTAL             9.2849e+12   6.6203e+12   5.5843e+12     1.0360e+12       100.0%
  level 3: gap 1.036 T/ep

harm level 4: 5 episodes (USD per episode, mean)
component              naive        agent      perfect  agent-perfect share of gap
freight           1.4413e+10   1.5731e+10   1.0883e+10     4.8482e+09         0.4%
war_risk          1.2278e+08   1.0718e+08   1.3179e+08    -2.4607e+07        -0.0%
tariff            1.3536e+10   2.2594e+10   1.2723e+10     9.8708e+09         0.9%
holding           3.1776e+10   2.9913e+10   1.7646e+10     1.2267e+10         1.1%
queue_holding     5.2007e+09   1.0939e+09   1.1142e+09    -2.0246e+07        -0.0%
shortage          3.7970e+12   2.9299e+12   2.0692e+12     8.6063e+11        75.9%
disposal          8.2584e+09   9.4690e+09   4.5969e+08     9.0093e+09         0.8%
shed              7.2590e+12   5.6059e+12   5.3637e+12     2.4220e+11        21.4%
salvage_credit   -4.9622e+09  -4.9495e+09  -1.7461e+08    -4.7749e+09        -0.4%
TOTAL             1.1124e+13   8.6097e+12   7.4757e+12     1.1340e+12       100.0%
  level 4: gap 1.134 T/ep

```

## 2. Chip shortage by product and sink, fab lots vs the oracle

```
## Lost sales by product (USD/episode, mean): agent vs oracle vs naive
product                  demand $ naive lost agent lost oracle lost agent-oracle
chip_le                     3.407      2.714      1.845       1.343        0.503
chip_mat                    1.137      0.903      0.752       0.490        0.261
(T USD per episode)

## Lost sales by sink x product, top 25 by agent-oracle (T USD/episode)
sink                         product                demand    agent   oracle      a-o agent fill oracle fill
sink_sea                     chip_le                 0.584    0.354    0.158    0.196      39.4%       73.0%
sink_cn                      chip_mat                0.338    0.260    0.124    0.136      23.0%       63.2%
sink_us                      chip_le                 1.217    0.717    0.623    0.094      41.1%       48.8%
sink_jp                      chip_le                 0.340    0.178    0.113    0.065      47.7%       66.7%
sink_sea                     chip_mat                0.136    0.096    0.039    0.057      29.6%       71.6%
sink_in                      chip_le                 0.194    0.073    0.021    0.052      62.2%       89.1%
sink_eu                      chip_le                 0.437    0.170    0.130    0.040      61.2%       70.2%
sink_kr                      chip_le                 0.245    0.144    0.109    0.035      41.1%       55.5%
sink_jp                      chip_mat                0.080    0.051    0.027    0.024      36.6%       66.1%
sink_row                     chip_le                 0.390    0.209    0.188    0.021      46.3%       51.7%
sink_kr                      chip_mat                0.058    0.034    0.015    0.019      41.1%       73.8%
sink_in                      chip_mat                0.046    0.022    0.006    0.015      52.3%       86.2%
sink_us                      chip_mat                0.285    0.136    0.124    0.012      52.1%       56.5%
sink_row                     chip_mat                0.091    0.071    0.067    0.004      22.5%       26.4%
sink_cn                      chip_le                 0.000    0.000    0.000    0.000     100.0%      100.0%
sink_eu                      chip_mat                0.104    0.083    0.088   -0.005      20.5%       15.3%

by sink region: SEA 0.253, CN 0.136, US 0.107, JP 0.088, IN 0.068, KR 0.054, EU 0.034, ROW 0.024

## Fab lots started per episode (mean): agent vs oracle
fab                        cls      grid       product              cap*T     agent    oracle    a/o  a %cap  o %cap  E agent E oracle
fab_cn_mature_1            mature   grid_cn    chip_mat_raw      45414824   6043842  22747383   0.27   13.3%   50.1%   5439.5  20472.6
fab_jp_memory_1            memory   grid_jp    chip_le_raw       14964976   1741342   6766063   0.26   11.6%   45.2%   2194.1   8525.2
fab_sea_mature_1           mature   grid_sea   chip_mat_raw      14452880    835007   4580470   0.18    5.8%   31.7%    751.5   4122.4
fab_kr_memory_1            memory   grid_kr    chip_le_raw       31719480  12857211  14108541   0.91   40.5%   44.5%  16200.1  17776.8
fab_row_leading_1          leading  grid_eu    chip_le_raw        1573624    425673    609337   0.70   27.1%   38.7%    851.3   1218.7
fab_eu_leading_1           leading  grid_eu    chip_le_raw        2557048    734326    756485   0.97   28.7%   29.6%   1468.7   1513.0
fab_us_leading_2           leading  grid_us    chip_le_raw        1835843   1075143    724816   1.48   58.6%   39.5%   2150.4   1449.7
fab_us_leading_1           leading  grid_us    chip_le_raw        1835843   1367476    931060   1.47   74.5%   50.7%   2735.1   1862.3
fab_tw_leading_1           leading  grid_tw    chip_le_raw       14379144   6906304   6400926   1.08   48.0%   44.5%  13862.1  12945.2
fab_us_leading_3           leading  grid_us    chip_le_raw        1835843   1279751    543900   2.35   69.7%   29.6%   2559.6   1087.9
fab_tw_mature_1            mature   grid_tw    chip_mat_raw      12245740   5026969   4265248   1.18   41.1%   34.8%   4543.1   3842.7
fab_kr_leading_1           leading  grid_kr    chip_le_raw        3712072   1645640    737444   2.23   44.3%   19.9%   3291.3   1474.9
fab_eu_mature_1            mature   grid_eu    chip_mat_raw      18739656   5747924   4785540   1.20   30.7%   25.5%   5173.1   4307.0
fab_tw_mature_2            mature   grid_tw    chip_mat_raw      12245740   5196783   4117417   1.26   42.4%   33.6%   4696.0   3711.9
fab_us_mature_2            mature   grid_us    chip_mat_raw       9265724   6916544   5031099   1.37   74.6%   54.3%   6225.3   4528.4
fab_us_mature_1            mature   grid_us    chip_mat_raw       9265724   6796863   2618105   2.60   73.4%   28.3%   6117.4   2356.5
lots by grid (agent / oracle): grid_tw 17130057/14783590, grid_us 17435777/9848980, grid_kr 14502851/14845986, grid_jp 1741342/6766063, grid_eu 6907922/6151361, grid_cn 6043842/22747383, grid_sea 835007/4580470
lots by class (agent / oracle): leading 13434312/10703967, mature 36563932/48145262, memory 14598553/20874604
```

Chip balance and timing (`flow17.py`):

```
## chip balance per episode (mean, million units)
chip_le   agent   lots   28.03  of which in the last 10 weeks  2.12  served   30.95  lost   36.57
chip_le   oracle  lots   31.58  of which in the last 10 weeks  0.00  served   40.91  lost   26.60
   agent disposal of chip_le* (units/episode): osat_kr/chip_le 0.68M, fab_us_leading_3/chip_le_raw 0.64M, osat_tw/chip_le 0.39M, osat_my/chip_le 0.32M, fab_us_leading_1/chip_le_raw 0.29M, fab_us_leading_2/chip_le_raw 0.25M
chip_mat  agent   lots   36.56  of which in the last 10 weeks  3.52  served   37.23  lost   72.83
chip_mat  oracle  lots   48.15  of which in the last 10 weeks  0.01  served   62.64  lost   47.42
   agent disposal of chip_mat* (units/episode): fab_us_mature_1/chip_mat_raw 3.56M, fab_eu_mature_1/chip_mat_raw 1.40M, osat_tw/chip_mat 1.06M, fab_us_mature_2/chip_mat_raw 0.85M, osat_cn/chip_mat 0.22M, osat_my/chip_mat 0.14M

## lost-sales gap (agent - oracle, T USD/episode) by quarter of the episode
chip_le   wk 1-26: 0.007 (agent 0.317, oracle 0.310) | wk 27-52: 0.127 (agent 0.479, oracle 0.352) | wk 53-78: 0.177 (agent 0.521, oracle 0.344) | wk 79-104: 0.191 (agent 0.529, oracle 0.337)
chip_mat  wk 1-26: 0.020 (agent 0.130, oracle 0.111) | wk 27-52: 0.072 (agent 0.200, oracle 0.128) | wk 53-78: 0.088 (agent 0.212, oracle 0.124) | wk 79-104: 0.082 (agent 0.210, oracle 0.127)

## fab lots gap (oracle - agent, M lots) per grid by quarter
grid_cn     2.97   6.23   5.90   1.60
grid_eu    -0.49   0.46   0.31  -1.03
grid_jp     0.94   1.86   1.61   0.62
grid_kr    -0.62   0.94   1.12  -1.10
grid_sea    0.23   1.52   1.37   0.63
grid_tw    -1.45   0.27   0.51  -1.67
grid_us    -1.96  -1.49  -1.39  -2.75

## per episode: lots deficit (oracle - agent, M) at grids CN / JP / SEA / KR, and chip lost-sales gap T
ep   0 lvl 2  CN   0.04 JP   6.04 SEA   1.56 KR  -0.04 US  -8.64 TW   0.40  chip gap 0.638
ep   1 lvl 2  CN  28.67 JP   2.15 SEA   3.77 KR  -2.40 US  -1.42 TW  -9.85  chip gap 0.579
ep   2 lvl 1  CN   6.20 JP  -0.39 SEA   3.76 KR  -7.65 US -13.21 TW  -5.82  chip gap 0.229
ep   3 lvl 2  CN  -0.60 JP   0.12 SEA   6.89 KR   0.15 US  -7.33 TW  -0.46  chip gap 0.156
ep   4 lvl 2  CN  27.32 JP  -5.48 SEA   9.74 KR  -4.42 US  -3.54 TW   0.51  chip gap 0.433
ep   5 lvl 1  CN  24.22 JP  11.26 SEA   2.41 KR  -8.25 US  -2.41 TW   9.56  chip gap 0.924
ep   6 lvl 2  CN  22.84 JP   6.29 SEA   1.03 KR   0.09 US  -3.21 TW  -1.70  chip gap 0.865
ep   7 lvl 1  CN  27.89 JP  12.20 SEA   2.82 KR   5.34 US  -2.61 TW  10.01  chip gap 1.516
ep  10 lvl 1  CN   0.72 JP   4.63 SEA   2.30 KR   1.18 US  -8.90 TW  -7.38  chip gap 0.571
ep  14 lvl 1  CN   0.57 JP   8.61 SEA  -0.88 KR   2.91 US -18.20 TW -10.67  chip gap 0.677
ep  26 lvl 4  CN  14.62 JP   4.21 SEA   2.22 KR  -0.03 US  -7.78 TW  -3.64  chip gap 0.720
ep  41 lvl 4  CN  19.00 JP   7.06 SEA   6.19 KR   1.32 US  -7.57 TW   4.83  chip gap 1.070
ep  44 lvl 4  CN  18.55 JP   3.16 SEA  -0.17 KR  -1.07 US  -4.95 TW  -6.26  chip gap 0.543
ep  53 lvl 3  CN  25.74 JP   3.88 SEA   8.43 KR  -0.38 US  -8.15 TW   0.47  chip gap 0.902
ep  57 lvl 3  CN  23.04 JP   6.12 SEA   6.48 KR   3.88 US  -9.48 TW  -5.70  chip gap 1.023
ep  61 lvl 3  CN  15.96 JP   3.21 SEA  -0.07 KR   4.73 US -13.04 TW  -9.47  chip gap 0.706
ep  69 lvl 3  CN   8.56 JP   7.14 SEA   4.97 KR  -1.76 US -10.00 TW  -0.70  chip gap 0.646
ep  76 lvl 3  CN  25.52 JP   5.81 SEA   6.94 KR   3.20 US  -4.23 TW  -1.00  chip gap 1.111
ep  80 lvl 4  CN  27.62 JP   5.76 SEA   3.01 KR  10.99 US  -9.63 TW  -4.18  chip gap 1.232
ep 102 lvl 4  CN  17.58 JP   8.71 SEA   3.50 KR  -0.93 US  -7.44 TW  -5.87  chip gap 0.738
```

Why the fabs are off, OSAT packaging, disposal (`fabs17.py`), and the extra fuel it would take:

```
## Per fab-grid, weeks (summed over 20 episodes): agent fab state, and where the oracle's fab energy goes
grid      wk shed>0  agent: fab<5%cap & shed>0  fab<5% & wafers<1wk fab<5% other  oracle E in its shed weeks oracle E in agent-shed wks
grid_cn       80.3%                      80.3%                 0.0%         0.0%                       81.6%                      82.4%
grid_jp       87.2%                      87.2%                 0.0%         0.1%                       72.0%                      85.2%
grid_sea      89.7%                      89.7%                 0.0%         0.0%                       87.2%                      91.3%
grid_kr       42.5%                      42.5%                 3.3%         0.2%                       64.2%                      35.0%
grid_tw       39.1%                      39.1%                 0.1%         0.5%                       47.3%                      34.4%
grid_eu       57.1%                      57.1%                 0.0%         0.0%                       31.2%                      31.3%
grid_us        6.7%                       6.7%                 0.0%         0.0%                        1.5%                       1.5%
(share of all episode-weeks; 'oracle E in its shed weeks' = share of the oracle's fab energy at that grid delivered in weeks where the oracle itself sheds homes there, i.e. only possible through the base_first relaxation unless fuel is moved between weeks)

## CN: per episode, weeks with shed > 0 (agent / oracle), mean weekly shed as % of base load, agent CN lots
ep   0: shed weeks   7/  0, median shed in shed weeks   0.0% of base load, agent lots  14.6M, oracle  14.6M
ep   1: shed weeks 101/101, median shed in shed weeks   0.9% of base load, agent lots   1.3M, oracle  29.9M
ep   2: shed weeks  35/ 41, median shed in shed weeks   0.4% of base load, agent lots  20.7M, oracle  26.9M
ep   3: shed weeks 100/100, median shed in shed weeks   1.1% of base load, agent lots   1.0M, oracle   0.4M
ep   4: shed weeks 100/ 96, median shed in shed weeks   0.0% of base load, agent lots   1.5M, oracle  28.8M
ep   5: shed weeks 101/ 99, median shed in shed weeks   0.2% of base load, agent lots   1.3M, oracle  25.5M
ep   6: shed weeks 101/ 97, median shed in shed weeks   0.2% of base load, agent lots   1.1M, oracle  24.0M
ep   7: shed weeks 101/ 99, median shed in shed weeks   0.5% of base load, agent lots   1.2M, oracle  29.1M
ep  10: shed weeks  57/ 51, median shed in shed weeks   0.2% of base load, agent lots  19.9M, oracle  20.6M
ep  14: shed weeks  14/  0, median shed in shed weeks   0.0% of base load, agent lots  27.4M, oracle  28.0M
ep  26: shed weeks 101/100, median shed in shed weeks   0.4% of base load, agent lots   1.3M, oracle  15.9M
ep  41: shed weeks 101/100, median shed in shed weeks   3.5% of base load, agent lots   1.3M, oracle  20.3M
ep  44: shed weeks 101/101, median shed in shed weeks   0.4% of base load, agent lots   0.9M, oracle  19.4M
ep  53: shed weeks  96/ 95, median shed in shed weeks   0.8% of base load, agent lots   2.3M, oracle  28.1M
ep  57: shed weeks 101/ 99, median shed in shed weeks   0.2% of base load, agent lots   1.1M, oracle  24.1M
ep  61: shed weeks 101/ 93, median shed in shed weeks   0.1% of base load, agent lots   1.2M, oracle  17.2M
ep  69: shed weeks  48/ 40, median shed in shed weeks   0.2% of base load, agent lots  20.1M, oracle  28.7M
ep  76: shed weeks 101/101, median shed in shed weeks   0.6% of base load, agent lots   1.0M, oracle  26.6M
ep  80: shed weeks 102/101, median shed in shed weeks   1.4% of base load, agent lots   0.8M, oracle  28.4M
ep 102: shed weeks 102/101, median shed in shed weeks   0.4% of base load, agent lots   0.8M, oracle  18.4M

## OSAT packaging per episode (M units, mean): agent vs oracle
  (3, 7)     agent   16.79  oracle   30.50
  (0, 7)     agent    7.85  oracle   13.77
  (0, 6)     agent   10.30  oracle   13.53
  (5, 6)     agent   11.07  oracle   12.22
  (4, 6)     agent    7.13  oracle    7.56
  (4, 7)     agent    5.95  oracle    5.69
  (6, 7)     agent    2.65  oracle    3.97
  (2, 7)     agent    3.28  oracle    3.28
  (2, 6)     agent    1.29  oracle    3.21
  (1, 6)     agent    1.15  oracle    1.57
  (6, 6)     agent    0.23  oracle    0.24

## chip stock left at the end (agent, M units, mean) and chip disposal agent vs oracle
  chip_le        end stock   0.52  disposed agent   1.53  oracle   0.00
  chip_le_raw    end stock   0.32  disposed agent   1.44  oracle   0.12
  chip_mat       end stock   2.30  disposed agent   1.47  oracle   0.00
  chip_mat_raw   end stock   0.88  disposed agent   5.82  oracle   0.17

grid      base_load  fab draw at cap  agent shed-week median shortfall GWh  p75   oracle fabE/wk  extra fuel to cover ALL agent shed (GWh/ep)  oracle extra fab E vs agent (GWh/ep)
grid_cn      179607             393                                706.0 1863.8          196.9                                       166882                                15033
grid_jp       17819             181                               1089.8 3958.5           82.0                                       196750                                 6331
grid_sea      24875             125                                624.0 8110.9           39.6                                       261534                                 3371
grid_kr       10544             456                               2294.3 2507.9          185.1                                        94192                                 -240
grid_tw        4954             488                               1468.5 1688.5          197.1                                        46441                                -2601
grid_eu       51758             242                               1409.5 1566.8           67.7                                       112143                                 -454
```

## 3. Shed by grid

```
## Shed by grid (USD/episode, mean)
grid         priority        naive     agent    oracle       a-o  (T USD)
grid_tw      base_first     0.4591    0.1916    0.1357    0.0559
grid_kr      base_first     0.7781    0.3886    0.3551    0.0335
grid_in      base_first     0.1180    0.1399    0.1070    0.0329
grid_jp      base_first     1.0932    0.8116    0.7920    0.0197
grid_eu      base_first     0.5152    0.4626    0.4553    0.0073
grid_us      base_first     0.4246    0.4247    0.4200    0.0047
grid_sea     base_first     1.0841    1.0789    1.0799   -0.0010
grid_cn      base_first     1.1866    0.6884    0.7105   -0.0221
```

## 4. Per episode: gap and new disruption events (counts of events whose onset falls inside the episode)

```
## Per episode: gap and NEW disruption events (onset in week 0..T; events running since before the episode are left out)
  ep lvl   gap T naive-o T    RSS chipgap T shedgap T  energy_sho material_o militarise     piracy port_strik regional_c   sanction     tariff weather_cl
   0   2   0.786     2.895  0.728     0.638     0.098           9          0          1          3          0          0         10          7          2
   1   2   0.544     4.222  0.871     0.579    -0.053           3          0          0          0          3          2          9          6          5
   2   1   0.534     3.250  0.836     0.229     0.239          10          1          0          1          2          0         11         12          3
   3   2   0.446     2.243  0.801     0.156     0.254           5          0          3          0          2          0          5          3          2
   4   2   0.467     3.646  0.872     0.433    -0.002           4          6          1          0          5          0         20         17          3
   5   1   0.844     3.174  0.734     0.924    -0.124           7          1          0          1          2          0          7          4          3
   6   2   0.851     2.333  0.635     0.865    -0.038           1          2          0          1          1          0          4          6          1
   7   1   1.721     3.774  0.544     1.516     0.172          12          1          0          0          1          1          5          9          0
  10   1   0.717     2.528  0.716     0.571     0.107          10          0          4          0          0          2         10         12          2
  14   1   0.871     3.550  0.755     0.677     0.115           4          0          1          0          4          0          7          6          3
  26   4   0.802     3.453  0.768     0.720     0.065           4          1          2          0          1          1         17          8          1
  41   4   1.842     3.163  0.418     1.070     0.743          16          0          5          2          2          1         17          9          1
  44   4   0.632     3.957  0.840     0.543     0.064           9          3          1          0          3          0          9         13          3
  53   3   1.049     4.588  0.771     0.902     0.117           1          2          0          0          5          0         14         13          4
  57   3   1.210     3.153  0.616     1.023     0.151           2          1          0          0          2          0          2          4          2
  61   3   0.936     3.145  0.702     0.706     0.195           4          0          1          0          0          0          8         11          2
  69   3   0.878     3.290  0.733     0.646     0.210           0          0          2          1          1          0         10          7          4
  76   3   1.108     4.327  0.744     1.111    -0.033           7          1          1          0          2          0          4          2          2
  80   4   1.249     4.364  0.714     1.232    -0.001           5          0          3          5          1          0         20         12          3
 102   4   1.146     3.305  0.653     0.738     0.340           4          2          4          3          6          0         42         37          3

Gap with vs without each event type (mean T USD/episode; corr = Pearson of count vs gap):
  energy_shock           episodes 19/20: with 0.934, without 0.878, corr +0.39
  material_outage        episodes 11/20: with 0.942, without 0.919, corr -0.24
  militarised_closure    episodes 13/20: with 0.914, without 0.965, corr +0.26
  piracy                 episodes  8/20: with 1.016, without 0.875, corr +0.30
  port_strike            episodes 17/20: with 0.952, without 0.813, corr -0.09
  regional_conflict      episodes  5/20: with 1.125, without 0.867, corr +0.08
  sanction               episodes 20/20: with 0.932, without nan, corr +0.12
  tariff                 episodes 20/20: with 0.932, without nan, corr +0.07
  weather_closure        episodes 19/20: with 0.890, without 1.721, corr -0.48

```

## Notes / choices

- `outputs/oracle_fabs.py` named in the task does not exist on `cloud`; oracle lots per fab are read from the LP
  solution's `("p", t, f)` columns in `gap17.py` instead (also `E`, `ysh`, `U`, `D`, `xi`, `O`).
- Lots = raw chips (1 lot → 1 raw chip, minus scrap), so lot gaps are valued at the product's pi (leading/memory →
  chip_le ≈ 50.5k USD, mature → chip_mat ≈ 10.4k USD). These are gross upper bounds: a chip only counts if a sink that
  loses sales gets it in time.
- Events: omega `ev_*` rows; ones running since before week 0 are left out of the per-episode counts (sanctions often
  start thousands of weeks earlier).
- Runtime on this cloud box: the whole 20-episode run (agent + naive + oracle LP) took ~6 min on 4 cores once
  references were cached.
