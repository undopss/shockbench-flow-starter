Status: done — imit_room is better on all three Full sets (dev 20 +0.0128, fresh seed +0.0056, devpick +0.0035, every 90% interval > 0) and does no harm on Small. It is real, but far below the +0.05 bar.

# Task 26: learn from the perfect plan what doesn't need foresight (imitation)

Plan: solve the oracle LP on Full and Small training episodes from our own root, record its structural decisions
(grid and terminal stocks, fab power and lots, wafer stocks) next to mpc_fab3sell's, fit rules that use only what an
agent can observe, build agents/mpc_imit and run the funnel.

## 1. What the oracle does differently (Full root 2626, 40 episodes; `outputs/task-26/an_full.txt`, `rules_full.txt`)

- **Fuel stays at the terminal, and the grid sits at the rationing line.** The oracle's rationed fuels (LNG) end most
  weeks with `(I - psi*I_bar)/burn` ≈ 0: the grid holds just psi·I-bar plus about one week of burn. Everything else
  waits at the terminal. mpc_fab3sell often fills the grid to 3-4 weeks of burn (grid_us/lng p50 4.0 vs 1.2; grid_sea/lng
  1.67 vs 1.20; grid_jp/lng 1.76 vs 1.20).
- **The oracle never disposes of fuel. We do** (Small: grid_eu/lng 69, grid_jp/lng 29, grid_tw/lng 19 units/week).
  Overfilled grids spill, and the spill is paid for twice: the fuel itself and its disposal.
- **It ships less**, mainly on the expensive long routes (uranium/enrichment pipes about half of ours; Qatar LNG via
  Hormuz 2219 vs 3253; US LNG 30.9k vs 35.2k per week), and it burns the same fuel. The surplus we ship ends as stock
  or spill.
- **Fabs run in long on/off blocks** (lag-1 autocorrelation of utilisation 0.85-0.96 vs 0.05-0.55 for us on most
  fabs; runs of ≥90% utilisation last 10-25 weeks vs 2-4 for us), with almost no wafer stock (p50 0 weeks of capacity
  vs 0.5-3 for us). Mean utilisation goes both ways (lower on most US/TW fabs, higher on kr_memory, cn_mature, sea_mature). The *timing* of those blocks follows chip demand and the
  disruptions it foresees, so we found no observable rule that predicts it (not built).
- Held-out check of the grid rule (20 train / 20 test episodes, `rules_full.txt`, "Rule G/C"): in weeks with enough
  fuel in the pool, the oracle's end-of-week grid stock lands within 0.25 week of burn of the fitted level in 55-99% of
  the weeks on most crude/LNG pools (grid_us/crude 99%, grid_eu/crude 97%, grid_sea/lng 93%, grid_jp/lng 83%).
  Exceptions: grid_tw/lng, grid_cn/lng, grid_sea/crude and grid_in/lng (8-19%). mpc_fab3sell hits the same band in only
  3-64% of weeks.

Cost J on those 40 episodes: oracle 5.744 T USD, mpc_fab3sell 6.451 T USD.

## 2. What was built: `agents/mpc_imit` (off by default) and `agents/mpc_imit_room` (rule on)

One option, `imit_grid`, caps every terminal → grid release after the planners have run:
- **"room"**: never send more than fits. Release ≤ grid storage − current grid stock − fuel arriving at the grid this
  week + `imit_burn` (0.9) × this week's possible burn (rationed if below the line). This stops the overfill and spill;
  the fuel stays at the terminal for later.
- **"target"**: the same, plus a cap at the oracle's level: the grid ends the week at most at psi·I-bar + `imit_margin`
  (1.0) week of burn.
- `lp_overflow_cost` (default 100, as before) exposes the energy LP's penalty on fuel planned above storage. Unchanged
  in every variant here.

"Both rules on" is the same as "target": in the code, target = min(room cap, target cap). So no separate variant was
run; its numbers are the imit_target rows.

## 3. Results (runner `outputs/variants.py` after the params.json fix; baseline = mpc_fab3sell with its own params)

Full dev 20 (entropy 0, `variants26_full_0_1008-2055`):
```
variant                      RSS     L1     L2     L3     L4     diff  interval               better%  fallb
mpc_fab3sell              0.8099  0.800  0.854  0.790  0.739  +0.0000  [+0.0000, +0.0000]     nan%      0
imit_room                 0.8228  0.821  0.858  0.791  0.755  +0.0128  [+0.0023, +0.0295]   100.0%      0  <-- better
imit_target               0.8212  0.822  0.852  0.791  0.754  +0.0112  [-0.0012, +0.0302]    88.1%      0
```

Fresh Full seed (overfitting guard), **entropy 1461252710** (random), 12 episodes (`variants26_full_1461252710_1008-2134`):
```
variant                      RSS     L1     L2     L3     L4     diff  interval               better%  fallb
mpc_fab3sell              0.8040  0.872  0.748  0.690  0.835  +0.0000  [+0.0000, +0.0000]     nan%      0
imit_room                 0.8096  0.874  0.763  0.690  0.838  +0.0056  [+0.0013, +0.0100]   100.0%      0  <-- better
imit_target               0.8089  0.873  0.762  0.692  0.836  +0.0050  [+0.0012, +0.0088]    99.6%      0  <-- better
```

Small dev 20 (no-harm check, entropy 0, `variants26_small_0_1008-2144`):
```
variant                      RSS     L1     L2     L3     L4     diff  interval               better%  fallb
mpc_fab3sell              0.7815  0.810  0.750  0.795  0.670  +0.0000  [+0.0000, +0.0000]     nan%      0
imit_room                 0.7823  0.811  0.751  0.795  0.670  +0.0008  [+0.0002, +0.0018]   100.0%      0  <-- better
imit_target               0.7825  0.811  0.750  0.796  0.670  +0.0010  [-0.0002, +0.0024]    91.9%      0
```

Earlier funnel stages (first session):
Full devpick:2,2,1,1 (`variants26_full_0_1008-1503`):
```
mpc_fab3sell              0.8500  0.843  0.869  0.838  0.845  +0.0000  [+0.0000, +0.0000]     nan%      0
imit_room                 0.8535  0.845  0.875  0.842  0.846  +0.0035  [+0.0019, +0.0054]   100.0%      0  <-- better
imit_target               0.8505  0.841  0.873  0.840  0.844  +0.0005  [-0.0000, +0.0010]    93.4%      0
```
Small random 20, entropy 1372962772 (`variants26_small_1372962772_1008-1530`):
```
mpc_fab3sell              0.7145  0.656  0.792  0.701  0.786  +0.0000  [+0.0000, +0.0000]     nan%      0
imit_room                 0.7149  0.656  0.792  0.702  0.786  +0.0003  [-0.0000, +0.0008]    91.8%      0
imit_target               0.7179  0.658  0.796  0.706  0.794  +0.0033  [+0.0015, +0.0055]   100.0%      0  <-- better
```

## 4. sbf check (this cloud machine, 1 dev episode)

`agents/mpc_imit_room` (= mpc_imit + `"imit_grid": "room"`): all checks pass.
- Small: week 1 0.121 s, median act 0.089 s, max 0.122 s (budget 2 s)
- Full: week 1 0.302 s, median act 0.230 s, max 0.302 s (budget 4 s); mpc_fab3sell on the same check: median 0.232 s, max 0.340 s.
The rule adds no measurable CPU.

## Verdict

**imit_room is a small, consistent, cheap gain: +0.004 to +0.013 RSS on Full** (positive on dev 20, devpick 6 and a
fresh seed of 12; 90% intervals all above 0), no harm on Small, no CPU cost. On these numbers it is a safe add-on to the
final candidate (`agents/mpc_imit_room`). imit_target is about the same on Full, a little noisier. Neither comes
close to +0.05.
The bigger structural difference, fabs running in long on/off blocks with almost no wafer stock, depends on when
demand and disruptions come. We found no observable rule for its timing, so it is not imitated.

Surprising: the gain comes from *not* doing something (overfilling grids and spilling fuel), not from copying a
target level. The "target" cap adds nothing over plain "room".

Assumptions written down (nobody could be asked): "both rules on" was treated as identical to "target" (it is, by
the code); the fresh seed was a runner-picked random root (1461252710); the Full dev 20 baseline was rerun with the
fixed runner (0.8099, equal to the team's absolute mpc_fab3sell number).
