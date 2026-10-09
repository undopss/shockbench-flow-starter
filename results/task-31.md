Status: running a per-level parameter sensitivity on Full dev 20 (baseline split done)

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
