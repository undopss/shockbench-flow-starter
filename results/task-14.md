Status: done — verdict: TOO SMALL (ceiling ≈ 0.05 T USD/episode for a cheaper pulse; ≈ 0.12 T even counting other grids)

# Task 14: a cheaper pulse (measure first)

Baseline `agents/mpc_pulse` (TW/KR pulse 1.5 w + fab_cap observed) vs the same agent with `{"pulse_weeks": 0}`
(identical code to `agents/mpc_chip` + `fab_cap_mode: observed`: the two folders differ only in these PARAMS).
Script: `outputs/task-14/pulse_cost.py` (plays both as `cost_breakdown.py` does; per grid/week shed, served load,
fab energy, lots). Data: `outputs/task-14/pulse_cost_full_0_dev.json`, `..._devpick-2-2-1-1.json`.

## Full dev 20 (root 0), mean USD per episode, diff = pulse − nopulse
RSS: pulse 0.6752, nopulse 0.5949 (reproduces mpc_pulse's 0.6751 / the +0.08 gain).
```
  tariff          pulse   1.7123e+10 nopulse   1.5111e+10 diff  +2.0120e+09
  holding         pulse   2.9980e+10 nopulse   2.9745e+10 diff  +2.3478e+08
  shortage        pulse   2.8394e+12 nopulse   3.2399e+12 diff  -4.0050e+11
  disposal        pulse   3.1218e+09 nopulse   2.9130e+09 diff  +2.0878e+08
  shed            pulse   4.1727e+12 nopulse   4.0571e+12 diff  +1.1563e+11
  TOTAL J         pulse   7.0770e+12 nopulse   7.3593e+12 diff  -2.8232e+11

grid           shedUSD p  shedUSD np   d shedUSD     lots p    lots np   energy p  energy np 0-shed wk p    np
grid_tw        1.844e+11   1.286e+11  +5.584e+10  1.162e+07  5.552e+06  1.577e+04       7798        64.6  44.7
grid_kr        3.834e+11   3.245e+11  +5.890e+10  1.002e+07  4.353e+06  1.352e+04       5875        60.1  25.6
grid_jp        8.111e+11   8.102e+11  +9.112e+08  1.046e+06  1.065e+06       1318       1342        13.4  13.3
grid_cn        6.884e+11   6.883e+11  +1.040e+08  3.987e+06  3.851e+06       3588       3466        20.4  19.9
grid_us        4.243e+11   4.243e+11  -2.005e+07  8.914e+06   9.34e+06       9901  1.061e+04        97.0  97.0
grid_eu        4.624e+11   4.623e+11  +7.577e+07  3.547e+06  3.698e+06       3895       4106        44.6  44.6
grid_sea       1.079e+12   1.079e+12  -4.990e+06  4.938e+05  5.053e+05      444.4      454.8        10.8  10.8
```
Split of the added TW/KR shed (VOLL 4.125 M USD per unit on both grids):
```
grid_tw fab energy diff 7974 served diff -13536 generation diff -5563 -> -0.023 T USD
grid_kr fab energy diff 7643 served diff -14278 generation diff -6635 -> -0.027 T USD
```
So of +0.116 T shed: **0.065 T is power moved from homes to fabs** (that is the pulse working: under base_first it is
the only way fabs get power, and it buys 0.40 T of chips, ~26 M USD of chips per energy unit vs 4.1 M VOLL), and
**0.051 T is generation lost outright** (fuel held back → ration factor / end-of-horizon stock). Full 6 (devpick
2,2,1,1) gives the same picture (+0.112 T shed; lost generation 4.7k+7.0k units ≈ 0.048 T).

## Ceiling
- (a) A perfect cheaper pulse (same fab energy, no lost generation): **≈ 0.05 T** (+tariff/disposal 0.002 T).
  Absolute upper bound if the whole added shed were free: 0.118 T — not reachable, since 0.065 T is the transfer to
  fabs itself.
- (b) Other grids / timings, probe on Full 6 vs mpc_pulse (`outputs/task-14/variants_probe.json`):
```
full, entropy 0, 6 episodes; diff = variant - mpc_pulse, 90% paired interval
variant                      RSS     L1     L2     L3     L4     diff  interval               better%  fallb
mpc_pulse                 0.7132  0.725  0.753  0.625  0.709  +0.0000  [+0.0000, +0.0000]     nan%      0
pulse_allfab_15           0.5639  0.557  0.579  0.554  0.571  -0.1493  [-0.1692, -0.1281]     0.0%      0  <-- worse
pulse_twkrcneu_15         0.5600  0.548  0.568  0.572  0.573  -0.1532  [-0.1795, -0.1268]     0.0%      0  <-- worse
pulse_twkr_10             0.7179  0.724  0.761  0.639  0.708  +0.0047  [-0.0046, +0.0130]    75.1%      0
pulse_twkr_12             0.7126  0.715  0.759  0.636  0.706  -0.0006  [-0.0110, +0.0086]    36.3%      0
pulse_twkr_20             0.7160  0.733  0.745  0.638  0.693  +0.0028  [-0.0080, +0.0151]    70.3%      0
```
  Pulse size 1.0–2.0 weeks: flat. Adding CN/EU: −0.15 (strongly harmful; not investigated why). Task 2: JP/SEA
  +0.020 RSS ≈ 0.07 T at best.
- Total ≈ 0.05 T (shed) + ≤ 0.07 T (other grids, already available as an option) ≈ **0.12 T < 0.17 T bar**.

## Verdict
**Too small; nothing built.** The pulse's extra shed is mostly the intended home→fab transfer; the recoverable waste
is ~0.05 T/episode (~+0.015 RSS). Choices made without asking: used `mpc_pulse` + `pulse_weeks: 0` as "mpc_chip +
observed" (identical code); ran the probe on Full 6 only (all intervals flat or clearly worse, so no Full 20 run).
Surprise: pulsing CN/EU (or all fab grids) costs −0.15 RSS — never add them.
