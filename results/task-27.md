Status: done. Verdict: dead end (no build for the final)

# Task 27: know the climate (disruption statistics) + `closure_end`

Baseline: **`clim_off`** = `agents/mpc_clim` with mpc_fab3sell's params.json (same code as mpc_fab3sell, climate options off).
I did not use plain `{"agent": "agents/mpc_fab3sell"}` as the reference: `outputs/variants.py` drops every
`params.json` when it copies an agent, so that entry plays mpc_fab3sell **without** its params (kappa_lp, pp_direct,
pp_split, sell_end): Full 6 0.822 vs 0.850, Small 20 0.750 vs 0.763. **This affects every round that used the plain
baseline.** Tables re-based on clim_off with `outputs/task-27/rebase.py`.

## (a) `closure_end`: never shown in the scored regime
The scored regime is `standard` (gym registration default) and its `theta.chi` is False (`information/theta.py`:
"chi of informed and standard: ... false, closure_end null"). Checked: in 5 Full + 5 Small gym episodes with
428 + 232 closed chokepoint-weeks, `closure_end.*.observed` is 0 every time (`outputs/task-27/ce_probe.py`).
So no agent can use it. Nothing to build.

## (b) Statistics (300 own-root episodes per task, root 27027, from omega/marks)
`outputs/task-27/climate.py`, `climate_report.py` → `climate_full_300.txt`, `climate_small_300.txt`; `hazard.py` → `hazard.txt`
and `agents/mpc_clim/climate.json`.
- **Energy sources never lose supply** (0% of weeks below 0.9 × normal, all 10 sources). Grid G_bar drops (energy shocks):
  ~2% of weeks, median 3 weeks, depth ~30%.
- **Chokepoints (Full)**: closed share of weeks Taiwan 17%, Malacca 13%, Hormuz 9%, Suez 9%; Cape/Panama/Turkish ~0.5%
  (weather only, reopen within 2 weeks ~80%).
- **Open straits almost never close**: P(closed within 12 weeks | open now) ≈ 1-2%.
- **Closed straits**: just closed (d = 1 week) → open again within 4 weeks 43-59% (Hormuz/Malacca/Suez/Taiwan); after
  3+ weeks closed only 5-30% within 12 weeks (militarised closures: median 37 weeks). Weather closures: ~1 week.
- Edge cuts: sanctions last for the whole episode (median duration 120 weeks); port strikes/piracy are short.
- Events per Full episode (acting): sanctions 33, tariffs 14, energy shocks 4.7, weather closures 2.9, strikes 2.8,
  militarised closures 1.7, material outages 3.2.

## What was built: `agents/mpc_clim` (copy of mpc_fab3sell, all new options off by default)
- `clim_reopen`: a closed chokepoint's future lane capacity in the energy LP = P(reopened by then | closed for d weeks).
- `clim_derate`: an open chokepoint's future lane capacity × P(still open then).
- `clim_safety`: per pool, extra safety weeks = clim_safety × 10 × (import-capacity share passing a chokepoint, weighted
  by its long-run closed share). At 1.0: e.g. a grid importing all through Malacca gets +1.3 weeks.
- `climate.json` holds only statistics from my own root (nothing from the hidden set).

## Results (exactly as printed, rebased on clim_off)

Full 6, root 0, devpick:2,2,1,1:
```
full, entropy 0, 6 episodes (devpick:2,2,1,1); diff = variant - clim_off, 90% paired interval
variant                      RSS     L1     L2     L3     L4     diff  interval               better%
mpc_fab3sell              0.8219  0.828  0.836  0.795  0.786  -0.0281  [-0.0372, -0.0178]     0.0%  <-- worse
clim_off                  0.8500  0.843  0.869  0.838  0.845  +0.0000  [+0.0000, +0.0000]     nan%
reopen                    0.8481  0.840  0.868  0.838  0.841  -0.0019  [-0.0039, -0.0002]     0.0%  <-- worse
reopen_derate             0.8482  0.836  0.872  0.841  0.841  -0.0018  [-0.0027, -0.0007]     0.0%  <-- worse
risk_safety               0.8557  0.845  0.876  0.857  0.828  +0.0057  [+0.0047, +0.0066]   100.0%  <-- better
all_clim                  0.8552  0.842  0.878  0.856  0.831  +0.0052  [+0.0045, +0.0061]   100.0%  <-- better
sw5                       0.8584  0.845  0.873  0.872  0.838  +0.0084  [+0.0037, +0.0138]   100.0%  <-- better
sw1                       0.8268  0.835  0.837  0.792  0.831  -0.0231  [-0.0433, -0.0003]     0.0%  <-- worse
```
Small random 20, root 1604362749:
```
small, entropy 1604362749, 20 episodes (20); diff = variant - clim_off, 90% paired interval
variant                      RSS     L1     L2     L3     L4     diff  interval               better%
mpc_fab3sell              0.7504  0.734  0.860  0.647  0.634  -0.0121  [-0.0189, -0.0053]     0.1%  <-- worse
clim_off                  0.7626  0.751  0.859  0.657  0.688  +0.0000  [+0.0000, +0.0000]     nan%
reopen                    0.7646  0.750  0.867  0.654  0.697  +0.0020  [+0.0001, +0.0041]    95.9%  <-- better
reopen_derate             0.7671  0.755  0.867  0.654  0.697  +0.0045  [+0.0013, +0.0077]    99.6%  <-- better
risk_safety               0.7700  0.755  0.876  0.650  0.722  +0.0074  [+0.0032, +0.0120]   100.0%  <-- better
all_clim                  0.7685  0.756  0.870  0.648  0.724  +0.0059  [+0.0015, +0.0106]    99.0%  <-- better
sw5                       0.7641  0.752  0.864  0.645  0.713  +0.0015  [-0.0031, +0.0062]    67.7%
sw1                       0.7607  0.749  0.867  0.632  0.701  -0.0019  [-0.0109, +0.0068]    36.8%
```
Full dev 20, root 0 (decision):
```
full, entropy 0, 20 episodes; diff = variant - clim_off, 90% paired interval
variant                      RSS     L1     L2     L3     L4     diff  interval               better%  fallb
clim_off                  0.8099  0.800  0.854  0.790  0.739  +0.0000  [+0.0000, +0.0000]     nan%      0
risk_safety               0.8072  0.791  0.857  0.797  0.738  -0.0027  [-0.0133, +0.0045]    32.5%      0
all_clim                  0.8089  0.794  0.858  0.796  0.738  -0.0010  [-0.0082, +0.0047]    39.3%      0
sw5                       0.8061  0.790  0.853  0.799  0.738  -0.0039  [-0.0150, +0.0050]    30.4%      0
```

## Verdict
- (a) `closure_end`: impossible (never shown in the scored regime).
- (b) climate-based hedging: **no gain on Full dev 20** (−0.001 to −0.004, intervals hold 0); the +0.006 on Full 6 /
  Small 20 was noise or episode-specific. Expected: task 15 put perfect foresight of *all* in-episode events at 0.127 T
  (≈ +0.04 RSS), and statistics recover only a small part of that. Disruptions are either short (weather, strikes,
  energy shocks: 1-3 weeks) or effectively permanent (sanctions, militarised closures), so "the present persists" is
  already almost the right forecast, and sources never fail.
- Skipped (my call): Small dev 20 and the fresh Full seed 12, since nothing passed Full dev 20; `sbf check` on Full
  (the code isn't meant for the final). `sbf check --task=small` with every climate option on passed: max 0.200 s,
  median 0.136 s per week.

## Files
`agents/mpc_clim/` (+ `climate.json`), `outputs/task-27/` (scripts, stats, `variants27*.json`, `run_*.txt`,
`rounds/*_results.json`).
