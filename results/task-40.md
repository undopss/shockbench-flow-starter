Status: dev 20 round 1 done (smart3 +0.0024, end4 +0.0009 above 0); running round 2 (smart3+end4 combo)

# Task 40: lost generation during pulses (`agents/mpc_pleak`)

## Setup notes (choices made without asking)
- **The home tgz cache does not match this machine**: its joblib / reference keys hold generator id `93b801…`, this
  container computes `7740c88…` for the same package and instance (same Python patch version too: I checked with
  Python 3.13.5, still `7740c88…`; tasks 37/38 saw the same). So the Full dev references were rebuilt here once
  (~25 min, mostly the harm cut points). I saved them as **`cache/sbf-cache-cloud.tgz`** (same layout; unpack with
  `tar xzf cache/sbf-cache-cloud.tgz -C ~/.cache`) so the next cloud session skips that. Only the Full dev root 0 is in
  it, as the task's speed rule asks (no other seeds were used).
- mpc_best reproduces exactly: Full dev 20 RSS **0.8454** (task 38's number).

## 1. Measurement (Full dev 20, mean per episode)
Script `outputs/task-40/pleak.py` (plays as `cost_breakdown.py`; data in `outputs/task-40/pleak_full_0_dev.json`) and
`outputs/task-40/split.py`. "nopulse" = mpc_best with `pulse_plan: false, pulse_weeks: 0` (no planner, no hold rule).
RSS: best 0.8454, nopulse 0.6688 (pulses are worth +0.177 RSS, 0.613 T/ep).

```
  shortage        best   2.2430e+12 nopulse   3.0673e+12 diff  -8.2431e+11
  shed            best   4.2123e+12 nopulse   4.0108e+12 diff  +2.0157e+11
  tariff          best   2.0886e+10 nopulse   1.6170e+10 diff  +4.7159e+09
  disposal        best   1.4026e+10 nopulse   1.0949e+10 diff  +3.0766e+09
  holding         best   3.2936e+10 nopulse   3.1855e+10 diff  +1.0811e+09
  freight         best   1.7956e+10 nopulse   1.7613e+10 diff  +3.4266e+08
  TOTAL J         best   6.5364e+12 nopulse   7.1499e+12 diff  -6.1346e+11

grid       d shed (USD)   fab energy best|nopulse  d gen  0-shed weeks best|nopulse  ration weeks (rationed fuel) best|nopulse
grid_tw    +6.118e+10     23593 | 11043            -2280  70.8 | 40.8               31.3 | 77.3
grid_kr    +5.304e+10     19689 |  8557            -1724  57.4 | 24.9               37.9 | 79.4
grid_jp    +1.395e+10      4912 |  2476             -946  28.8 | 15.2               42.4 | 45.4
grid_cn    +5.668e+10     17658 |  4500             -582  50.4 | 18.2               28.7 | 40.9
grid_us    +0              17893 | 17964              -70  97.0 | 97.0                -
grid_eu    +1.399e+10      9711 |  6898             -579  57.3 | 44.6               25.4 | 46.2
grid_sea   +2.750e+09      1578 |  1001              -90  17.0 | 12.3                5.5 |  5.3
TOTAL fab grids: d shed +2.0159e+11 USD = transfer to fabs +1.7572e+11 + lost generation +2.5870e+10
```
Split of the pulse-related shed (+0.202 T/ep):
- **(a) home → fab transfer: 0.176 T** (fab energy +42.7k units; it buys 0.82 T of chip sales).
- **(b) generation lost: 0.026 T ≈ 0.0076 RSS** (6271 units of output):
  - fuel not burned −4548 units: terminals overflow while fuel is held (terminal disposal +26.3k units vs +14.8k more
    fuel shipped in; at CN/SEA the extra shipments ≈ the extra disposal, i.e. supply that the source would have thrown
    away anyway; at **KR, TW, JP the overflow eats delivered fuel**), net of end-stock −6.9k;
  - non-fuel output curtailed −1723 units (null / nuclear segments scaled by load < 1 in full weeks: the surplus of a
    pulse week; inherent to pulsing);
  - rationing is **not** a leak any more: the planner rations far fewer weeks than no pulse (TW 31 vs 77).
  - fuel left at the episode end: +0.7k (TW), +0.7k (KR) units: small.
- **(c) other: ~0** (US/EU/SEA small; the extra disposal + tariff + freight on shipped-then-dumped fuel is ≈ 0.008 T in
  USD outside shed).

Ceiling for task 40 = (b) + the dumped fuel's cost ≈ **0.034 T ≈ +0.01 RSS**, with the non-fuel 0.007 T unreachable,
so realistically ≤ +0.005..0.008.

## 2. Options built (`agents/mpc_pleak` = mpc_best + `_pleak()` in agent.py, all off by default)
Applied to the terminal -> grid slots of the planned / pulsed grids after the hold rule and the planner (before
imit_grid's clip). They only raise a release, never lower one.
- `pl_trickle` f: mini pulses, release at least f x terminal stock every week (the user's fixed trickle).
- `pl_smart` + `pl_smart_w` w: smart mini pulse, release the terminal stock the next full week does not need:
  everything above `w x segment (share G-bar) + psi I-bar - grid stock - arrivals at the grid this week`.
- `pl_overflow`: release at least what would overflow the terminal's storage after this week's arrivals.
- `pl_end` N: in the last N weeks of the episode release everything (nothing held is worth anything at the end).

## 3. Probe, Full devpick:2,2,1,1 (6 episodes)
```
full, entropy 0, 6 episodes; diff = variant - mpc_best, 90% paired interval
variant                      RSS     L1     L2     L3     L4     diff  interval               better%  fallb
mpc_best                  0.8864  0.890  0.895  0.873  0.857  +0.0000  [+0.0000, +0.0000]     nan%      0
trickle10                 0.8858  0.887  0.900  0.875  0.828  -0.0006  [-0.0022, +0.0011]    19.6%      0
trickle25                 0.8739  0.868  0.894  0.872  0.815  -0.0124  [-0.0254, -0.0010]     0.0%      0  <-- worse
smart1                    0.8771  0.871  0.898  0.872  0.827  -0.0093  [-0.0223, +0.0052]    18.2%      0
smart2                    0.8901  0.891  0.905  0.876  0.849  +0.0038  [+0.0005, +0.0074]   100.0%      0  <-- better
overflow                  0.8900  0.891  0.904  0.876  0.850  +0.0036  [+0.0003, +0.0073]   100.0%      0  <-- better
end4                      0.8880  0.892  0.895  0.874  0.857  +0.0016  [+0.0004, +0.0029]   100.0%      0  <-- better
```
(`outputs/variants/v40_probe_full_0_1010-1023/results.json`). A fixed trickle starves the pulse (10% flat, 25% clearly
worse); the smart trickle with a 1-week need also starves it, with a 2-week need it helps.

## 4. Full dev 20, round 1
```
full, entropy 0, 20 episodes; diff = variant - mpc_best, 90% paired interval
variant                      RSS     L1     L2     L3     L4     diff  interval               better%  fallb
mpc_best                  0.8454  0.850  0.874  0.810  0.767  +0.0000  [+0.0000, +0.0000]     nan%      0
trickle10                 0.8410  0.845  0.873  0.804  0.758  -0.0044  [-0.0074, -0.0015]     0.4%      0  <-- worse
overflow                  0.8457  0.849  0.876  0.811  0.766  +0.0003  [-0.0019, +0.0028]    58.4%      0
smart2                    0.8463  0.850  0.878  0.809  0.769  +0.0009  [-0.0012, +0.0033]    76.0%      0
smart3                    0.8478  0.851  0.879  0.811  0.770  +0.0024  [+0.0002, +0.0048]    95.9%      0  <-- better
end4                      0.8463  0.852  0.874  0.811  0.768  +0.0009  [+0.0002, +0.0017]   100.0%      0  <-- better
ovf_end4                  0.8467  0.850  0.877  0.812  0.767  +0.0013  [-0.0011, +0.0038]    80.0%      0
smart2_ovf_end4           0.8477  0.851  0.879  0.811  0.769  +0.0023  [+0.0001, +0.0047]    96.0%      0  <-- better
```
(`outputs/variants/v40_dev_full_0_1010-1030/results.json`). The devpick-6 gains of overflow / smart2 shrank on dev 20
(as in task 33); the fixed trickle (user's mini pulse, 10%) is reliably harmful.
