Status: Full fresh-seed check running (Full dev 20 and Small fresh 20 done: both better)

# Task 12: wasted power and wasted fuel (baseline `agents/mpc_pulse`)

## Measure

Script: `outputs/task-12/waste.py` (plays the agent the way `outputs/cost_breakdown.py` does, and logs every
`allocate_energy` call: g_av, y-bar, E-hat, y, E per grid and week). Chip value of one power unit at fab f =
pi(packaged product, weighted by lost sales over the sinks that lost sales in that episode) × R_f / e_f (≈ 25 M USD per
power unit for leading-edge chips). Only lots started before T − (tau + 4) count. Each product's total is capped by its
lost-sales USD (the cap never bound).

Full dev `devpick:2,2,1,1`, USD per episode (mean of 6):

| lever | USD/episode | how |
|---|---|---|
| (a) power left over at a fab grid while its fabs were **wafer-limited** | **7.9e11** | homes served and every fab's request served, leftover > 0, fabs below capacity because they had no wafers: min(leftover, draw at capacity), valued at the best such fabs |
| (a) of which non-storable (the non-fuel segment) | 3.8e11 | the fuel part of the leftover stays in stock, so this part is the strict lower bound of the waste |
| (b) fuel disposed of at fab grids/terminals | 2.5e10 (+1.2e9 shed) | disposed fuel added to the most valuable later needs (shed at VOLL, unmet fab draw), limited by that fuel's segment headroom share·G-bar·ration − available. Most disposal (US LNG 290k, IN LNG 94k units) is at grids whose LNG segment is already at its share cap, so it can't help |
| (c) weeks 0-1% short of homes+fabs (fabs got ~nothing) | 2.0e11 | fab draw left unmet in those weeks. Mostly grid_cn (65 of 104 weeks 0-1% short); covering that would take ~41k fuel units per episode at CN. 1-5% short: 6.1e11; >5%: 7.7e11 |

Raw table (`outputs/task-12/full6.log`, JSON `outputs/task-12/waste_full_0_devpick-2_2_1_1_mpc_pulse.json`):

```
  ep lvl   lost_usd shortage_usd   shed_usd      unmet          a     a_null          b     b_shed         c1         c5       cbig
   2   1  2.747e+12  2.747e+12  2.252e+12  1.256e+12  1.120e+12  5.138e+11  5.109e+10  7.257e+09  2.058e+11  4.082e+11  6.424e+11
   5   1  2.619e+12  2.619e+12  2.228e+12  2.136e+12  5.280e+11  2.651e+11  2.371e+10  0.000e+00  4.081e+11  7.770e+11  9.509e+11
   0   2  2.769e+12  2.769e+12  2.369e+12  1.494e+12  7.590e+11  3.768e+11  2.009e+10  0.000e+00  1.780e+11  2.952e+11  1.020e+12
   1   2  2.073e+12  2.073e+12  5.610e+12  1.705e+12  6.677e+11  3.244e+11  2.182e+10  0.000e+00  5.013e+10  1.019e+12  6.358e+11
  53   3  3.172e+12  3.172e+12  3.857e+12  1.242e+12  1.113e+12  5.363e+11  1.734e+10  0.000e+00  1.965e+11  5.961e+11  4.492e+11
  26   4  2.994e+12  2.994e+12  7.965e+12  1.590e+12  5.688e+11  2.720e+11  1.729e+10  0.000e+00  1.314e+11  5.539e+11  9.051e+11
    mean  2.729e+12  2.729e+12  4.047e+12  1.570e+12  7.928e+11  3.814e+11  2.522e+10  1.210e+09  1.950e+11  6.082e+11  7.673e+11
```

Per grid, a_units (power units per episode): TW 11.4k, US 14.9k, KR 10.1k, CN 1.9k, EU 3.7k, JP 1.0k, SEA 0.7k.

**Ceiling (a) ≈ 0.79 T USD/episode (at least 0.38 T): far above the 0.17 T bar → built.** (b) too small. (c) is
0.2 T on paper, but almost all of it is at CN and needs ~41k extra fuel units there; not built.

Why (a) happens: with `fab_cap_mode: observed` the chip LP plans a power-starved fab at its recent starts, so it keeps
only ~2× recent starts in wafers. When a pulse (or a calm week) gives the grid spare power, the fab can start only the
few wafers it holds.

## Build: `agents/mpc_buffer`

A copy of `mpc_pulse` with one new chip-LP option, **`wafer_buffer`** (weeks of nameplate starts kept on hand as
wafers at every fab, soft: `I[wafer@fab, t] + short[f, t] >= wafer_buffer · cap_eff`, capped at 95% of the fab's wafer
storage; `short` costs `buffer_cost` = 1000 USD per wafer-week). In the folder it is **on by default (3.0)**; `0`
gives back `mpc_pulse` exactly. Files: `agents/mpc_buffer/chips.py`, `agents/mpc_buffer/agent.py` (PARAMS).

## Test (baseline `agents/mpc_pulse`)

Full 6 (`full 0 devpick:2,2,1,1`):
```
variant                      RSS     L1     L2     L3     L4     diff  interval               better%  fallb
mpc_pulse                 0.7132  0.725  0.753  0.625  0.709  +0.0000  [+0.0000, +0.0000]     nan%      0
buf1                      0.7697  0.771  0.800  0.724  0.751  +0.0565  [+0.0556, +0.0576]   100.0%      0  <-- better
buf2                      0.7876  0.784  0.810  0.768  0.761  +0.0744  [+0.0701, +0.0793]   100.0%      0  <-- better
buf1_c10k                 0.7699  0.771  0.800  0.726  0.751  +0.0567  [+0.0552, +0.0584]   100.0%      0  <-- better
buf05                     0.7477  0.757  0.786  0.670  0.731  +0.0345  [+0.0339, +0.0351]   100.0%      0  <-- better

buf3                      0.7902  0.786  0.813  0.771  0.768  +0.0770  [+0.0714, +0.0834]   100.0%      0  <-- better
buf4                      0.7890  0.782  0.813  0.774  0.765  +0.0758  [+0.0717, +0.0804]   100.0%      0  <-- better
buf6                      0.7890  0.782  0.813  0.774  0.765  +0.0758  [+0.0717, +0.0804]   100.0%      0  <-- better
```
(the second block is a second run with the same baseline and episodes; buf4 = buf6 because the wafer storage caps the buffer.)

Full dev 20 (`full 0 dev`):
```
variant                      RSS     L1     L2     L3     L4     diff  interval               better%  fallb
mpc_pulse                 0.6752  0.650  0.752  0.635  0.632  +0.0000  [+0.0000, +0.0000]     nan%      0
buf2                      0.7337  0.710  0.796  0.717  0.687  +0.0585  [+0.0471, +0.0719]   100.0%      0  <-- better
buf3                      0.7363  0.712  0.798  0.720  0.689  +0.0610  [+0.0489, +0.0753]   100.0%      0  <-- better
```

Small fresh seed (`small random 20`, entropy 317049864), `mpc_buffer` = buffer 3:
```
variant                      RSS     L1     L2     L3     L4     diff  interval               better%  fallb
mpc_pulse                 0.6892  0.623  0.744  0.690  0.846  +0.0000  [+0.0000, +0.0000]     nan%      0
mpc_buffer                0.7247  0.655  0.778  0.750  0.872  +0.0355  [+0.0266, +0.0458]   100.0%      0  <-- better
```

FULL_FRESH_PLACEHOLDER

## sbf check (agents/mpc_buffer, buffer 3)

Both pass. CPU per week on this cloud machine (1 dev episode): Small median 0.037 s, max 0.074 s; Full median 0.133 s,
max 0.227 s (budgets 2 s / 4 s). This machine is much faster than the home server, so re-time it there before upload.

## Verdict

**Wafer buffer at fabs: +0.061 RSS on Full dev 20 vs `mpc_pulse` (0.7363 vs 0.6752), better on 20/20 episodes.** A final
candidate (not uploaded). Choices I made alone: buffer 3 weeks (2-6 are all within noise of each other on Full 6, 3 was
best on Full 20 by +0.003), buffer_cost 1000 (10000 gave the same result).

Not done: per-fab buffers (only fabs on grids with spare power), and (c) for CN.
