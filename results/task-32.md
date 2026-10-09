Status: done (dead end: every steering variant is worse on Full devpick, intervals below 0)

# Task 32: steer power to the most valuable fab inside a grid (`agents/mpc_steer`)

## 1. Measurement (baseline mpc_imit_room, Full devpick:2,2,1,1, `outputs/task-32/probe32.py`)
RSS 0.8535 (L1-4 0.845/0.875/0.842/0.846), 0 fallback weeks. Per multi-fab grid, mean per episode (104 weeks).
A week is "partial" when the fabs got 2-98% of their nameplate draw. "best share" = top-value fab's share of the
fabs' power if the split were greedy by pi/e (value per GWh); gain = that re-split valued at pi (gross: assumes sellable).

| grid | full wk | partial wk | zero wk | fab GWh in partial wks | top share got | top share best | gross gain T/ep |
|---|---|---|---|---|---|---|---|
| TW (leading 25M/GWh vs 2× mature 11M) | 11.0 | 57.3 | 35.7 | 18.3k | 0.60 | 0.79 | 0.041 |
| KR (memory 40M vs leading 25M, same chip_le_raw) | 25.5 | 46.7 | 31.8 | 14.5k | 0.80 | 0.96 | 0.030 |
| US (3 leading vs 2 mature) | 16.2 | 69.8 | 18.0 | 14.0k | 0.13 | 0.20 | 0.036 (not sellable: US leading output already disposed 1.2M/ep) |
| EU (2 leading vs mature) | 20.2 | 24.5 | 59.3 | 5.3k | 0.19 | 0.25 | 0.005 |

Low-value fabs hold 1.2-1.7 weeks of nameplate wafers in partial weeks (the 3-week buffer), so the split follows
nameplate, as task 28 said. Fab output disposed at the fab (per ep): 0 at TW and KR; US leading 1.19M, US mature 3.9M,
EU 1.2M, JP 0.19M. Sellable gross ceiling ≈ TW+KR ≈ 0.07 T/ep ≈ 0.02 RSS: **below the +0.05 bar even if fully captured.**

## 2. What I built (`agents/mpc_steer`, copy of mpc_imit_room, all new options off by default)
`chips.py` option `steer` (agent PARAMS `steer`, `steer_weeks` 4, `steer_margin` 1.2, `steer_stat` "max"|"mean",
`steer_buf` 1.0, `steer_grids` []). Per grid with 2+ powered fabs, fabs are ranked by chip value per unit of energy
(pi of the packaged chip / e: KR memory 40M > KR leading 25M; leading 25M > mature 11M at TW/US/EU; equal-value fabs
are never steered against each other). The leftover fab power E is estimated from the energy the grid's fabs used in the
last `steer_weeks` weeks (max or mean, read from work in process: e·starts/R). A lower-ranked fab gets an allowance
R·max(0, margin·E − nameplate draw of the better fabs)/e lots a week: the chip LP plans its starts at most at that, and
its wafer buffer becomes `steer_buf` weeks of the allowance instead of 3 weeks of nameplate. Unknown grid ids in
`steer_grids` are skipped. With steer off the agent plays exactly like mpc_imit_room (steer_off: diff 0.0000 on all 6).

## 3. Tests: Full devpick:2,2,1,1 (root 0), baseline `agents/mpc_imit_room` (its own params.json)
Variant files: `outputs/task-32/variants32{,b,c}.json`; results in `outputs/variants/variants32*_full_0_1009-*/`.

```
full, entropy 0, 6 episodes; diff = variant - base, 90% paired interval
variant                      RSS     L1     L2     L3     L4     diff  interval               better%  fallb
base                      0.8535  0.845  0.875  0.842  0.846  +0.0000  [+0.0000, +0.0000]     nan%      0
steer_off                 0.8535  0.845  0.875  0.842  0.846  +0.0000  [+0.0000, +0.0000]     0.0%      0
steer_max                 0.8482  0.848  0.870  0.819  0.829  -0.0053  [-0.0095, -0.0009]     0.0%      0  <-- worse
steer_max_m1              0.8262  0.826  0.842  0.805  0.815  -0.0273  [-0.0324, -0.0216]     0.0%      0  <-- worse
steer_mean                0.8241  0.823  0.842  0.804  0.798  -0.0294  [-0.0340, -0.0242]     0.0%      0  <-- worse
steer_mean_b2             0.8320  0.825  0.857  0.816  0.805  -0.0215  [-0.0254, -0.0179]     0.0%      0  <-- worse
steer_last                0.8392  0.842  0.856  0.811  0.819  -0.0143  [-0.0223, -0.0053]     0.0%      0  <-- worse
results: outputs/variants/variants32_full_0_1009-0835/results.json
```

```
full, entropy 0, 6 episodes; diff = variant - base, 90% paired interval
variant                      RSS     L1     L2     L3     L4     diff  interval               better%  fallb
base                      0.8535  0.845  0.875  0.842  0.846  +0.0000  [+0.0000, +0.0000]     nan%      0
steer_max_twkr            0.8480  0.844  0.872  0.824  0.832  -0.0055  [-0.0062, -0.0048]     0.0%      0  <-- worse
steer_max_kr              0.8474  0.843  0.870  0.825  0.834  -0.0061  [-0.0080, -0.0044]     0.0%      0  <-- worse
steer_max_tw              0.8497  0.839  0.875  0.839  0.843  -0.0038  [-0.0053, -0.0021]     0.0%      0  <-- worse
steer_mean_twkr           0.8405  0.837  0.867  0.814  0.820  -0.0130  [-0.0183, -0.0083]     0.0%      0  <-- worse
steer_max_us              0.8512  0.844  0.871  0.838  0.842  -0.0023  [-0.0042, -0.0001]     0.0%      0  <-- worse
results: outputs/variants/variants32b_full_0_1009-0842/results.json
```

```
full, entropy 0, 6 episodes; diff = variant - base, 90% paired interval
variant                      RSS     L1     L2     L3     L4     diff  interval               better%  fallb
base                      0.8535  0.845  0.875  0.842  0.846  +0.0000  [+0.0000, +0.0000]     nan%      0
tw_mean                   0.8469  0.838  0.871  0.834  0.834  -0.0066  [-0.0089, -0.0045]     0.0%      0  <-- worse
tw_mean_m15               0.8492  0.836  0.878  0.838  0.840  -0.0043  [-0.0076, -0.0014]     0.0%      0  <-- worse
tw_max8                   0.8509  0.841  0.873  0.841  0.844  -0.0026  [-0.0036, -0.0017]     0.0%      0  <-- worse
tw_max_b2                 0.8497  0.838  0.874  0.841  0.843  -0.0038  [-0.0051, -0.0024]     0.0%      0  <-- worse
kr_max8                   0.8498  0.845  0.875  0.826  0.833  -0.0037  [-0.0047, -0.0026]     0.0%      0  <-- worse
results: outputs/variants/variants32c_full_0_1009-0849/results.json
```

No variant passed stage 1 (all intervals below 0), so I did not spend runs on Full dev 20, a fresh seed or Small.

## 4. Why it loses (probe32 on two variants; per episode, devpick 6)
| | base | KR steer (max, 4 wk) | TW steer (mean) |
|---|---|---|---|
| J (T/ep) | 6.318 | 6.346 (+0.028) | 6.344 (+0.026) |
| KR memory / leading lots (M) | 17.08 / 2.30 | 17.26 / 1.53 | – |
| KR full-power weeks, fab GWh in them | 25.5, 11.6k | 23.3, 10.6k | – |
| KR shed GWh | 59.4k | 60.9k | – |
| KR top-fab share in partial weeks | 0.80 | 0.90 | – |
| TW leading / mature lots (M) | 7.19 / 10.37 | – | 7.56 / 2.25 |
| TW fab energy (GWh) | 23.7k | – | 17.1k |
| TW top-fab share in partial weeks | 0.60 | – | 0.92 |
| lost chip_mat units (M) | 54.6 | – | 59.8 |

- The steering itself works (the top fab's share in partial weeks rises to 0.90-0.92), but **it costs more than it
  gains**. A wafer at the low-value fab only steers power if that fab holds **less than one week of nameplate**, so the
  same wafers are missing in the full-power (pulse) weeks: at KR the leading fab lost 0.77M lots, mostly in full weeks,
  while memory gained only 0.17M (it is near its own cap in the partial weeks it matters). Wafers can't be moved out
  of a fab and take ≥1 week to arrive, so without knowing which weeks will be full vs partial the wafers can't be timed.
- Fewer wafers on hand also make pplan see less fab draw and plan fewer/smaller pulses (KR shed +1.5k GWh/ep).
- At TW the leftover power is badly estimated from past use: the leading fab saturates at its cap, mature gets almost
  nothing, and 6.6k GWh/ep of fab power goes unused (mature lots −8.1M, leading only +0.37M).
- US/EU: the "more valuable" leading chips are already disposed at the US fabs (1.2M/ep), so steering there only
  throws away sellable mature chips (steer_max_us −0.0023).

## Verdict
**Dead end, keep it off.** The ceiling was small to start with (gross, at pi, perfect knowledge of each week's
leftover: TW 0.041 + KR 0.030 T/ep ≈ 0.02 RSS; US/EU not sellable), and every no-foresight rule I tried loses
0.003-0.029 RSS on Full devpick with intervals below 0. Capturing part of it would need a planner that knows a
week ahead whether the grid will be full or partial and times wafer arrivals exactly (wafers that arrive for a full
week and are not used steal power in the next partial weeks); that is a joint fuel+wafer plan, not worth it for ≤0.02.

## Notes / choices made without asking
- Measurement used my own probe (`outputs/task-32/probe32.py`, task 28's world construction: no naive fallback;
  0 fallback weeks in every probed run, and the probe's RSS matches the runner's to 4 digits).
- `sbf check agents/mpc_steer --task=small` (steer off): passes, median act 0.095 s, max 0.148 s, week 1 0.123 s.
  Not run on Full since this is not a final candidate and steer-off plays like mpc_imit_room.
- Runs here are fast (6 Full episodes ≈ 1 min with the cache), timings are this machine's, not the server's.
