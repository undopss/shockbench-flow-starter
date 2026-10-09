# Agent optimization ideas and evidence

This is an idea archive, not a claim that every item is implemented or beneficial. The current working branch when this
archive was created is `task-26-imit`. Keep the experiment branch and official score separate from this document.

For the most recent line-by-line source review, see [`PULSE_V2_DETAILED_AUDIT.md`](PULSE_V2_DETAILED_AUDIT.md).

## Current evidence snapshot

- `mpc_fab3sell`: Full dev 20 RSS 0.8099; verified base used by tasks 20, 26, and 28.
- `mpc_imit_room`: Full dev 20 RSS 0.8228 (+0.0128, paired 90% interval [+0.0023, +0.0295]); independent Full seed
  of 12: 0.8096 vs 0.8040 (+0.0056, interval [+0.0013, +0.0100]); Full devpick 6: +0.0035. This is a confirmed,
  modest development-set improvement, not a hidden competition score.
- `mpc_pulse_v2`: local paired episode-cost reductions are recorded in its experiment report. The local cached reference
  generator/hash does not match this checkout, so these runs do not establish a valid RSS or a ranking against
  `mpc_imit_room`.
- `mpc_fb` / task 25: exposed a measured fuel-LP prediction error, but candidate results need matched-baseline
  confirmation before treating any feedback variant as an improvement.

## Highest-priority problems to investigate

### A. Fuel LP can count phantom fuel

**Problem:** its `off_sf` shortfall variable can fill a modeled fuel deficit in the stock balance. Task 25's replay found
weeks where the LP's predicted stock equaled real stock plus large shortfall slack; it then planned less replenishment
than the actual grid needed. `mpc_imit_room` still has the unconstrained slack.

**Improvement:** derive fuel use from the simulator transition, including rationing based on last week's grid stock,
fuel available after arrivals, and the grid's actual load. Test a physically bounded shortfall separately from an exact
or near-exact one-week transition model. Measure stock prediction error and fab/home outcomes before selecting by RSS.

**Status:** bug measured; proposed correction not yet confirmed against the correctly parameterized baseline.

### B. Planners do not share one final schedule

**Problem:** the energy LP, chip LP, pulse planner, and `imit_room` post-plan clamp run in sequence. A later planner can
overwrite or clip a flow without updating the other plans. For example, `imit_room` uses a fixed 0.9 burn estimate;
the energy LP's planned arrival schedule can then differ from the submitted action.

**Improvement:** first record each stage's requested and final flow and calculate prediction-versus-execution error.
Then either put grid storage/transfer constraints into the LPs or update the shared schedule after each final action
change. Keep a last-step safety clamp, but make the preceding planner aware of its constraint.

**Status:** code-structure issue confirmed; score impact not isolated.

### C. Fab power is the largest measured remaining policy opportunity

**Problem:** on Full, homes are served before industrial loads. Fab energy is divided according to wafer-limited
requested draw. The fuel planner can improve grid supply while the chip planner still does not place the right wafers
at the right fabs, or predicts a different fab power split from the simulator.

**Improvement:** couple fuel release and wafer positioning to the expected value of chips that can actually be sold.
Use the exact simulator power allocation in the weekly forecast. Evaluate partial-power weeks and include the cost of
extra home shedding caused by pulses.

**Evidence:** task 28's Full audit put fab power and pulse-added shedding above the small cost terms; task 21 bounded
standalone chip-side improvements as modest on its six-episode probe. Treat the numeric ceilings as sample-specific.

### D. Pulse v2 queue forecasts omit parts of the future path

**Problem:** in-flight cargo can be forecast directly to its final destination by adding remaining travel times. This
does not model another queue at a later chokepoint. Queued cargo forecasts use current throughput/edge capacity and
do not include future new arrivals from the plan in the same queue state.

**Improvement:** make a time-expanded queue forecast by chokepoint and commodity, including arrivals, release capacity,
remaining route legs, and planned shipments. Validate predicted arrival week and quantity against full simulator
replays before testing score.

**Status:** implementation gap confirmed by inspection; v2's overall RSS is unverified.

### E. Production variables are partly forecasts disguised as controls

**Problem:** chip LP contains fab-start and OSAT-packaging decisions, while the submitted action controls transport.
The simulator starts production and packages automatically from available stock, capacity, and realized energy.

**Improvement:** represent fab and OSAT outputs as consequences of a forecasted simulator transition, or explicitly
account for the limits on indirectly steering them through wafer/raw-chip inventory. Compare predicted starts and
packaging with actual values week by week.

**Status:** model/control mismatch confirmed; measured score ceiling is small for some OSAT mismatches, so prioritize
fab-power effects first.

### F. Planning horizons and uncertainty need calibration

The energy, pulse, and chip planners use different horizons (12, 8, and 24 weeks in the checked configurations). Check
whether long transit/production paths fall beyond one planner's horizon and whether terminal values compensate for
that truncation. The demand forecast directly informs only part of the episode; do not assume a larger horizon helps
without a paired experiment.

**Improvement:** harmonize only the horizons that demonstrably miss valuable arrivals or production, add a terminal
value based on downstream demand and salvage, then run paired Full tests.

**Status:** plausible modeling risk; contribution not isolated.

## The original Pulse v2 eleven

Numbers below are mean cost savings from the first six local Full episodes, not RSS. The two combined-candidate batches
had six episodes each. Cached reference generator/hash mismatch prevents treating them as official-equivalent score
results. Positive one-at-a-time effects did not always combine.

| # | Idea | Local screen | Decision in v2 experiment | Follow-up |
|---|---|---:|---|---|
| 1 | Forecast grid power and bound planned fab starts by it | +$84.1B | Kept | Validate against the exact simulator split among wafer-limited fabs. |
| 2 | Track terminal and grid fuel inventories separately | +$46.9B | Kept | Reconcile with the final terminal-transfer schedule. |
| 3 | Search multi-week terminal-to-grid pulses | -$153.8B | Rejected | Do not revive without a materially different objective/model. |
| 4 | Price energy by downstream fab value | -$17.6B | Rejected | Earlier direct value shaping regressed; combine only with a physical power model. |
| 5 | Steer wafer supply toward highest chip value per energy | -$65.9B | Rejected | Revisit only with sellable demand and exact power-allocation coupling. |
| 6 | Force one-week fab starts and OSAT packaging to physical targets | +$21.0B | Removed from combined agent | Standalone gain mostly disappeared when combined. |
| 7 | Bound fuel shortfall slack by one week's burn | +$17.6B | Removed from combined agent | Important model fix candidate, but re-test against a correct baseline. |
| 8 | Add a special priority credit to US leading-edge fabs | +$16.2B | Removed from combined agent | Marginal combined gain was small and unstable. |
| 9 | Forecast FIFO release of chokepoint queue cargo | +$112.8B | Kept | Fix multi-chokepoint and planned-arrival omissions; validate RSS. |
| 10 | Include remaining episode time, tariffs, and full recent-start window in LP costs | +$53.8B | Kept | Check consistency of economic units and terminal value. |
| 11 | Add extra solver deadlines/fallback checks | $0 | Rejected as a score change | Keep normal reliability checks; no measured gain from extra guards. |

Four retained changes saved a mean $238.2B per episode in the first local batch and $151.4B in a separate six-episode
batch, but this is a cost-based local result with the reference mismatch stated above—not a valid RSS comparison to
the newer Full candidate.

## Mentor notes translated into experiments

1. **Seeds and evaluation quality:** use one episode for smoke/crash checks only. Choose with paired episodes, cover all
   four harm levels, record entropy/root and episode IDs, and keep a fresh Full seed untouched until the candidate is
   frozen. If an interval is inconclusive, increase the predeclared paired sample; do not keep rerunning until a good
   result appears. This improves decisions, not RSS directly.
2. **Developer/validation sets:** fit rules and parameters on independent generated roots; confirm on fixed Full dev;
   use a separate fresh Full root as a final overfit guard. Never split weeks from the same episode across train/test.
3. **Rules vs hardcoding:** each rule should target a measured failure, depend on observable state, explain its causal
   path, and survive held-out roots and harm levels. Avoid episode IDs, hidden generator state, and unexplained constants.
4. **Parameter calibration:** search a small, declared set of high-impact MPC parameters on training roots; log every
   trial and use paired RSS. Avoid wide search on the public dev set.
5. **Time-series model / imitation:** generate offline datasets from independent simulator roots. Start with simple
   persistence and linear/MLP predictors for decision-relevant quantities (fuel burn, fab energy, shortages). Compare
   against current MPC and estimate the counterfactual score ceiling before integrating a model.
6. **Hugging Face / zero-shot / GPU:** defer large or downloaded models until a small model demonstrates held-out
   value. The competition agent must work offline and on CPU; GPUs can speed training but do not improve inference
   availability on the scorer.
7. **“MPC training time”:** MPC is an online optimizer, not necessarily a trained neural policy. Track per-week solve
   time and setup cost separately from offline dataset/model training; neither should be confused with episode score.

Runnable follow-ups derived from these notes are in [`../CLOUD_TASKS.md`](../CLOUD_TASKS.md), tasks 29–32.

## Ideas tested and deprioritized

- Manual tanker queue overrides/holds: task 28 estimated essentially no Full gain; do not make this the next major task.
- Climate-based future closure hedging: task 27 did not show a Full dev 20 gain. `closure_end` was unobserved in the
  scored standard regime.
- Larger model or remote zero-shot inference: no measured value, incompatible with the offline CPU-only evaluation
  unless converted to a compact, bundled model.
- Extra fallback guards as a score lever: task 28 saw no missed fallbacks in the probe; maintain safety but prioritize
  physical model accuracy and fab energy planning.
