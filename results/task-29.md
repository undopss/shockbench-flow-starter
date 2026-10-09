Status: done — negative. The chip LP's marginal value makes the pulse planner worse on Full devpick (pv1 -0.010 [-0.016, -0.004]); pp_value 20 sits on a flat optimum (5..80 within 0.0015). Not a final candidate.

Plan: measure pplan's fab-energy value V (pp_value x estimate) vs the chip LP's marginal value per grid/week on Full,
then feed the planner that value (`agents/mpc_pval`, options `pv_dual`, `pv_scale`, `pv_release`, off by default) and run the funnel.

Built so far: `agents/mpc_pval` = copy of `agents/mpc_imit_room` (same params.json) +
- `chips.py`: after the chip LP solves, `fab_val[fab][t]` = dual of each fab's start upper bound (USD per extra wafer start).
- `pplan.py`: with `fab_val`, V[t] = pv_scale * sum_f draw_f * fab_val_f * R/e / sum_f draw_f / VOLL (same fab draw estimate
  as before, only the USD per start changes from pp_value(20) * pi to the LP's dual). `pv_release`: if that V never beats
  VOLL in the window, release the grid's fuel (no pulse) instead of the fixed TW/KR pulse rule.

## 1. Measurement: planner's V vs the chip LP's marginal value (Full dev episodes 0, 2, 5, 7, all 104 weeks)

`outputs/task-29/probe.py` plays `agents/mpc_pval` with `pv_dual: "measure"` (plays exactly like mpc_imit_room, logs both
values for every planned grid and week); `outputs/task-29/an.py` summarises (`outputs/task-29/measure.txt`).
V in VOLL units per unit of fab energy (> 1 means fab energy is worth more than homes, so a pulse can pay).

```
week-0 values in VOLL units (fab-draw weighted); 'max' columns: the planner window's max (what decides a pulse)
grid           n  Vmax>1  Vdmax>1  Vd0>0   med V0 med Vd0|>0  p90 Vd0  max Vd0 med Vd/V|>0
grid_cn      401    1.00     0.39   0.45     56.0       2.78     2.80     2.85       0.050
grid_eu      397    1.00     0.34   0.43     77.9       1.53     2.20     3.94       0.020
grid_jp      406    1.00     0.46   0.60    194.4       9.68     9.70     9.75       0.050
grid_kr      416    1.00     0.24   0.43    183.1       7.26     9.13     9.20       0.040
grid_sea     416    1.00     0.37   0.68     56.0       1.17     2.78     2.87       0.021
grid_tw      415    1.00     0.42   0.53     93.6       4.23     4.66     4.72       0.045
grid_us      380    1.00     0.42   0.43     82.0       2.50     3.28     4.12       0.031

share of grid-weeks whose window max is > 1 (a pulse can pay), by quarter
Q1: dual 0.24   pp_value x pi 1.00
Q2: dual 0.41   pp_value x pi 1.00
Q3: dual 0.56   pp_value x pi 1.00
Q4: dual 0.29   pp_value x pi 1.00
```

- **pp_value x pi is ~20-50x the chip LP's marginal value** whenever the latter is positive (median ratio 0.02-0.05;
  when positive, the dual is about the sinks' pi, so the extra 20 is just the hand factor). The old V is > 1 in 100%
  of grid-weeks, so the planner always thinks fab energy beats homes.
- The dual is **zero in 32-57% of grid-weeks** (week 0) and its window max beats VOLL in only 24-46% of grid-weeks
  (Q1 0.24, Q3 0.56): in those weeks the LP says one more start is worth nothing (the fab is wafer-limited, its
  chips can't get out, or the starts can wait). Positive duals: JP ~9.7, KR ~7-9, TW ~4.5, CN ~2.8, US ~2.5-4,
  EU ~1.5-4, SEA ~1.2-2.9 VOLL units: honest pulses still pay at JP/KR/TW, barely at SEA/EU.
- At episode start (weeks 1-4) the chip LP plans **zero starts** and every start has a negative reduced cost
  (-1k to -24k USD: the wafer-buffer penalty, starting a wafer now drops it below the 3-week buffer).

## 2. Full devpick:2,2,1,1 (root 0), baseline `agents/mpc_imit_room` (`outputs/task-29/v29a.json`)

All mpc_pval variants carry mpc_imit_room's params.json + the listed option. pv1/pv3: `pv_dual` true, `pv_scale` 1/3;
pv1_rel: + `pv_release`; pp5/pp1: the old valuation with `pp_value` 5/1 (control: "just a lower value").

```
round v29a_full_0_1009-0833: task full, entropy 0, episodes devpick:2,2,1,1, baseline imit_room
references ready in 1196 s (6 episodes)
  played imit_room in 55 s: RSS 0.8535
  played pv1 in 51 s: RSS 0.8434
  played pv3 in 48 s: RSS 0.8432
  played pv1_rel in 49 s: RSS 0.8315
  played pp5 in 50 s: RSS 0.8523
  played pp1 in 51 s: RSS 0.8475

full, entropy 0, 6 episodes; diff = variant - imit_room, 90% paired interval
variant                      RSS     L1     L2     L3     L4     diff  interval               better%  fallb
imit_room                 0.8535  0.845  0.875  0.842  0.846  +0.0000  [+0.0000, +0.0000]     nan%      0
pv1                       0.8434  0.839  0.870  0.824  0.793  -0.0102  [-0.0156, -0.0042]     0.0%      0  <-- worse
pv3                       0.8432  0.840  0.866  0.826  0.800  -0.0103  [-0.0156, -0.0043]     0.0%      0  <-- worse
pv1_rel                   0.8315  0.830  0.862  0.803  0.774  -0.0220  [-0.0384, -0.0075]     0.0%      0  <-- worse
pp5                       0.8523  0.844  0.876  0.839  0.840  -0.0012  [-0.0023, -0.0000]     0.0%      0  <-- worse
pp1                       0.8475  0.842  0.875  0.820  0.839  -0.0060  [-0.0079, -0.0042]     0.0%      0  <-- worse

results: outputs/variants/v29a_full_0_1009-0833/results.json
```

## 3. The other direction and the dual's shape (`outputs/task-29/v29b.json`, same 6 episodes, same baseline numbers)

pp40/pp80: the old valuation with a higher `pp_value`. pv20: the dual x 20 (same level as the old V, the dual's
grid/week pattern): this separates "the level is wrong" from "the dual's pattern is wrong".

```
round v29b_full_0_1009-0858: task full, entropy 0, episodes devpick:2,2,1,1, baseline imit_room
references ready in 2 s (6 episodes)
  baseline imit_room: reused full_0_devpick-2-2-1-1_f8d60554249f41c6.json
  played imit_room in 0 s: RSS 0.8535
  played pp40 in 62 s: RSS 0.8520
  played pp80 in 60 s: RSS 0.8523
  played pv20 in 47 s: RSS 0.8462

full, entropy 0, 6 episodes; diff = variant - imit_room, 90% paired interval
variant                      RSS     L1     L2     L3     L4     diff  interval               better%  fallb
imit_room                 0.8535  0.845  0.875  0.842  0.846  +0.0000  [+0.0000, +0.0000]     nan%      0
pp40                      0.8520  0.842  0.875  0.842  0.846  -0.0015  [-0.0032, +0.0001]    18.9%      0
pp80                      0.8523  0.842  0.877  0.842  0.842  -0.0012  [-0.0030, +0.0008]    19.1%      0
pv20                      0.8462  0.836  0.877  0.831  0.814  -0.0073  [-0.0134, -0.0006]     0.0%      0  <-- worse

results: outputs/variants/v29b_full_0_1009-0858/results.json
```

## 4. Shed by grid and fab lots, before/after (Full dev episodes 0, 2, 5, 7; `outputs/task-29/shedlots.py`)

Shed in T USD (qty x VOLL) and wafer starts in M lots per episode; base = mpc_pval with defaults (= mpc_imit_room),
pv1 = `pv_dual` true. (These are not the devpick episodes: the runner does not store its episode ids.)

```
Full dev episodes 0, 2, 5, 7 (per-episode means). base = mpc_imit_room params, pv1 = + pv_dual true
J (reward sum, env scale) base ['4.837e+12', '4.778e+12', '4.428e+12', '4.002e+12']  pv1 ['4.815e+12', '4.777e+12', '4.468e+12', '4.192e+12']

grid          shed base T  shed pv1 T   diff T
grid_tw            0.2810      0.2854  +0.0044
grid_kr            0.2919      0.2997  +0.0077
grid_jp            0.4780      0.4688  -0.0092
grid_cn            0.2212      0.1818  -0.0394
grid_us            0.3301      0.3301  +0.0000
grid_eu            0.5059      0.4976  -0.0082
grid_sea           0.2198      0.2182  -0.0017
grid_in            0.0219      0.0222  +0.0002
total              2.3499      2.3037  -0.0462

fab                    lots base M lots pv1 M   diff M
fab_tw_leading_1             6.497      6.569   +0.072
fab_tw_mature_1              4.598      4.461   -0.138
fab_us_leading_1             1.457      1.456   -0.001
fab_kr_leading_1             2.199      2.001   -0.198
fab_kr_memory_1             17.831     16.916   -0.915
fab_us_leading_2             1.015      1.015   -0.000
fab_jp_memory_1              4.312      2.521   -1.791
fab_us_leading_3             1.454      1.453   -0.001
fab_eu_leading_1             1.103      0.911   -0.192
fab_row_leading_1            0.654      0.575   -0.080
fab_cn_mature_1             23.038     15.090   -7.949
fab_us_mature_1              7.128      7.121   -0.007
fab_eu_mature_1              8.596      7.212   -1.383
fab_sea_mature_1             2.028      1.616   -0.412
fab_tw_mature_2              4.932      5.087   +0.155
fab_us_mature_2              7.389      7.381   -0.008
total                       94.232     81.384  -12.848
```

## Verdict

**Negative: the honest value as the chip LP measures it is worse than pp_value x pi. Don't use it.** Not run on
`full 0 dev` / a fresh seed / Small (decision, written down): no variant cleared the first Full stage (every interval
<= 0), and pp_value 5..80 is flat, so there is nothing to confirm.

Why it fails (from the tables):
- The dual is myopic. With `fab_cap_mode: observed` the chip LP caps a power-starved fab at ~1.25x its recent starts,
  so it can only value the next few starts, and those can often wait (dual 0 in 32-57% of grid-weeks). A pulse
  delivers a big block of energy that the LP never sees as feasible. So the LP undervalues it: pv1 saves 0.046 T/ep
  of home shed (CN -0.039, JP -0.009, EU -0.008) but starts **12.8 M fewer lots** (CN mature -7.9 M, JP memory -1.8 M,
  EU mature -1.4 M, KR memory -0.9 M), which costs more than the shed it saves.
- Even at the old level (pv20), the dual's week-by-week pattern loses 0.007: pulsing only when the LP wants starts
  this week is worse than pulsing whenever the fab has wafers.
- "x20 is too high" isn't supported either: pp_value 5 -0.0012, 1 -0.0060, 40 -0.0015, 80 -0.0012. The planner's
  decisions hardly change between 5 and 80 (fab energy beats homes by a wide margin at the chips' pi already:
  median V/20 = 2.8-9.7 VOLL units). So the 0.19 T of pulse shed (task 20 item 2) is **not** a valuation problem:
  at the true chip value (~pi) the pulses still pay. Reducing that shed needs better timing/foresight (when the grid
  will be full anyway), not a different price.
- Surprise: at episode start the chip LP plans **zero starts** for weeks 1-4 and gives every start a negative reduced
  cost (-1k..-24k USD). That's the wafer-buffer penalty (starting a wafer drops the fab below its 3-week buffer).
  The buffer's soft cost makes the LP's duals unusable as a value of energy. A buffer-free second solve for the duals
  would fix that, but the pv20 result says the pattern, not just the level, is the problem, so I didn't build it (time box).

Code: `agents/mpc_pval` (from `agents/mpc_imit_room`, same params.json). Options are off by default, and with the defaults it plays
exactly like mpc_imit_room (`pv_dual` false: the duals are computed but not used). The dual extraction is inside try/except.
