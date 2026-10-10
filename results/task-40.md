Status: measurement done; running the devpick-6 probe of the fixes

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
