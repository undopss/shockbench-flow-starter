Status: running Full devpick test (measurement done, below)

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
