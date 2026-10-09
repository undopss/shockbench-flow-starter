# Detailed audit: latest experimental MPC Pulse v2

## Scope and confidence

I treated `agents/mpc_pulse_v2` as the latest implementation to inspect and compared its architecture with the
verified `agents/mpc_imit_room` candidate and the simulator under `agents/scen/sbfv/dynamics/`. The code audit is
static; I did not change the agent or run a new score experiment.

`mpc_imit_room` remains the best *validated RSS result in this checkout*: Full dev 20 RSS 0.8228 (+0.0128 vs
`mpc_fab3sell`) and fresh Full 12 +0.0056, with zero fallbacks in the reported runs. Pulse v2's experiment report
shows promising local cost reductions, but its cached generator/reference hashes do not match the current package.
Those results cannot rank it against `mpc_imit_room` or establish its RSS. Before promotion, rebuild/match references
and run paired Full RSS tests.

## Main conclusion

Pulse v2 adds useful physical forecasts, but the agent still plans with several different approximate worlds:

1. the fuel LP plans source shipments and, optionally, terminal transfers;
2. the power forecast partly uses that schedule and partly substitutes a pulse heuristic;
3. the chip LP treats fab starts and OSAT packaging as decision variables and relies on estimated power;
4. the final action can be clipped by the simulator's shared-edge/fleet constraints.

An error in any layer changes the effective future stocks used by the next layer. The highest-priority code defect I
found is the chip LP's missing aggregate constraints for shared downstream route edges. The highest-priority model
defect inherited from the earlier MPC is fuel shortfall slack that can create phantom stock in the LP. The largest
remaining measured economic opportunity is still getting the right fabs powered without causing excess home shedding.

## Findings ranked by expected impact

### P0 — Results do not yet prove v2 is better

The experiment report has only two six-scenario local Full batches and explicitly says the cached references have
different generator IDs/omega hashes. Cost savings on those scenarios are useful for screening individual code ideas,
but not a comparable RSS estimate, not a hidden-set estimate, and not evidence that the combined agent beats
`mpc_imit_room`.

**Improvement:** reproduce the selected features with references built from the current package; compare v2, its
original baseline, and `mpc_imit_room` on the same Full episodes, with agent parameters loaded. Use Full dev 20 and a
separate fresh Full root after a Full devpick screen. Report paired aggregate/per-harm RSS, episode costs, fallbacks,
and CPU. Keep v2 as experimental until that is done.

### P1 — Chip route LP can overbook shared downstream edges

In `chips.py`, each slot is individually limited by the minimum capacity along its route, but the aggregate capacity
constraint groups slots only by `ls["first"]`. Two routes with different first edges can therefore each consume the
full capacity of a common later edge in the LP. Full contains concrete chip-route examples: two `chip_le_raw` routes
from different Korean fabs to OSAT Vietnam share the Taiwan-to-Vietnam segment; their first edges differ. Static Full
route inspection found 29 eligible `(commodity, shared edge)` groups with more than one first edge.

The simulator clips requests against shared edge capacity. The LP can consequently forecast more wafer/raw-chip
arrival than the simulator executes, then make downstream plans from phantom supply. This also explains a plausible
part of the measured chip LP forecast/execution gap (task 21: expected pi-weighted fill 56%, observed 53%), although
that report did not isolate this constraint as the cause.

**Improvement:** build aggregate rows for every `(edge, week)` used by all LP slots, not only the first edge. Each
route's individual upper bound should still respect the minimum remaining edge capacity, while the shared row limits
the sum of every compatible route using that edge. Include already released/occupied capacity and any relevant shared
fleet or cross-planner use. Add a diagnostic comparing requested to executed quantity by edge and lane. First test
chip-only routing on paired Full episodes; do not assume that the task-21 ceiling is recoverable by this fix.

Code: [`chips.py`](../agents/mpc_pulse_v2/chips.py), route capacity around `lead`/`hi` and the “each first edge” rows
near the final `A_ub` construction.

### P1 — Fuel LP has an unbounded phantom-shortfall variable

The fuel LP fixes planned burn to `share × G_bar` and includes `off_sf` in the inventory balance with a sign that
lets the optimizer compensate for stock it did not receive. `off_sf` has a cost but no physical upper bound. Task 25
measured this behavior: predicted pool stock could equal real stock plus a large shortfall quantity, after which the
planner under-shipped the grid. Pulse v2 retains the same mechanism (`agent.py`, `off_sf` variable and pool balance).

**Improvement:** model actual fuel consumption in a one-week transition first: rationing uses last week's grid stock;
available fuel is capped by stock after arrivals; fuel burn depends on the realized grid load. Bound unmet-burn slack
by a physically justified amount, and never carry it forward as real stock. Compare prediction error by grid/fuel/week
before evaluating RSS. The task-25 `fb_sf_cap` switch is a candidate ablation, not a proven fix: rerun it against a
properly parameterized baseline because the old results had runner/parameter caveats.

Code: [`agent.py`](../agents/mpc_pulse_v2/agent.py), `off_sf` setup and the pool stock balance around the LP rows.

### P1 — Future power uses a different terminal-transfer schedule than the fuel LP

When `separate_fuel` is active, the energy LP optimizes `off_transfer` for terminal-to-grid moves, then emits the
current week's transfer in `flows`. It saves only the source-slot part of the solution to `energy_schedule`; the
future `off_transfer` variables are not saved. `power_schedule()` therefore forecasts future terminal transfers with
a simple pulse/availability rule, not with the LP solution. The chip LP can be optimized against a power plan the
energy LP itself did not choose.

There is a second failure mode: `energy_schedule` is not cleared at the start of each week. If `_plan()` returns
`None` or raises, `fuel_inputs()` may reuse last week's schedule. If there is no schedule yet, it repeats the current
fallback flow for every future departure offset, which is not a valid future schedule either.

**Improvement:** return a structured energy plan containing source dispatches, terminal inventory, terminal transfers,
and arrivals. Reset it to `None` before every solve. If the solve fails, construct an explicit conservative fallback
forecast instead of reusing stale values or repeating this week's flow. Feed the exact final first-week action into
the power model and re-simulate after any post-processing.

Code: [`agent.py`](../agents/mpc_pulse_v2/agent.py), transfer variable layout and `energy_schedule` assignment;
[`forecast.py`](../agents/mpc_pulse_v2/forecast.py), `fuel_inputs()` and `power_schedule()`.

### P1 — Power forecast does not reproduce fab-level energy allocation

`grid_step()` estimates total grid power after fuel availability and home load. `power_schedule()` turns that into
leftover headroom; `chips.py` then divides it across fabs using nominal draw. The simulator instead requests fab power
using wafer-limited draw (`e × p_hat / R`) and splits the leftover pro rata by those requests. Thus the split changes
with each fab's actual wafer stock, restoration, and capacity. The model can give a high-value fab too little power in
its forecast, or plan wafer starts at a fab whose actual share will be smaller.

**Improvement:** calculate per-fab requested draw from predicted wafer availability and current observed restoration;
apply the exact homes-first allocation; cap predicted fab starts at the resulting power and wafer limits. Where the
LP's continuous start variables make that relationship nonlinear, use a small fixed-point iteration or a conservative
piecewise-linear approximation. Evaluate actual versus predicted starts and energy on partial-power weeks.

Code: [`forecast.py`](../agents/mpc_pulse_v2/forecast.py), `grid_step()`/`power_schedule()`;
[`chips.py`](../agents/mpc_pulse_v2/chips.py), `power` to `hi[off_f]` bounds.

### P1 — Queue forecast skips later chokepoints and planned queue competition

For a shipment already in the pipeline, `route_arrivals()` adds the travel time of every remaining route edge and
projects it directly to the final destination. If the remaining route passes another chokepoint, that future queue,
its kappa, and possible closure are skipped. For an existing queue, the forecast shares current edge/kappa capacity
among observed queue lots, but does not insert planned incoming shipments or current pipeline arrivals into those
same weekly queue capacities. It also holds today's open state/capacity constant across the forecast: closed now means
no future release in the forecast; open now means no future closure.

The result can be either optimistic (cargo reaches a factory before a second queue delays it) or pessimistic (a
currently closed route is treated as closed for the entire horizon). New source dispatches are not propagated through
the same time-expanded queue state.

**Improvement:** model cohorts at each chokepoint and week. Add observed queued lots, pipeline arrivals, and planned
dispatches; release FIFO subject to per-edge and pool throughput; move each released cohort to the next edge, where it
may join another queue. Use known current restrictions exactly and scenario/expected capacities only where the future
is genuinely unknown. Compare predicted arrival week/quantity with simulator logs before scoring.

Code: [`forecast.py`](../agents/mpc_pulse_v2/forecast.py), `route_arrivals()`.

### P2 — The chip LP treats automatic production as a controllable plan

`chips.py` has free variables for fab starts and OSAT packaging. The action sent to the simulator contains flows; it
does not command those starts/packaging directly. Fabs start according to stock, effective capacity, and actual power;
OSAT output follows automatic throughput and pro-rata package rules. The planner can therefore choose production
quantities that its flow action cannot guarantee.

**Improvement:** keep the LP focused on controllable transport. Predict starts/packaging by applying simulator
transitions to each candidate inventory/power state, or iteratively reconcile LP starts with automatic production.
Do not optimize a free production variable unless its implementation can be enforced through inventory/power decisions.
Log predicted versus actual production and packaging; task 28 found the OSAT pro-rata discrepancy small, so the fab
power mismatch is the higher-value target.

### P2 — The observed-start cap can lag after power recovers

With `fab_cap_mode="observed"`, a fab with wafer inventory and low recent starts is capped using recent WIP starts
plus a gradual growth margin. This usefully avoids planning full production during prolonged power starvation. But
after the fuel/pulse plan restores power, recent starts may still be low, so the chip LP may under-position wafer/raw
materials for a recovering fab. Conversely, the cap may be wrong after a fab-capacity shock.

**Improvement:** compare the observed-start cap with a power-conditioned cap from the same week's predicted fab energy.
Make the recovery bound depend on current energy and effective capacity, not only recent starts. Test separately on
weeks where power availability rises after a constrained period; report start prediction error and RSS by harm level.

### P2 — The horizon and terminal value are not aligned across subsystems

The checked configuration uses an energy horizon of 12 weeks, a pulse horizon of 8, and a chip horizon of 24. A
shipment can affect fuel, fab starts, WIP, OSAT stock, and sink sales after different delays. Each LP also has its own
terminal stock/shortage penalty. This creates boundary effects: a move can look valuable in one LP but fall beyond the
other LP's horizon or be valued differently at the horizon edge.

**Improvement:** trace representative end-to-end routes and identify arrivals/production/sales that fall beyond each
horizon. Add a calibrated terminal value for in-transit stock and WIP based on expected downstream demand and actual
salvage. Extend only the limiting horizon and measure CPU/score; do not increase all horizons by default.

### P2 — Future capacity, tariff, and closure inputs are mostly frozen at current values

The LP uses current edge capacity/open state across future weeks, while pending prohibitions are handled separately.
Future unsignalled closures/capacity changes cannot be known exactly. This creates route overconfidence when an open
lane later closes and route over-rejection when a closed lane reopens. However, task 27's climate-statistics options
did not improve Full dev 20, and `closure_end` was unobserved in the scored standard regime.

**Improvement:** use deterministic information that is actually announced (pending prohibitions and known effective
weeks); evaluate probabilistic capacity forecasts only if a counterfactual ceiling supports them. Do not revive broad
climate derating without new evidence.

### P3 — Error handling can turn a forecast bug into a failed action

`act()` delegates directly to `_act()`. The power forecast call is outside the local exception guards used for the LP
solves and assumes `_setup()` built all required arrays. If setup was partial or malformed observations trigger a
forecast error, the agent may raise rather than return its already-computed fallback flows. Solver failures otherwise
fall back silently, making it hard to see which planner is actually controlling a week.

**Improvement:** initialize every plan/schedule field explicitly; guard power forecasting; always preserve a valid
fallback action. Record lightweight counters for energy failure, power-forecast failure, chip failure/skip, action
clipping, and final forecast error. Keep metrics silent in normal scoring output and verify no CPU regression.

### P3 — Compute time guard may skip the most valuable planner

The chip LP runs only if elapsed process CPU is below `chip_time_limit × 0.4` (0.8 s under the default 2.0 s). Power
and fuel planning happen first. V2's local report saw peak action CPU below 0.7 s in its sampled runs, so there is no
evidence this caused those losses; more complex weeks may cross the early threshold.

**Improvement:** measure skip frequency and score impact by episode/week. If skips occur, reserve a hard budget for the
chip LP or simplify power forecasting. Do not remove safeguards based on median time alone.

## Lower-value or rejected directions

- Tanker `override`/`hold` control: task 28 estimated approximately zero Full ceiling; prioritize source-side and
  physical queue prediction instead.
- Broad learned closure-risk derating: task 27 did not improve Full dev 20; known warnings were weak and reopening
  announcements were unavailable in the scored regime.
- More generic tariff/holding/disposal cost tuning: task 28 measured these gaps below the major power/chip effects.
- Large zero-shot/Hugging Face model: no held-out value shown; final inference must run offline on CPU. First test a
  small predictor as an MPC correction on generated episodes.

## Suggested implementation order

1. **Add diagnostics only:** on matched simulator episodes, log planned/actual edge flows, source/grid/terminal stock,
   `off_sf`, predicted/actual burn, fab energy/starts, queues, and falls back/skips. This localizes which gaps are
   active in Full.
2. **Fix shared downstream edge capacity rows in the chip LP.** It is a specific feasible-model defect with direct
   effects on executed flows. Compare on paired Full; preserve a pre-change baseline.
3. **Correct fuel inventory/burn accounting and schedule state.** Remove phantom stock; save/reset the full energy plan;
   check one-week simulation parity.
4. **Make power/fab forecasts reflect wafer-limited simulator allocation** and let the chip plan use that exact forecast.
5. **Make queue prediction time-expanded end-to-end**, then calibrate horizon/terminal values only where logs show
   material error.
6. Re-run matched RSS gates against `mpc_imit_room` and `mpc_fab3sell`, all harm levels, a fresh Full seed, and Small
   no-harm check. Promote only a measured gain with no fallback/CPU regressions.

## Source files inspected

- `agents/mpc_pulse_v2/agent.py`, `chips.py`, `forecast.py`, and `fallback.py`.
- `agents/mpc_imit_room/agent.py`, `chips.py`, and its `params.json`.
- Simulator behavior in `agents/scen/sbfv/dynamics/sim.py`, `production.py`, `clip.py`, and `chokepoint.py`.
- `results/task-21.md`, `results/task-26.md`, and branch report `origin/task-28-rulelawyer:results/task-28.md`.
