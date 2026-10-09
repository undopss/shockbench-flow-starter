Status: building agents/mpc_calm (switch test); sensitivity done: no calm/storm crossover

# Task 31: the calm episodes (harm level 1)

## Step 1, first pass (task 20's per-episode data, `mpc_fab3sell`, Full dev 20; `outputs/task-31/levels31.py`)

**Level-1 episodes on Full are not calm.** Every one has 4-12 energy shocks, 1-4 militarised closures, 22-35 sanctions;
the naive rule's gap is 3.26 T/ep (level 2: 3.07, level 3: 3.70, level 4: 3.65). The harm level sorts episodes by the
damage to the *naive plan*, not by how many disruptions there are, so there is no calm regime to switch into.
Pulses are worth *more* at level 1 than elsewhere (pulses off: L1 RSS 0.800 → 0.582, L2 0.854 → 0.794).

| level | RSS | gap T/ep | shortage (LE / MAT) | shed | pulse shed price | other |
|---|---|---|---|---|---|---|
| 1 | 0.800 | 0.651 | 0.313 / 0.105 | 0.178 (KR 0.081, IN 0.064, EU 0.020, JP 0.020) | 0.206 | 0.056 |
| 2 | 0.854 | 0.449 | 0.183 / 0.114 | 0.118 | 0.114 | 0.035 |
| 3 | 0.790 | 0.779 | 0.430 / 0.100 | 0.216 | 0.255 | 0.033 |
| 4 | 0.739 | 0.953 | 0.519 / 0.124 | 0.276 | 0.197 | 0.035 |

Level 1 vs level 2: +0.13 T more chip_le shortage (eps 7, 5, 10), shed at KR (ep 5: 0.18 T) and at **grid_in** (ep 7:
0.32 T, a grid with no fabs, shedding ~1000 GWh *every week* for 30+ weeks while the oracle sheds 0). In a first replay
of ep 7 with `mpc_imit_room` that grid_in shed is gone (weeks 1-40: shed only in weeks 3-8 and 26), so the baseline
already fixed it (to be confirmed by the full split).

## Step 1: the split for the baseline `mpc_imit_room` (Full dev 20, `outputs/task-31/levels_full_imit_room.txt`)

`gap17.py full 0 dev agents/mpc_imit_room 4` (0 fallback weeks). Pulse shed price = shed(with pulses) − shed(task 20's
mpc_fab3sell with every pulse off), so its grid_in entry is imit_room's fix, not the pulse.

| level | RSS | gap T/ep | chip_le | chip_mat | shed | shed by grid (> 0.01) | pulse shed price | other (holding, tariff, disposal, freight) |
|---|---|---|---|---|---|---|---|---|
| 1 | 0.821 | 0.581 | 0.315 | 0.110 | 0.102 | KR 0.073, JP 0.021, EU 0.019, TW −0.014 | 0.195 (w/o IN) | 0.054 |
| 2 | 0.858 | 0.437 | 0.178 | 0.113 | 0.112 | JP 0.045, CN 0.033, EU 0.020, TW 0.012, SEA −0.011 | 0.109 | 0.034 |
| 3 | 0.791 | 0.773 | 0.429 | 0.099 | 0.213 | TW 0.099, CN 0.053, KR 0.029, EU 0.016 | 0.254 | 0.032 |
| 4 | 0.755 | 0.892 | 0.514 | 0.124 | 0.220 | TW 0.117, EU 0.031, JP 0.032, CN 0.027, IN 0.013 | 0.191 | 0.031 |

imit_room already removed level 1's grid_in shed (0.064 → −0.001): L1 0.800 → 0.821. What is left at level 1:

- **Chips, 0.425 T of 0.581 (73%)**, almost all in 3 episodes: ep 7 (0.864: CN mature 22.6M lots short, KR memory 7.1M,
  JP memory 5.9M; the agent sheds 0.09 T *less* than the oracle; value fill 63% vs 82%), ep 5 (0.571: JP memory 11.0M
  lots short, TW leading 3.1M), ep 10 (0.403). This is fab power at CN/JP/KR (task 30's lever), not over-caution.
- **Shed 0.102**: ep 2 alone is 0.318 T. **Ep 2 is the one "too aggressive" episode**: the agent starts *more* lots than
  the oracle at almost every fab (+5.7M TW leading, +7.4M KR memory, +7.4M CN, +5.4M JP), sells the same (value fill
  48.7% vs 49.1%), disposes of 44 B USD of stock and pays 0.32 T of extra shed. The extra chips can't reach a sink.
- Holding/tariff/disposal/freight 0.054 (L2-4: 0.031-0.034): +0.02 T more at level 1, ≈0.3 L1 points.

So level 1's deficit vs level 2 is not a calm-specific behaviour: it is the same two levers as everywhere (fab power
where chips are short; pulses that buy unsellable chips), concentrated in eps 7 and 2.

## Step 2a: is the agent tuned for storms? Per-level sensitivity (Full dev 20, entropy 0, `outputs/task-31/sens31.json`)

`uv run python outputs/variants.py full 0 dev outputs/task-31/sens31.json 4` (round `sens31_full_0_1009-0846`):
```
full, entropy 0, 20 episodes; diff = variant - imit_room, 90% paired interval
variant                      RSS     L1     L2     L3     L4     diff  interval               better%  fallb
imit_room                 0.8228  0.821  0.858  0.791  0.755  +0.0000  [+0.0000, +0.0000]     nan%      0
wb2                       0.8108  0.813  0.847  0.766  0.746  -0.0120  [-0.0181, -0.0056]     0.1%      0  <-- worse
wb4                       0.8233  0.824  0.855  0.793  0.752  +0.0005  [-0.0051, +0.0051]    57.1%      0
sw1.5                     0.8113  0.814  0.840  0.775  0.748  -0.0115  [-0.0201, -0.0026]     2.1%      0  <-- worse
sw4.5                     0.8204  0.817  0.855  0.795  0.755  -0.0024  [-0.0063, +0.0013]    15.5%      0
ppv10                     0.8220  0.823  0.853  0.790  0.756  -0.0008  [-0.0029, +0.0009]    28.3%      0
ppv40                     0.8198  0.820  0.850  0.791  0.756  -0.0029  [-0.0056, -0.0007]     0.3%      0  <-- worse
```
(wb = `wafer_buffer` weeks, default 3; sw = `safety_weeks`, default 3; ppv = `pp_value`, default 20.)
**No knob is "built for storms":** less buffer or less fuel safety is worse at level 1 too (wb2 −0.008, sw1.5 −0.007
at L1), and nothing moves level 1 by more than +0.003.

Ceiling of a switch among these 7 settings (`outputs/task-31/switch_bound31.py`, my own pooled RSS, 0.8244 for the
baseline vs the runner's 0.8228): a switch that **knows the harm level** and picks the best setting per level:
**+0.0017**; one that picks the best setting **per episode in hindsight**: +0.010 (an optimistic bound: it also
selects on noise). Both far below +0.05.

Observable "calm weeks" (no closure, energy shock or piracy active in the last 4 weeks, from the episode's events)
don't follow the harm level either: L1 148 of 520 weeks, L2 78, L3 126, L4 17; two of five L1 episodes have none.
