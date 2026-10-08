# Cloud tasks

You are a Claude cloud session working for the Mantis team. The person who started you said **"you are task N"**.
Do task N from the list below, and only that task. Everything you need is in this repo (branch `cloud`).

## Before you start

1. Read `CONTEXT.md` (rules, what we know, how the game works). The hard rules there apply: never guess numbers,
   never upload to Codabench, never push to `main`.
2. `uv sync`
3. **Unpack the home server's evaluation cache** (saves 10-20 minutes per Full run; covers the Full and Small dev
   episodes and our earlier seeds): `mkdir -p ~/.cache && tar xzf cache/sbf-cache.tgz -C ~/.cache`.
   A new random seed still builds its own references; that is expected.
4. The current best agent is `agents/mpc_chip`. Its options are in `PARAMS` at the top of `agents/mpc_chip/agent.py` and
   can be overridden by a `params.json` next to it. The test runner uses that to make variants without copying code.

## How to test (the same for every task)

Runner: `uv run python outputs/variants.py <small|full> <entropy|random> <episodes> <variants.json> 4`

- The first entry of `variants.json` is the **baseline** (always `{"agent": "agents/mpc_chip"}` unless the task says
  otherwise). Every other entry is compared with it **on the same episodes**, with a 90% paired interval.
- Stage 1 (filter): `small random 20`. Stage 2: `full 0 devpick:2,2,1,1` (6 Full dev episodes, all four harm levels).
  With the cache from step 3 the Full dev episodes need no reference computing.
- An idea is promising if its Full stage interval is above 0 (the runner prints `<-- better`).
- **The bar:** we only care about ideas that can plausibly add **+0.05 RSS on Full**. Don't spend time on small tuning.

## Never end your turn while a test runs

A routine session is closed as soon as your turn ends, and **every background job dies with it**. So never "launch in
the background and report later": wait for the runner in the foreground (e.g. a `while pgrep -f variants.py; do sleep
60; done` loop with a long timeout, repeated as needed) until the results are written and pushed.

## Show up on the team's page right away

The team watches a page that reads your branch from GitHub every 2 minutes. So **before any long work**:
create the branch `task-N-<short-name>` from `cloud`, write `results/task-N.md` with a first line
`Status: started` and one sentence on your plan, commit and push. Then **push an update at every milestone**
(the status line + what you learned so far; e.g. `Status: building references`, `Status: running Full test`,
`Status: done`). Keep it short.

## How to hand back

1. Work on the branch `task-N-<short-name>` from `cloud` (created at the start, see above).
2. New agent code goes in a **new folder** `agents/<short_name>/` (start from a copy of `agents/mpc_chip`), or as a new
   option in `agents/mpc_chip` that is **off by default** (so the baseline doesn't change).
3. Write `results/task-N.md` (in Ukrainian or English, short): what you built, the runner tables exactly as printed
   (with the seed), your verdict, and anything surprising.
4. `git add -f` your variants JSON files and the runners' `results.json` files, commit, push, open a PR into `cloud`.
5. In your final chat message: the result tables + one-line verdict. The user will paste them to the main Claude.
6. If your code is meant for the final: `uv run sbf check <agent> --task=small` and `--task=full` must pass. Report the
   max and median CPU seconds per week (budget: Small 2 s, Full 4 s; the scoring server is at least ~5x faster than
   the home server, unknown vs your machine).

## Tasks

### 1. RUN: pulse and fab-capacity combos on Small
`variants.json`:
```json
{"mpc_chip": {"agent": "agents/mpc_chip"},
 "pulse_twkr_15": {"agent": "agents/mpc_chip", "params": {"pulse_weeks": 1.5, "pulse_grids": ["grid_tw","grid_kr"]}},
 "pulse_auto": {"agent": "agents/mpc_chip", "params": {"pulse_weeks": 1.5, "pulse_grids": "auto"}},
 "pulse_auto_obs": {"agent": "agents/mpc_chip", "params": {"pulse_weeks": 1.5, "pulse_grids": "auto", "fab_cap_mode": "observed"}},
 "fabcap_observed": {"agent": "agents/mpc_chip", "params": {"fab_cap_mode": "observed"}}}
```
Run `small random 20`, then the same file on `full 0 devpick:2,2,1,1`.

### 2. RUN: pulses at Japan and SE Asia on Full
On Full, Taiwan is fine but Japan and SE Asia shed homes 96-101 of 104 weeks and their fabs run at ~1%.
```json
{"mpc_chip": {"agent": "agents/mpc_chip"},
 "pulse_twkrjpsea_15": {"agent": "agents/mpc_chip", "params": {"pulse_weeks": 1.5, "pulse_grids": ["grid_tw","grid_kr","grid_jp","grid_sea"]}},
 "pulse_jpsea_15": {"agent": "agents/mpc_chip", "params": {"pulse_weeks": 1.5, "pulse_grids": ["grid_jp","grid_sea"]}},
 "pulse_jpsea_25": {"agent": "agents/mpc_chip", "params": {"pulse_weeks": 2.5, "pulse_grids": ["grid_jp","grid_sea"]}}}
```
Run `full 0 devpick:2,2,1,1` only.

### 3. BUILD: planned pulses
Today the pulse is a fixed rule: hold fuel at a terminal until it has `pulse_weeks` of burn, then release everything.
Why it works: grids are `base_first` (homes first, fabs get the leftover); a grid that is always slightly short never
powers its fabs, but a grid that is fully supplied in some weeks powers them in those weeks. Also the rationed fuel's
output is cut by `I_prev / (psi * Ibar)` when last week's stock is under the line.
Build a version that **plans** the release: per grid with fabs, choose which weeks get the batch (e.g. a small MILP with
`scipy.optimize.milp`, or a rule that releases exactly enough to keep the grid stock at/above `psi * Ibar` and full
output in alternate weeks), valuing fab power at the chips it makes (leading-edge ~50k USD per chip, e ≈ 0.002 energy
per wafer). Read `shockbench_flow/dynamics/sim.py` (step 7) for the exact rules. Ceiling: chip shortage is ~95% of
our gap to the clairvoyant plan; the crude rule already gives +0.04 (Small) / +0.08 (Full 6).

### 4. BUILD: tanker priorities at straits
Tanker cargo (LNG, crude) queues at chokepoints (Malacca holds ~3.6k LNG on average on Small) and is released by a
default FIFO, pro-rata rule limited by the chokepoint's tanker throughput (kappa). The action has `override_qty`
(36 slots on Small) and `release_mode` per (chokepoint, tanker commodity): 0 default, 1 override, 2 hold. We never use
them. Build: release LNG bound for grids that feed fabs (TW, KR, JP, SEA on Full) first, and crude/EU-bound cargo after.
Read `shockbench_flow/dynamics/chokepoint.py` (`release`, `_overrides`) and `docs/fields/*.md`. Ceiling: more fuel to
fab grids in the weeks it matters → fab power → chips (same mechanism as the pulse).

### 5. BUILD: why are US fabs still under-fed on Full?
On Full episode 0 with `fab_cap_mode: observed`, US fabs (grid_us has no power cuts) still run at 6-62%, and the chip
LP plans almost no wafers for `fab_us_leading_3` although `mat_jp_wafer` holds 1.78M wafers and the edge cap is
10.6k/week. Find what binds in the chip LP (`agents/mpc_chip/chips.py`): downstream OSAT/route capacity, demand
already covered in the LP's view, lead times vs horizon, a modelling bug... Fix it. Ceiling: US fabs are ~14% of chip
demand; running them fully is worth roughly +0.1 on Full (rough estimate, verify).

### 6. BUILD: calm episodes on Full
Harm level 1 (calm) is 50% of the score. Use `outputs/cost_breakdown.py full 0 dev agents/mpc_chip 4` and look at the
level-1 table: where does `mpc_chip` lose money vs the clairvoyant plan in calm episodes, and is any of it reachable
(remember: the clairvoyant oracle relaxes the homes-first rule, so part of the chip gap is unreachable)? Propose and
implement one fix aimed at level 1, test it, and report the level-1 numbers.

### 7. RUN: fresh-seed Full check (anti-overfitting)
Everything on Full so far used the 20 official dev episodes. Check the best variants on **new** Full episodes:
use task 1's `variants.json` with `full random 12`. This builds references for a new root (~20-40 min); that's fine.

### 8-10. Reserved for Andrii's ideas
(The main Claude adds them here.)

## Round 2 (2026-10-07 evening): where can mpc_pulse still win on Full?

**For tasks 11-14 the baseline is `agents/mpc_pulse`** (Full dev 0.6751; its gap to clairvoyant ≈ 1.15 T USD/episode,
~88% chip shortage, ~10% power shed). Each task is **measure first, build only if the ceiling is big**:
1. Write a diagnostic script (`outputs/task-N/…py`) that plays `mpc_pulse` exactly as `outputs/cost_breakdown.py` does
   (copy its `episode()`; `traj.records` are `StepRecord`s, see `shockbench_flow/dynamics/state.py`: `lots_started`,
   `energy` per fab, `segment` per grid/fuel, `shed`, `served`, `lost`, `stock`, `disposal`, …) on **Full dev
   `devpick:2,2,1,1`**, then on all 20 dev if it looks promising.
2. Report the **ceiling in USD per episode** (the most this lever could save if done perfectly) and how you computed it.
   +0.05 RSS on Full ≈ 0.17 T USD/episode. **Below ~0.17 T: stop, write the numbers, verdict "too small".**
3. Only above that: build it (new folder `agents/<name>/` copied from `agents/mpc_pulse`, or an off-by-default option)
   and run the funnel vs `agents/mpc_pulse`: `full 0 devpick:2,2,1,1`, then `full 0 dev` if better.

How power reaches fabs (`shockbench_flow/dynamics/production.py: allocate_energy`, `sim.py` ~L330-360): each fuel
segment gives `min(share_k·G-bar·ration, fuel on hand)`; ration = min(1, last week's stock / (psi·I-bar)) for the
rationed fuel. `base_first` grids: homes get `y = min(y-bar, G_av)` first; fabs share what is left **pro rata to their
requested draw `e_f·p-hat_f/R_f`**, p-hat = min(capacity·availability, wafers on hand). A fuel can't cover another
fuel's share. Fab draw is often ~1% of a grid's load, so a 1% fuel shortfall leaves the fabs with nothing.

### 11. MEASURE (+BUILD): steer scarce power to the most valuable fabs
Fabs on one grid split leftover power in proportion to `e·p-hat/R`. We control p-hat only through **wafers on hand**.
Measure per grid-week with leftover power < total draw: the chip value made per power unit at each fab (pi of its chip ×
yield / e, but **only for chips whose sinks actually lose sales** in that episode: use `lost`·pi per product), and how
much more value the same power would make if it went to the best fab(s) (up to their capacity). Sum = ceiling.
If big: starve low-value fabs of wafers on contested grids (chip LP option).

### 12. MEASURE (+BUILD): wasted power and wasted fuel
Count, per fab grid and week: (a) power available to fabs that no fab used because they had no wafers (G_av − y − ΣE
while fabs were wafer-limited), (b) fuel thrown away (disposal at grid/terminal fuel slots above storage, e.g. Japan
LNG overflowing while crude is short), (c) weeks a grid was 0-1% short of full load (fabs got ~nothing for a tiny
shortfall). Convert each into lost chip value (as in 11). Ceiling = (a)+(b)+(c) value. If big: build the fix.

### 13. MEASURE (+BUILD): chips to the most expensive missing demand
Per episode: lost sales by sink and product (units and USD = pi × lost), packaged/raw chips held at OSATs/sinks at the
end and over time, disposal of chips, and chips delivered to sinks that had no shortage that week while another sink of
the same product lost sales. Ceiling = USD of lost sales that chips already in the system (not new production) could
have covered. If big: change the chip LP's routing/priorities.

### 14. MEASURE (+BUILD): a cheaper pulse
The pulse (TW/KR, `pulse_weeks` 1.5) adds power shed. Compare `mpc_pulse` with `agents/mpc_chip` +
`{"fab_cap_mode": "observed"}` (= mpc_pulse without the pulse) per grid: shed USD, chip lots started, fab energy.
Ceiling = the shed the pulse adds (if a smarter pulse kept the same chips with no extra shed) + the chips a pulse at
other grids/timings could add (see task 2: JP/SEA added only ~+0.01). If big: build a pulse that only releases when
the stored fuel covers homes + fabs for the whole pulse week and doesn't starve homes before it.

## Round 3 (2026-10-08 night)

New facts (see CONTEXT.md + results/task-12.md): **`agents/mpc_buffer`** (mpc_pulse + `wafer_buffer` 3 weeks of wafers at
every fab) is the new best: Full dev 20 0.7363 (+0.061 vs mpc_pulse). A homes-first MILP (`outputs/reachable_bound.py`)
shows the oracle's extra fab power at JP/CN/KR is reachable with foresight, so the remaining gap is **foresight and
planning**, not the rules. **Baseline for round 3: `agents/mpc_buffer`.**

### 15. MEASURE (+BUILD): are the early warnings worth something? (Full first)
The GUIDE says the signals are "where an agent can gain". We only ever tested one: chokepoint `warning.score` vs a
closure within 8 weeks (AUC 0.51, `outputs/warnings_study.py`). Never tested: **region** units (14 regions) and the
**dyad** unit (rival pair, e.g. TW–CN conflict → fab/OSAT outages), **`messages.*`** threads (tariff proposals/final
notices, sanction threats, military threats; some are false alarms), **`pending_prohibitions.*`** (announced sanctions
with their start week). Read the ground truth from the episode's omega (see how `outputs/warnings_study.py` and the
package's `disruption/` and `information/` modules do it).
1. Per signal type on **Full** (gym `ShockBench/Full-v0`, ≥100 episodes): base rate of its event, AUC / precision at a
   few thresholds, and **lead time** (weeks between the first useful signal and the event).
2. **Value of information** (the money question): for the event types that predict well, how much does knowing them
   help? E.g. compare the oracle LP with vs without that event class (or run mpc_buffer with the true event injected
   into its plan vs without) on Full devpick:2,2,1,1. Ceiling in USD/episode; bar 0.17 T.
3. Only above the bar: use the signal in `agents/mpc_buffer` (new folder or off-by-default option), funnel vs
   `agents/mpc_buffer`: `small random 20` → `full 0 devpick:2,2,1,1` → `full 0 dev`.

### 16. RUN/BUILD: planned pulses on top of the wafer buffer
Task 3's planner (`agents/mpc_pplan`, options `pulse_plan`, `pp_value`, `fab_cap_mode`) was +0.08 vs mpc_chip but −0.012
vs mpc_pulse on Full dev 20, maybe because its pulses landed on fabs with no wafers (task 12's finding). Port its
`pplan.py` + options into a copy of `agents/mpc_buffer` (`agents/mpc_bufplan/`, off by default = mpc_buffer exactly),
then test `pp_value` 20 / 50 (with the buffer on) vs `agents/mpc_buffer`: `small random 20` → `full 0 devpick:2,2,1,1`
→ `full 0 dev` if better. Also try enabling it for CN/JP/SEA only (task 14: the plain pulse at CN/EU costs −0.15 RSS;
say why if you can).

### 16 (rerun). Planned pulses on the buffer — finish it
The first task-16 session ended its turn while its Small run was in the background, so nothing was tested. The agent is
already built: `git fetch origin task-16-bufplan && git checkout task-16-bufplan` (`agents/mpc_bufplan`, off by default
= mpc_buffer). Use `outputs/task-16/variants16.json` (baseline mpc_buffer; pp20, pp50 on all grids; pp20/pp50 at
CN/JP/SEA only). CN/SEA exist only on Full, so: run the all-grid variants `small random 20` first, and the CN/JP/SEA
ones directly on `full 0 devpick:2,2,1,1`; anything better on Full 6 → `full 0 dev`. Keep pushing to `task-16-bufplan`.
**Wait for every run in the foreground** (see "Never end your turn while a test runs").

### 17. MEASURE: where is mpc_buffer's remaining gap on Full? (do this first, report fast)
`uv run python outputs/cost_breakdown.py full 0 dev agents/mpc_buffer 4` (all 20 Full dev episodes). Then break the
gap to the clairvoyant plan down further so the team knows where the next +0.1 can come from:
1. per cost component and per harm level (the script prints this);
2. chip shortage by product (chip_le / chip_mat) and by sink, and fab lots started per fab vs the oracle's
   (`outputs/oracle_fabs.py full 0 dev 4` gives the oracle's lots per fab; compare with the agent's `detail.lots_started`);
3. shed by grid (agent vs oracle);
4. per episode: which disruption types were active (from omega: closures, sanctions, tariffs, conflicts, fab outages)
   and how the gap correlates with them (is the gap mostly in episodes with event X?).
Write the tables to `results/task-17.md` with a short "where the next 0.1 RSS is" section (≈0.33 T USD/episode).
No building in this task.

## Round 4 (2026-10-08 morning)

New facts: **`agents/mpc_bufplan` with `{"pulse_plan": true, "pp_value": 20}` = Full dev 20 0.7820** (+0.046 vs
mpc_buffer, results/task-16.md). Its planner is off by default, so the baseline for round 4 is that agent **with
those params** in `variants.json`. Warnings are a dead end (results/task-15.md). Where the rest is: results/task-17.md.

### 18. BUILD: let the CN/JP/SEA fabs run (team goal: Full ≈ 0.82-0.84)
Task 17's biggest lever (ceiling ≈ 0.3 T USD/episode ≈ +0.09 RSS): at grid_cn / grid_jp / grid_sea the fabs run under
5% of capacity in 80-90% of episode-weeks, because the grid has a **tiny** home shortfall every week (CN median ~0.4%
of base load) and under base_first fabs get nothing. They never lack wafers. The oracle starts ~4x the lots there.
Task 16's planner restricted to CN/JP/SEA gave only +0.013 on Full 6, so this is still open.
Task 17's hint (untested): size the extra fuel to **shortfall + fab draw** (≈0.5-1% of load at CN), not to weeks of
burn (that is why the plain pulse at CN cost −0.15 RSS in task 14). Ideas, your call: a small targeted top-up / pulse at
these grids sized to close the shortfall plus the fab draw; letting the fuel LP value fab power at these grids (chips
they make × pi of their sinks); planning alternating weeks (bank fuel, then one fully-powered fab week). Check what is
physically reachable first (`outputs/reachable_bound.py`, task 17's `fabs17.py`) and say why the planner missed it.
1. Build in a copy (`agents/mpc_fab3/`, from `agents/mpc_bufplan`, with pp20 on; new options off by default).
2. Funnel vs baseline `{"agent": "agents/mpc_bufplan", "params": {"pulse_plan": true, "pp_value": 20}}`: CN/SEA exist
   only on Full, so go straight to `full 0 devpick:2,2,1,1`, then `full 0 dev` if better, plus `small random 20` as a
   no-harm check (JP is on Small).
3. Report fab lots at CN/JP/SEA (agent vs oracle) and shed by grid, before vs after.
4. `sbf check` Small and Full for the best variant (CPU max/median per week).

### 19. BUILD: stop making chips nobody can sell (runs in parallel with task 18)
Task 17 (results/task-17.md, point 2): mpc_buffer disposes of **10.3M chips per episode** on Full (oracle ~0.3M) and
ends with 4.0M in stock. Mostly chip_mat_raw at fab_us_mature_1 (3.6M) and fab_eu_mature_1 (1.4M), chip_le_raw 1.4M at
US fabs, packaged chip_le/chip_mat 1.5M each at the kr/tw/my OSATs. The agent also over-starts US fabs (17.4M lots vs
the oracle's 9.8M) and TW (17.1M vs 14.8M): more output than their OSAT routes can take (e.g. sanctioned fab→OSAT
edges), plus 2.1M chip_le + 3.5M chip_mat lots started in the last 10 weeks that can't reach a sink in time.
Ceiling ≤ 0.2 T USD/episode (value of those chips), realistic part unknown: measure it first.
Ideas, your call: cap lots at fabs whose raw-chip outflow is blocked or full; send the wafers/power to fabs whose chips
can reach a sink instead (that's where the value is, not the disposal cost of 0.011 T); stop starting lots that can't
reach a sink before the episode ends; route raw chips before they overflow.
1. Build in a copy (`agents/mpc_sell/`, from `agents/mpc_bufplan`, with pp20 on; new options off by default).
   Don't touch CN/JP/SEA fuel/pulse logic (that's task 18; the two should combine later).
2. Funnel vs baseline `{"agent": "agents/mpc_bufplan", "params": {"pulse_plan": true, "pp_value": 20}}`:
   `small random 20` → `full 0 devpick:2,2,1,1` → `full 0 dev` if better.
3. Report chips disposed / ending stock / lots per fab (agent vs oracle), before vs after.
4. `sbf check` Small and Full for the best variant (CPU max/median per week).

## Round 5 (2026-10-08 afternoon): the map

New facts: **`agents/mpc_fab3sell`** = task 18's best (mpc_fab3 + kappa_lp, pp_direct cn/eu, pp_split) + task 19's
`sell_end`, all set in its `params.json`. **Codabench Small 0.7668** (200 hidden episodes); Full dev 20 ≈ 0.805-0.81.
**Baseline for round 5: `agents/mpc_fab3sell`** (plain `{"agent": "agents/mpc_fab3sell"}`). Board: 5th place is
0.8537 on Small, so we need **≈ +0.08-0.09**. Small tuning is useless now: we need to know where a big chunk is.
Task 17's map was for the older mpc_buffer (CN turned out mostly fixed already), so it must be redone.

### 20. MEASURE: where does mpc_fab3sell still lose points? (the map, report fast)
Rerun task 17's breakdown on `agents/mpc_fab3sell`, **Full dev 20 and Small dev 20** (`outputs/task-17/gap17.py`,
`report17.py`, `flow17.py`, `fabs17.py`; `outputs/cost_breakdown.py`). Gap to the clairvoyant plan, in T USD/episode
and as RSS points:
1. per cost component and harm level;
2. chip shortage by product × sink, and lots per fab vs the oracle (where are we short of chips, and which fabs could
   have made them: power-limited, wafer-limited, capacity-limited, or just not planned?);
3. shed by grid; 4. by time (quarters of the episode, last weeks);
5. **the list**: rank the 5-8 biggest separate leaks by T USD/episode, each with its cause in one line and whether
   it is reachable without foresight (say how you know). This list is the deliverable.
Note any difference between Small and Full (the board is Small, the final is Full).
No building in this task.

### 21. MEASURE: our chip LP vs the oracle's chip decisions, side by side
82% of the gap (task 17) is chip shortage, mostly in calm conditions, so the chip planning itself may be the leak.
On 4-6 Full dev episodes (`devpick:2,2,1,1` or a subset) compare week by week what `agents/mpc_fab3sell`'s chip LP
(`chips.py`) decides vs the clairvoyant LP (`shockbench_flow.oracle.lp`): wafer purchases, lots started per fab,
raw-chip routing fab→OSAT, packaged routing OSAT→sink, stock levels. Find the decisions that differ most in value
and say **why** ours differs: horizon (chip_H 24 vs a 104-week plan), demand forecast (what the agent assumes vs
the true demand), capacity assumptions (`fab_cap_mode`), the wafer buffer, end-of-window value, or something else.
For each cause, a cheap test of how much fixing it would give (e.g. give the chip LP the true future demand or a
longer horizon offline and measure). Bar: ≥ 0.15 T USD/episode. No building beyond those offline tests.

### 22. MEASURE (+BUILD if it pays): one joint LP instead of three glued planners
Our agent is three separate planners (fuel LP, chip LP that assumes fabs get all the power they ask for, pulse
planner); the oracle solves fuel → power → fabs → chips → sinks in **one** LP. The package already has the joint
version: `shockbench_flow.policies.mpc_det` (rolling `oracle.lp.build_lp` on the persistence forecast, horizon sweep
`mpc_det[H=...]`, planning rules) and `mpc_scen` (scenarios). On Small 64 eps (Oct 6, `outputs/compare_baselines.py`)
they scored mpc_scen 0.731, mpc_det_safety 0.719, mpc_det 0.717 — **below** mpc_fab3sell's Codabench 0.7668. Why?
1. Run `mpc_det` (canonical H and 1-2 longer H, e.g. the H_SWEEP's largest that fits) and `mpc_det_safety` vs
   `agents/mpc_fab3sell` on **Full devpick:2,2,1,1** (play them the way `outputs/compare_baselines.py` /
   `cost_breakdown.py` `policy:` does). Record RSS, CPU s per week (budget 4 s on Full; the scorer is maybe ~5x faster
   than the home FX-6100, unknown vs your machine) and the cost breakdown per component for each.
2. **Where does the joint LP win and where does it lose vs ours** (per component, per grid shed, per fab lots, per
   sink shortage)? E.g. does it keep CN/JP fabs powered better (it knows power and chips together) but lose on the
   things our hacks fix (wafer buffer, pulses through base_first rationing, chokepoint queues kappa_tb, sell_end)?
3. If its wins are big (≥ 0.15 T USD/episode on some component), say what a hybrid would look like (e.g. use the
   joint LP's fab energy / lots as targets for our planners, or run the joint LP and patch its action with our
   buffer/pulse logic) and, if time allows, build it as `agents/mpc_joint/` (start from `agents/mpc_fab3sell`, the
   joint part off by default) and test vs `agents/mpc_fab3sell`: `full 0 devpick:2,2,1,1` → `full 0 dev`.
   It must stay inside the CPU budget with margin, and fall back to mpc_fab3sell's action on any failure.

## Round 6 (2026-10-08 evening): the power side
Results of round 5 (read them): task 20 (the map), task 21 (**the chip LP is not the gap**: perfect information gives
it ≤ +0.006 RSS; the chip-side ceiling with foresight is 0.156 T), task 22 (the package's joint LP `mpc_det` scores
0.42-0.50 vs our 0.85 on Full 6: our three planners are the right design). What is left and reachable is on the
**power side**: (a) the pulses' price in home shed, Full ≈ 0.19 T/episode (TW 0.061, KR 0.056, CN 0.052, EU 0.015,
JP 0.012; task 20 item 2); (b) fab power at JP memory / SEA / CN, ≈ 0.18 T on Full devpick (task 21 "avail − free";
task 20 items 3, 6). Baseline: `agents/mpc_fab3sell`. We have until Oct 10 evening, so build properly.

### 23. BUILD: an honest value of fab energy in the pulse planner
`pplan.py` maximises VOLL × homes served + V × fab energy, with V = `pp_value` (20, a hand-tuned factor) × an estimate
of the chips the energy makes. So it buys fab power at 20x its estimated chip value and pays for it in home shed. But
many of those chips can't be sold (task 20 item 1, task 19: OSAT→sink edges at capacity; task 21: routing ceiling).
1. Measure first, on Full devpick: per fab grid and week, the planner's V vs the **true marginal value** of one more
   unit of fab energy there (e.g. the chip LP's dual / re-solve with +ε fab capacity → Δ lost sales at pi; or the oracle's
   value). Where is ×20 way too high or too low?
2. Build `agents/mpc_pval/` (from `agents/mpc_fab3sell`, new options off by default): feed the planner a per-grid
   (per-fab, per-week if cheap) value from the chip LP instead of `pp_value` × estimate. Keep CPU in budget (the chip
   LP runs after the energy side now; you may reuse last week's duals).
3. Funnel vs `agents/mpc_fab3sell`: `full 0 devpick:2,2,1,1` → `full 0 dev` → fresh Full seed 12 + `small random 20`.
   Report shed by grid and fab lots before/after.

### 24. MEASURE + BUILD: more power for the JP / SEA / CN fabs
Task 20 item 3: fab_jp_memory_1 runs at 21% of capacity (oracle 45%), 98% of its missed lots in weeks with JP shed
≥ 1% of base load; task 18 point 5 says JP crude can arrive ≤ ~553/week vs 891 needed (Malacca + Taiwan lanes) and JP
gas is cut 20-25% by sanctions in some episodes. Task 21: the power side is ≈ 0.18 T on Full devpick (eps 5, 53, 26).
1. For JP, SEA, CN: what limits the grid's output, fuel by fuel (lng / crude / nucfuel), week by week: source supply,
   lane/chokepoint capacity (incl. kappa_tb queues), terminal storage, the rationing line psi·I-bar, or our own
   dispatch? What does the **oracle** do differently there (which sources/lanes/fuels it uses, when it stocks up)?
   `outputs/reachable_bound.py` (homes-first MILP) gives what is reachable with foresight; also give a no-foresight
   estimate.
2. If a lever ≥ 0.1 T exists (e.g. other fuels/lanes the energy LP under-uses, stocking up before known cuts, nucfuel
   with its long lead, routing around Malacca), build it in `agents/mpc_jpow/` (from `agents/mpc_fab3sell`, off by
   default) and run the same funnel as task 23. Don't change pplan's valuation (that's task 23); the two should combine.
