# Task 3: planned pulses (`agents/mpc_pulse`)

## What it is
`agents/mpc_pulse` = `mpc_chip` + `pplan.py`. Every week, for every `base_first` grid that feeds fabs, a planner
chooses how much fuel each terminal→grid slot releases (lng, crude). Off switch: `"pulse_plan": false`.

- **Method `enum` (default):** every sequence of weekly release modes over 6 weeks (4^6 = 4096: hold / just enough
  for full output / that plus the rationing line psi·Ibar / release everything) is simulated with the step-7 rules:
  rationing on I_prev, `min(share·G·ration, on hand)`, homes first, `burn = av·load`, disposal above storage,
  dispatch only from last week's terminal stock, a shared edge cap. Only week 1 is played. ~1–4 ms per grid.
- Inputs: terminal arrivals = pipeline + chokepoint queues + the energy LP's future shipments. Fuels without a
  terminal slot (nucfuel) are simulated ahead. Fab draw is computed from wafers (pipeline) and `cap_eff`.
- Objective: VOLL·homes + V·fab energy + 0.9·VOLL·fuel left at the end. V = `pp_value` × pi of the chip × R/e
  (per unit of energy). **Default `pp_value` = 5.0.**
- `pp_method: "milp"` (scipy milp, the same model) is also there, but HiGHS spends 0.3–0.5 s per grid at the root
  node and it played worse (+0.015). Not recommended.
- `pp_chip_value: true` (the chip LP's shadow price instead of pi) gives ~0: the chip LP assumes the fabs get full
  power, so it sees no shortage and its shadow prices are ~0.

## Why it works (Full ep 0, measured)
G-bar ≈ y-bar + the full fab draw (JP: 18000 vs 17819 + 181), so any fuel shortfall leaves the fabs with zero
power. Each fuel's output is capped at share·G, so fuels can't substitute for each other: JP is short of **crude**
(554 vs 900 per week) while its LNG overflows storage. KR is short of both lng and crude, so the pulses have to line
up in the same week.

## Results (runner tables exactly as printed)

Stage 2, Full 6 dev (round task3_r1):
```
full, entropy 0, 6 episodes; diff = variant - mpc_chip, 90% paired interval
variant                      RSS     L1     L2     L3     L4     diff  interval               better%  fallb
mpc_chip                  0.5802  0.517  0.692  0.568  0.522  +0.0000  [+0.0000, +0.0000]     nan%      0
pulse_all_15              0.5263  0.502  0.541  0.550  0.567  -0.0539  [-0.0773, -0.0273]     0.0%      0  <-- worse
pp_enum_lpval             0.5810  0.517  0.692  0.572  0.522  +0.0008  [+0.0007, +0.0009]   100.0%      0  <-- better
pp_enum_pi05              0.6205  0.546  0.735  0.618  0.613  +0.0404  [+0.0105, +0.0742]   100.0%      0  <-- better
pp_enum_pi10              0.6230  0.556  0.713  0.620  0.706  +0.0429  [+0.0132, +0.0764]   100.0%      0  <-- better
pp_milp_pi05              0.5953  0.538  0.694  0.578  0.585  +0.0151  [-0.0013, +0.0338]    94.8%      0
```
(In round r1, `pp_enum_lpval` used the chip LP's shadow price; the pi-valued variants have `pp_chip_value: false`.)

Full 6 dev, value and horizon (rounds task3_r3, task3_r4):
```
pp_enum_pi10              0.6230  0.556  0.713  0.620  0.706  +0.0429  [+0.0132, +0.0764]   100.0%      0  <-- better
pp_enum_pi20              0.6547  0.611  0.731  0.622  0.720  +0.0745  [+0.0174, +0.1391]   100.0%      0  <-- better
pp_enum_pi10_H7           0.6163  0.544  0.714  0.611  0.707  +0.0361  [+0.0160, +0.0588]   100.0%      0  <-- better
pp_enum_pi30              0.6573  0.623  0.718  0.627  0.718  +0.0771  [+0.0200, +0.1417]   100.0%      0  <-- better
pp_enum_pi50              0.6628  0.631  0.719  0.638  0.716  +0.0826  [+0.0224, +0.1508]   100.0%      0  <-- better
```

Stage 1, Small, random root 1039472713, 20 episodes (rounds task3_r2, task3_r5):
```
small, entropy 1039472713, 20 episodes; diff = variant - mpc_chip, 90% paired interval
variant                      RSS     L1     L2     L3     L4     diff  interval               better%  fallb
mpc_chip                  0.6486  0.630  0.647  0.688  0.790  +0.0000  [+0.0000, +0.0000]     nan%      0
pp_enum_pi05              0.6852  0.684  0.662  0.714  0.774  +0.0366  [+0.0107, +0.0656]    99.7%      0  <-- better
pp_enum_pi10              0.6915  0.693  0.668  0.712  0.768  +0.0430  [+0.0176, +0.0713]   100.0%      0  <-- better
pp_enum_pi20              0.6932  0.694  0.668  0.717  0.777  +0.0446  [+0.0184, +0.0742]   100.0%      0  <-- better
pp_enum_pi50              0.6943  0.695  0.670  0.719  0.777  +0.0457  [+0.0202, +0.0750]   100.0%      0  <-- better
```

## Verdict
**Promising: +0.083 Full (6 dev, interval [+0.022, +0.151]) and +0.046 Small (20 fresh, [+0.020, +0.075])** with the
default `pp_value` 5.0. Most of the gain is at L1 (calm), which carries 50% of the weight. Caveats: the value
(2/3/5) was chosen on these same 6 Full dev episodes, and the Full interval is wide. It should be confirmed on fresh
Full episodes (task 7's method) with `agents/mpc_pulse` before it becomes the final pick.

## Checks
`sbf check mpc_pulse --task=small`: pass, max 0.135 s / median 0.061 s per week (1 dev episode).
`sbf check mpc_pulse --task=full`: pass, max 0.280 s / median 0.179 s per week (1 dev episode).
Own run of Full ep 0 (`outputs/task3/cpu.py`): max 0.28 s, median 0.16 s.

## Surprises
- The fixed rule `pulse_weeks 1.5` on **all** grids is *worse* on Full here (−0.054); only the planned version wins.
- Pulses pay off even at 0.5×pi. A unit of fab energy is worth R/e wafers (500–1100 chips), many times VOLL.
