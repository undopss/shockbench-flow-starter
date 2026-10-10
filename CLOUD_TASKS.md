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

**Tasks 23 and 24 above are PARKED (not launched); don't do them unless your task number says so.**

## Round 7 (2026-10-08 evening): broader ideas, information we never used
Baseline for every task below: `agents/mpc_fab3sell` (Codabench Small 0.7668; Full dev 20 0.810, Small dev 20 0.782).
Read results/task-20.md (the map), task-21.md (chip LP is accurate; the remaining gap is the power side + foresight),
task-22.md (our three planners beat the package's joint LP by far). Other teams are at 0.85-0.88 on Small, so much
more is reachable without foresight than our ceilings suggested. We have until Oct 10 evening: build properly, but
keep each new piece an option that is **off by default** in a new agent folder, and keep the CPU budget with margin.
Funnel for anything you build (vs `agents/mpc_fab3sell`, same episodes): `small random 20` + `full 0 devpick:2,2,1,1`
→ if either is better, `full 0 dev` and `small 0 dev` → a fresh Full seed 12 as the overfitting guard.

### 25. BUILD: closed loop — let the agent learn from what actually happened (feedback)
Every week the agent sees what its last action did, and ignores it: `last_week.sinks.demand/served/lost`,
`last_week.clip.requested/executed` (did the simulator execute what we asked?), `last_week.cost_components`,
`last_week.shed.qty` (used only by the pulse), plus the realized stock/pipeline vs what our LPs predicted.
1. Measure first (Full devpick + Small dev, a few episodes): week by week, where do our planners' **predictions miss
   reality** systematically? E.g. fuel LP's expected grid output vs real G_av / shed per grid; chip LP's expected
   served vs real served per sink; requested vs executed per slot type (clipping we don't know about); pulse
   planner's predicted fab energy vs real. Which misses are biased (always the same sign) and big in USD?
2. Build `agents/mpc_fb/`: online corrections from those signals (e.g. per-grid / per-fab / per-lane learned
   correction factors or bias terms with a simple running estimate, shrunk toward 1 early in the episode).
3. Funnel above. Report which correction gave what.

### 26. MEASURE + BUILD: learn from the perfect plan what doesn't need foresight (imitation)
The oracle's decisions are part foresight, part structure (task 15: ~85% of the gap is calm-time planning). Find the
structural part and copy it.
1. On ≥ 40 training episodes of your own root (Full; and Small), solve the oracle (`shockbench_flow.oracle.lp`) and
   record, per week: grid stocks per fuel vs psi·I-bar, terminal stocks, fab energy / lots per fab, wafer stocks per fab,
   chip stocks per OSAT, which lanes/sources it uses. Do the same for `agents/mpc_fab3sell`.
2. Find patterns that depend only on what an agent can observe (week, stock, graph_now, forecast...): e.g. "the oracle
   keeps grid X's crude at ~k weeks of burn", "it powers fab Y in alternate weeks", "it front-loads wafers before week
   N", "it never uses lane Z". Fit simple rules/targets (per grid/fab, maybe a function of observed state); check on
   held-out episodes that they predict the oracle (and say how well).
3. Build `agents/mpc_imit/` that feeds those targets into our planners (e.g. as target stocks / soft constraints /
   values) and run the funnel.

### 27. MEASURE + BUILD: know the climate (disruption statistics) + use `closure_end`
Our planners assume the present persists. Instead, learn the **statistics** of disruptions offline and hedge, without
predicting a specific event. Also read `closure_end.chokepoint` / `closure_end.end_week` (announced reopening of a
closed strait), which no agent of ours has ever used.
1. From ≥ 200 training episodes (gym `ShockBench/Full-v0` / `Small-v0`, own root; ground truth from omega as
   `outputs/task-15/signals.py` does): per grid / chokepoint / source / edge, the rate and duration of energy shocks,
   closures, outages, sanctions, capacity cuts; how often `closure_end` is announced and how accurate it is.
2. Value: (a) `closure_end`: when a strait's reopening is known, don't route the long way / don't over-stock (or plan
   the flow for the reopening week); (b) risk-based safety stocks: per grid/fuel, a safety level from the shock
   statistics (expected shortfall during a typical shock × its probability) instead of the flat `safety_weeks`, and
   expected-capacity derating of risky lanes in the LPs.
3. Build `agents/mpc_clim/` (precomputed statistics stored as a small data file next to agent.py; nothing per-episode
   leaks from the hidden set) and run the funnel. Report (a) and (b) separately.

## !!! Runner bug fixed (2026-10-08 ~18:30 Kyiv), read this
Until commit after dd67ac4, `outputs/variants.py` **dropped the agent folder's own `params.json`** when a variant had
no "params". So `{"agent": "agents/mpc_fab3sell"}` played mpc_fab3sell's PARAMS defaults = **mpc_bufplan pp20**
(Full dev 20 0.7820, not 0.8099), and every round-7 "diff vs mpc_fab3sell" is really vs pp20. Variants that pass
the full params (e.g. task 25's sfcap) are fine in absolute RSS. Now fixed: with no "params" the folder's own
params.json is kept. **Compare against the absolute mpc_fab3sell numbers, or rerun the baseline with the fixed runner.**

## Round 8 (2026-10-08 evening)

### 28. MEASURE: "rule lawyer" — read the whole simulator and list the mechanics we don't exploit (Full only)
Other teams are at 0.85-0.88 on Small; we are at 0.767 (Small) / ~0.81 (Full dev 20) with `agents/mpc_fab3sell`, and
every lever we measured from the outside turned out small (results/task-15..27). Maybe they exploit rules we never
read. What we already read and use: the energy step (`shockbench_flow/dynamics/sim.py` step 7, `production.py:
allocate_energy`: fixed fuel shares, base_first, rationing line psi·I-bar → our pulses) and the strait release
(`chokepoint.py`: FIFO, kappa_tb, `release_mode`/`override_qty`; task 4 found tanker priorities a dead end on Full).
1. Read **every** module of the simulator and the cost accounting end to end (`shockbench_flow/dynamics/*`,
   `instance/schema.py`, the cost / scoring code, how RSS is computed and weighted). For each mechanic write: the exact
   rule (file:line), what our agent does about it now, and whether an agent could gain from it. Candidates (not a
   limit): how fabs and OSATs choose what to start (order, yield `alpha_bar`, OSAT `R`), lot/wafer timing, storage caps
   and disposal, end-of-episode salvage and terminal value, holding and queue-holding charges, tariffs and war risk,
   lost sales vs backlog per sink, demand generation and the forecast, edge/lane alternatives (`alt_of`, `edges.mode`),
   container throughput `kappa_ct`, the energy step's corner cases, what `release_mode` "hold" (2) can do for fuel or
   for timing, anything in the action space we never set, the fallback rule, rounding/clipping, the scoring's harm
   levels and weights (level 1 = 50%).
2. For every mechanic that could be worth something, a **rough ceiling in T USD/episode on Full** (cheap check on Full
   devpick:2,2,1,1, e.g. a counterfactual play or an LP bound), and how it could be used without foresight.
3. Deliverable: `results/task-28.md` with a ranked table "mechanic | rule (file:line) | we do now | idea | ceiling T |
   needs foresight?". No building in this task. Baseline numbers: use `agents/mpc_fab3sell` with its own params.json
   (the runner bug is fixed in `outputs/variants.py`; if you use another play path, check it loads params.json).

### 26 (rerun). Finish the imitation task
The first task-26 session hit the account's usage limit mid-run. Continue on its branch:
`git fetch origin task-26-imit && git checkout task-26-imit` (`agents/mpc_imit`, `outputs/task-26/variants26.json`).
What it found before it stopped (from its log, partly not pushed): Full devpick 6 imit_room +0.0035, imit_target +0.0005;
Small random 20 imit_target +0.0033, imit_room +0.0003; **Full dev 20 (vs the real mpc_fab3sell 0.8099): imit_room 0.8228,
imit_target 0.8212** (intervals not recorded). Do, in order, pushing after each:
1. rerun `full 0 dev` with variants26.json (record the tables), plus a variant with **both** rules on (imit_room + imit_target);
2. a **fresh Full seed, 12 episodes** (the overfitting guard; pick a new random root and write it down), same variants;
3. `small 0 dev` as a no-harm check; 4. `sbf check` Small and Full for the best variant (CPU max/median);
5. finish `results/task-26.md`: what each rule does (in plain words), the tables, verdict. Full is what counts.
**Wait for every run in the foreground** (see "Never end your turn while a test runs").

### 28 (rerun). Rule lawyer — finish it
The first task-28 session hit the usage limit right after starting. Continue on `task-28-rulelawyer` if it has useful
work (`git fetch origin task-28-rulelawyer`), otherwise start it from `cloud`. Same instructions as task 28 above.

## Round 9 (2026-10-09): five big ideas on top of the final candidate (Full only)
**Baseline for every task in this round: `{"agent": "agents/mpc_imit_room"}`** (its own params.json is kept by the fixed
runner; Full dev 20 ≈ 0.823, Small 0.77). Read first: `results/task-20.md` (the map), `results/task-21.md`,
`results/task-26.md`, `results/task-28.md` (rule lawyer table). Bar: **plausibly +0.05 RSS on Full** (0.01 RSS ≈ 0.034
T/ep on Full). Funnel: `full 0 devpick:2,2,1,1` → `full 0 dev` → fresh Full seed 12 (write the root down) →
`small 0 dev` (no-harm only). Small is NOT a target (the final is Full). New code: a new folder copied from
`agents/mpc_imit_room`, new options off by default. **Time box: about 2 hours.** The account has a shared usage limit
that has killed sessions before, so **push `results/task-N.md` after every milestone** (numbers so far, with intervals),
so nothing is lost if you are cut off. Final candidate code must pass `sbf check` Small + Full (report CPU max/median).

### 29. BUILD: an honest value of fab energy in the pulse planner (`agents/mpc_pval`)
The same as task 23 above (read it), on the new baseline. The pulses' price in home shed is ≈ 0.19 T/ep on Full
(task 20 item 2). Measure V (pp_value × estimate) against the true marginal value of fab energy per grid/week (chip
LP duals or re-solve with +ε), then feed the planner that value. Report shed by grid and fab lots before/after.

### 30. MEASURE + BUILD: more power for the JP / SEA / CN fabs (`agents/mpc_jpow`)
The same as task 24 above (read it), on the new baseline. ≈ 0.18 T on Full devpick (task 21, task 20 items 3 and 6);
task 28 row 1 + "facts worth knowing" (crude starts at 0, JP crude segment 5× fab headroom, crude stock-outs per grid).
Ideas to test: stock crude/LNG ahead at JP/CN/EU (they shed from crude stock-outs), other lanes around Malacca,
pulsing crude too. Don't change pplan's valuation (task 29 does); the two should combine.

### 31. MEASURE + BUILD: the calm episodes (harm level 1 = 50% of the score) (`agents/mpc_calm`)
RSS weights the harm levels 50/30/15/5. On Full dev 20 level 1 is 0.800, level 2 0.854 (task 20): the biggest weight
has the second-worst score. 1. Split the gap to the oracle on the level-1 dev episodes into its parts (chip shortage,
shed by grid, pulse price, buffer holding/disposal, end effects), vs the same on level 2-4. Is the agent too
aggressive in calm episodes (pulses, buffers, kappa_lp built for storms)? 2. Find an online signal that tells calm from
stormy (e.g. no closures/sanctions/energy shocks so far, warning scores, observed strait throughput) and switch
parameters by it (e.g. smaller pulses / buffer in calm weeks). Use only what the agent sees; do not use the harm level
itself. Watch level 1 and the pooled RSS.

### 32. BUILD: steer power to the most valuable fab inside a grid (`agents/mpc_steer`)
Task 28 row 3: leftover grid power is split between a grid's fabs ∝ e·p̂/R with p̂ = min(α·R·cap0, wafers on hand), and
our wafer_buffer keeps 3 weeks of nameplate at **every** fab, so power is split by nameplate, not by value. Task 28
gross ceiling ≈ 0.07 T at TW + KR, more if combined with pplan's knowledge of which weeks are partial. 1. Measure per
grid and week: the power split we get vs the split that maximises chip value (which fab's chips are sellable now:
task 20 item 1 says OSAT/fab out-edges at capacity cause most chip_le disposal). 2. Build: in partial-power weeks,
control wafers on hand per fab (smaller buffer / fewer wafers at fabs whose chips can't get out, more at the
valuable ones), so the split follows value. Report fab lots, disposal and shed before/after.

### 33. BUILD + VERIFY: stack every small win into one final candidate (`agents/mpc_final`)
We have several small wins measured separately; stacked they may reach +0.03-0.05. Start from `agents/mpc_imit_room`
and test, one at a time and then combined: (a) pulse on TW+KR+JP+SEA (`pulse_grids`; Full dev 20 +0.0098 on
mpc_pulse, fresh seeds +0.002/+0.005), (b) `fb_kappa_ct` from `agents/mpc_fb` on branch `task-25-feedback`
(Full dev 20 +0.0032), (c) `imit_target` together with `imit_room`, (d) a small joint sweep of the most important
existing params on Full devpick (pp_value, pulse_weeks, wafer_buffer weeks/cost, pp_direct grids), each value range
written down. Keep only what is positive on Full dev 20 **and** the fresh Full seed 12. Then the guard: the agent must
not crash or fall back if a grid name in params (pulse_grids, pp_direct) is missing from the map (skip it silently;
test with a renamed grid). Deliver `agents/mpc_final` with its params.json, the tables, `sbf check` Small + Full.

## Round 10 (2026-10-09 evening): team goal Full ≥ 0.85
Round 9 results (all merged into `cloud`): 29, 31, 32 dead; **30 `agents/mpc_jpow`** (jp_qedge + jp_arrfb 0.2, a
forecast bug fix: Full dev 20 +0.0091, fresh Full 12 +0.0061, all intervals > 0) and **33 `agents/mpc_final`**
(fb_kappa_ct + safety_weeks 4 + pp_end 0.7 + warn_gain 0.5: Full dev 20 +0.0043, fresh +0.0029; the grid-name guard
test passed). Both are copies of `agents/mpc_imit_room` with different code changes, never tested together.

### 34. BUILD + MEASURE: the combined agent and a fresh gap map (`agents/mpc_combo`)
1. Build `agents/mpc_combo` = `agents/mpc_imit_room` + the code changes of **both** `agents/mpc_jpow` and
   `agents/mpc_final` (diff each against mpc_imit_room, merge by hand, new options off by default in PARAMS).
   params.json = the union of both params.json files. Check: with only jpow's params it must reproduce mpc_jpow's play
   exactly on one Full dev episode (same J), and the same for mpc_final; write the J values down.
2. Variants vs baseline `{"agent": "agents/mpc_imit_room"}`: `combo` (full union), `combo_safe` (jpow params +
   `fb_kappa_ct` only), `jpow` (agents/mpc_jpow), `final` (agents/mpc_final). Run `full 0 dev` (20) and a **fresh Full
   seed, 20 episodes** (pick a new random root, write it down). Push after each run.
3. `sbf check` Small + Full on the best variant (CPU max / median), and `outputs/task-33/guard_test.py` on it.
4. **New gap map** of the best variant on Full dev 20 (the task-20 scripts: `outputs/task-17/gap17.py`,
   `outputs/task-20/map20.py`, `disp20.py`, `flow20.py`). The cost to the clairvoyant split into: shed by grid; chip
   lost sales split into **(a) not made** (fab had no power / no wafers / at capacity), **(b) made but disposed** (where,
   why), **(c) made but late or at a cheaper sink**; holding / disposal / tariff / freight. Compare with task 20's
   map (mpc_fab3sell) line by line: what did jpow change? Then the per-episode RSS list sorted, with the **5 worst
   episodes** and for each one line on what dominates its gap.
5. `results/task-34.md`: the tables exactly as printed, the recommended final candidate (with its params.json), the
   new map, and the 3 biggest remaining leaks with a rough T/ep each. Full is what counts.

### 35. BUILD: "jpow for chips" — shared downstream edges and strait queues in the chip LP (`agents/mpc_cq`)
Found by Andrii's audit (`ideas/PULSE_V2_DETAILED_AUDIT.md` on branch `task-26-imit`, "P1 — Chip route LP can overbook
shared downstream edges"; read it) and checked in our code: `chips.py` (~line 355) shares edge capacity **only per
route's first edge** (`by_edge[ls["first"]]`); each slot alone is capped by the min capacity along its route. The
simulator clips a dispatch only on its first edge (`dynamics/clip.py`); later legs are capped when cargo is released
from a chokepoint queue onto the next edge (`chokepoint.py`: eta = min(1, u_e / cargo queued onto e), plus kappa_ct
for containers). So two chip routes with different first edges can each plan the full capacity of a shared later
edge; the excess waits in the strait queue and arrives late, while the LP plans with on-time arrivals. Andrii counts 29
such (commodity, shared edge) groups on Full. Task 30 fixed the same mechanism for tanker fuel (`jp_qedge` in
`agents/mpc_jpow`), never for chips.
Start from **`agents/mpc_jpow`** (it has the tanker version of the fix to learn from) → `agents/mpc_cq`, new options
off by default. Baseline: `{"agent": "agents/mpc_jpow"}`.
1. Measure first (Full devpick:2,2,1,1): per chip lane and week, planned vs executed arrivals; how much chip cargo
   waits in strait queues because a later edge is full, and what it costs (late / lost sales at pi). Count the shared
   later-edge groups yourself.
2. Build: (a) a shared capacity row for **every** edge of every chip route, at the week the cargo reaches that edge
   (dispatch week + travel time of the earlier legs), over all slots and commodities that use it; (b) in the fixed
   arrivals, chip cargo already queued at a strait drains at min(kappa_ct share, next-edge capacity share), like
   `jp_qedge`; (c) both. Check the agent still reproduces mpc_jpow exactly with the options off.
3. Funnel vs mpc_jpow: `full 0 devpick:2,2,1,1` → `full 0 dev` → fresh Full seed 20 (new root, write it down) →
   `small 0 dev` (no harm only). `sbf check` Small + Full for the best variant (CPU max / median). Note: task 34 is
   building `agents/mpc_combo` (= mpc_jpow + mpc_final) in parallel; keep your change easy to copy into it (one option
   in chips.py + PARAMS).
4. `results/task-35.md`: the measurement, the tables, the verdict, and a one-line diff summary for porting to mpc_combo.

### 37. MEASURE + BUILD: chips made and thrown away (`agents/mpc_nodisp`)
Read `results/task-34.md` (new map) and `results/task-35.md`. On mpc_combo (Full dev 20) chips disposed are worth
≈ 0.27 T/ep at pi (chip_le 0.177 + chip_mat 0.089; ≈ 8 RSS points as a ceiling): 8.57 M units/ep disposed in weeks
the slot's out-edges were ≥ 95% full, 3.82 M with spare out-capacity (mostly chip_mat at fab_eu_mature_1, osat_tw,
osat_cn). Top: osat_kr chip_le 0.94 M, fab_us_mature_1 raw chip_mat 3.41 M (it makes 3.6 M more than the oracle),
fab_us_leading_3 raw chip_le 0.61 M, osat_tw chip_le 0.56 M, osat_my chip_le 0.49 M. Task 21 put better chip routing
with foresight at ≤ 0.094 T, so expect +0.01 to +0.03 at best; the bar here is a gain whose interval is above 0 on
Full dev 20 **and** a fresh Full seed. Reminder: the simulator starts every wafer a fab holds (up to cap and power) and
packages every raw chip an OSAT holds, so the only levers are **what we ship where** (wafers, raw chips, chips).
Start from **`agents/mpc_cq`** → `agents/mpc_nodisp`, new options off by default; baseline `{"agent": "agents/mpc_cq"}`.
1. Measure first on mpc_cq (Full devpick:2,2,1,1 with `outputs/task-20/disp20.py` / `outputs/task-34/map34.py`): how
   much disposal is left after task 35's fix, where, which commodity, and for each big case **why**: (i) out-edges
   full (then the chips should not have been made/sent there), (ii) spare out-capacity but no sink wanted them (then
   they should not have been made: wafers shipped to a fab whose output can't sell), (iii) spare capacity and demand
   but the LP did not ship (horizon end, LP model mismatch: e.g. disposal happens at end of week after serving,
   storage caps, lead times). Compare the chip LP's planned stock at each node with the real one.
2. Build the fixes the measurement points to. Candidates: a wafer buffer only where the fab's output is sellable
   (task 19's `sell_buffer` exists in chips.py, off; or size the buffer by the fab's sellable output, not nameplate);
   plan raw-chip shipments to OSATs with their out-edges' remaining capacity (cq_edges may already cover it); fix any
   LP-vs-simulator mismatch found in (iii).
3. Funnel vs mpc_cq: `full 0 devpick:2,2,1,1` → `full 0 dev` → fresh Full seed 20 (new root, write it down) →
   `small 0 dev` (no harm only). `sbf check` Small + Full for the best variant. Report disposal and lost sales
   before/after, by node.
4. `results/task-37.md`: measurement, tables, verdict, and a short port note (which files/options) so the change can
   be copied into the final agent (mpc_combo + cq).

### 38. BUILD + VERIFY: the final candidate (`agents/mpc_best`) = mpc_combo + cq + nd_open
Read `results/task-34.md`, `results/task-35.md`, `results/task-37.md`. Three verified wins, never tested together:
`agents/mpc_combo` (jpow + final; its chips.py comes from mpc_final: `fb_kappa_ct`), `agents/mpc_cq` (chips.py options
`cq_edges`, `cq_drain`, `cq_kappa`, built on mpc_jpow's chips.py) and `agents/mpc_nodisp` (= mpc_cq + `nd_open` in
chips.py). Deadline today 23:59 Kyiv, so work carefully but report fast.
1. Build `agents/mpc_best` from `agents/mpc_combo`: merge **by hand** the chips.py changes of mpc_nodisp (cq_* and
   nd_open) into combo's chips.py (which has fb_kappa_ct), plus the PARAMS and the `ChipPlanner(...)` arguments in
   agent.py. Diff every file against its sources first. params.json = mpc_combo's + `"cq_edges": true, "cq_drain": true,
   "cq_kappa": true, "nd_open": true` (and nothing from nd_open_e / sell_buffer: they were harmful).
   Reproduction checks on one Full dev episode, same J exactly: mpc_best with combo's params.json = mpc_combo; mpc_best
   with mpc_nodisp's params.json = mpc_nodisp. Write the J values down. Run `outputs/task-35/smoke35.py`-style smoke
   (all options on, every week, 0 LP failures; the agent swallows exceptions).
2. Variants vs baseline `{"agent": "agents/mpc_combo"}`: `best` (all), `best_no_nd` (without nd_open),
   `nodisp` (agents/mpc_nodisp). Runs, pushing after each: `full 0 dev` (20); fresh roots **540469033**, **1730880025**,
   **910653604** (20 each, the seeds tasks 34/35/37 used); and one **new** fresh root ×20 nobody has used (write it
   down; this is the untouched overfit guard). Then `small 0 dev` (no harm only). Report each table as printed and a
   pooled mean over the Full sets.
3. `sbf check` Small + Full for `best` (CPU max / median) and `outputs/task-34/guard_test.py 0 agents/mpc_best`.
4. Pack it: `uv run sbf pack mpc_best` and report the zip's sha256 (**do not upload**).
5. `results/task-38.md`: tables, verdict (is mpc_best the final? if a part hurts, drop it), the final params.json, the
   zip sha256. Status line first, updated after every run.


## Round 11: map the remaining gap to the oracle

### 39. ANALYZE + IMPROVE: explain the remaining RSS gap for the final candidate

Start only after task 38 has a final verdict. Use the final candidate selected there; if task 38 drops an option, do not resurrect it here. The current mpc_best score of 0.8855 is one Full dev episode only, not the pooled board score.

RSS is normalized against the clairvoyant oracle: RSS = 1 exactly when J_policy = J_oracle. For each harm stratum, 1 - RSS is the remaining fraction of the naive-to-oracle savings denominator. Report this distinction clearly. The oracle knows the full disruption path; classify losses as policy-reducible, resource-constrained, or information/foresight-limited. Do not promise that 1 is attainable by a causal online policy.

1. **Establish the baseline and make a fresh gap map.** On the exact Full dev episodes used for task 38, reproduce the selected candidate and compute pooled RSS with the official scoring code, per-stratum RSS, and paired differences against mpc_combo. Adapt task 34's map34 analysis to the selected candidate and report per-episode plus per-stratum costs against the same naive and oracle references. Keep units explicit (integer cents, USD/episode, and RSS); verify the mapping sums to the scorer's residual J gap. Add one untouched fresh Full root with 20 episodes, chosen before inspecting its results. Include level-4 episodes in the combined evidence, or state clearly if none were drawn.

2. **Separate the residual into actionable causes.** Re-measure, rather than copy task 34's mpc_combo numbers: shortage / lost chip sales, home-grid shedding, freight, tariffs, holding, disposal, salvage, and any remaining queue delay. For chip losses split chip_le and chip_mat into not made, disposed, and delivered too late / left in stock. For each large loss, attribute it to power, wafer availability, sanctions, fab choice, OSAT output, edge capacity, chokepoint queues, or forecast error. Mark gross production ceilings as upper bounds, not recoverable savings.

3. **Prioritize the experiments by measured headroom.**
   - **Fab power and wafer allocation:** test steering scarce power and wafers toward high-value JP/KR memory and CN/SEA fabs, while reducing surplus production that is later disposed (notably US mature). Task 34 estimated about 0.683 T/episode of gross fab output at risk in weeks with at least 1% home shedding; treat this as an upper bound and identify what is actually reachable after sanctions, wafers, power, and transport constraints.
   - **Production, routing, and sink demand together:** make the chip plan value shipments by whether they can reach a sink before demand expires. Inspect residual disposed lots and late sales after cq_edges, cq_drain, cq_kappa, and nd_open; distinguish lanes that are truly full from LP/simulator timing or inventory mismatches. Do not count the same lost sale under both shortage and disposal.
   - **Remaining queues:** task 35 reduced next-edge-full queueing from 273M to 15.4M unit-weeks per episode; re-measure on the final candidate, including Malacca-to-Suez. Only build another queue change if the map shows it can recover material demand.
   - **Home-grid shedding:** quantify the remaining value by grid and episode, especially TW, CN, KR, JP, and EU. Test changes to energy/fab dispatch against the same episodes; keep options that worsen homes or other harm strata out.
   - Treat small freight/tariff/holding improvements as secondary unless the new map shows a larger share than task 34 did.

4. **Run a paired funnel, one causal change at a time.** Compare each candidate to the selected task-38 final on Full dev 20 and the untouched fresh Full 20; reuse an existing seed only as a diagnostic, not as the untouched guard. Include Small dev 20 as a no-harm check. Print the paired 90% interval, better share, RSS by stratum, and the component gap before/after. Do not add separately measured gains arithmetically: interactions must be tested in the combined candidate. Run sbf check Small and Full and the task-34 guard test on any final pick.

5. **Deliverable:** update results/task-39.md with the status first, exact candidate and params, seed roots, RSS tables, a cost-to-oracle waterfall that reconciles to the scorer, confidence intervals, checks, and a verdict. Rank the top three remaining levers by recoverable RSS with evidence; label speculative ceilings and irreducible/foresight losses. Keep the best validated candidate if a new idea does not beat it reliably.

### 39 A / B / C. TUNE: re-tune the parameters of `agents/mpc_best` after the new fixes (three sessions in parallel)
`agents/mpc_best` (branch **`task-38-best`**, get it with `git fetch origin task-38-best && git checkout
origin/task-38-best -- agents/mpc_best`) = combo + cq + nd_open: Full dev 20 0.8454 (+0.013 vs mpc_combo); task 38 is
still running its fresh seeds. Its parameters were tuned before jpow / cq / nd_open changed how fuel and chips flow, and
some were never tuned. Earlier sweeps were flat or overfit (task 33: devpick +0.014..0.019 shrank to +0.001..0.006 on
dev 20; task 29: pp_value flat 5..80), so do it **honestly**:
- **Tune on a training root nobody has used: `full 20261010 20`** (entropy root 20261010, 20 episodes; all three
  sessions use the same root). Do **not** tune on `full 0 dev` or on the seeds of tasks 34/35/37/38.
- Baseline `{"agent": "agents/mpc_best"}` (its own params.json). Each variant = `{"agent": "agents/mpc_best",
  "params": {<mpc_best's params.json> + the one change}}` (the runner replaces params.json when "params" is given, so
  always pass the full set). One parameter at a time, the values listed below, all in one variants.json if CPU allows.
- Keep a value only if its interval on the training root is above 0. Then test **the combination of your winners**
  once on the training root, and confirm **once** on `full 0 dev` and on fresh root **342100426** (task 38's untouched
  seed). Report it as "kept" only if it is positive on both confirmations.
- If a value makes CPU per week rise (chip_H, H, pp_enum_H), report `sbf check --task=full` max CPU for it.
- `results/task-39X.md` (X = A/B/C): every table as printed, every value tried (also the losers), the final kept
  params and their confirmation tables. Status line first, pushed after every run. Branch `task-39X-tune`.

**39A (chips):** `wafer_buffer` 2, 2.5, 3.5, 4 (now 3); `buffer_cost` 300, 3000 (now 1000); `chip_H` 20, 28 (now 24).
**39B (energy):** `H` 10, 16 (now 12); `safety_weeks` 3, 5 (now 4); `cover_frac` 0.6, 1.0 (now 0.8); `imit_burn` 0.8, 1.0
(now 0.9); `end_weeks` 2, 4 (now 3).
**39C (pulses + JP):** `pulse_weeks` 1.0, 2.0 (now 1.5); `jp_arrfb` 0.1, 0.35 (now 0.2); `pp_end` 0.5, 0.9 (now 0.7);
`pp_H` 6, 10 (now 8; enum stays 6).

## Round 12 (2026-10-10, final day): the pulse leak

### 40. MEASURE + BUILD: lost generation during pulses (`agents/mpc_pleak`)
Start from `agents/mpc_best` (get it with `git fetch origin task-38-best && git checkout origin/task-38-best --
agents/mpc_best`; Full 100 episodes 0.8468, final candidate). Team goal Full ≥ 0.85, so a reliable +0.003..+0.01 counts.
Deadline today 23:59 Kyiv: **report within ~2.5 h**, push often.

Background (task 14, `results/task-14.md` on branch task-14-cheaper-pulse, measured on old mpc_pulse): the TW/KR pulse
added 0.116 T/ep of home shed; 0.065 T is the intended home→fab transfer, but **≈0.05 T (~+0.015 RSS) was generation
lost outright** (fuel held back → ration factor / end-of-horizon stock). Nothing was built. Since then the pulse is
planned by pplan.py (release modes) plus the `pulse_weeks` hold rule, so re-measure first.

**Speed rule: test ONLY on the cached Full dev episodes** (unpack `cache/sbf-cache.tgz` as in step 3 above; no new
seeds, no Small, no reference building). Use `full 0 devpick:<a,b,c,d>` (6 episodes) for quick probes and `full 0 dev`
(20) for the real comparison.
1. **Measure** on mpc_best, Full dev 20 (adapt `outputs/task-14/pulse_cost.py`): per grid (TW, KR, and any other
   pulsed grid) and week — generation vs what the fuel delivered could give, home shed, fab energy, fuel held in
   terminals/stock at episode end, ration-factor weeks. Split the pulse-related shed into (a) home→fab transfer,
   (b) generation lost (fuel arrived but not burned / burned too late / left at the end), (c) other. Give USD/ep and RSS
   (0.01 RSS ≈ 0.034 T on Full).
2. **Build** fixes for whatever (b) turns out to be, each behind a param (default off), e.g. release the held fuel
   so it is burned before it expires/ends idle, shorter hold when fabs are wafer-limited, burn down terminal stock
   before the end (pp_end), match the hold to fab demand. One causal change per variant.
3. **Variants** vs baseline `{"agent": "agents/mpc_best"}` (each = full mpc_best params.json + the change): probe on
   devpick 6, then the best 2–3 + their combination on `full 0 dev` 20. Keep only a change whose dev-20 interval is
   above 0. Note in the report that there is no fresh-seed check (overfit risk).
4. If something is kept: `sbf check mpc_pleak --task=full` (CPU max), `outputs/task-34/guard_test.py 0
   agents/mpc_pleak`, `uv run sbf pack mpc_pleak` + sha256. **Do not upload.**
5. `results/task-40.md`: status line first (pushed after every run), the measurement table, every variant table as
   printed, verdict, final params.json. Branch `task-40-pleak`.
6. **Must-test variant from the user ("mini pulses"):** while fuel is being held for a big pulse, release a small
   trickle to the grid (all of it goes to homes under base_first) instead of holding everything. Smart version: release
   only the fuel the coming pulse does **not** need to push fabs above home demand (e.g. fuel that would overflow
   terminal storage, be left at the end, or arrive in excess of the pulse's need). Try a fixed trickle fraction too
   (e.g. 10%, 25% of the held fuel per week) to see the trade-off. Same funnel as step 3.

### 41. MEASURE + BUILD: the score-weighted gap map and the worst calm episodes (`agents/mpc_calm2`)
Start from `agents/mpc_best` (`git fetch origin task-38-best && git checkout origin/task-38-best -- agents/mpc_best`).
Deadline today 23:59 Kyiv: **report within ~2 h**, push often. Task 40 (pulse leak) runs in parallel: don't touch
pulse/pplan code here.

Why: `scoring/rss.py` (56): RSS_G = sum_s p_s g-bar_s / sum_s p_s D-bar_s, p = (0.50, 0.30, 0.15, 0.05), with g-bar a mean
over the stratum's episodes. With equal episodes per stratum, **one USD saved in a level-1 episode is worth 10× one USD
in a level-4 episode**. Every gap map so far (tasks 20/34: "0.01 RSS = 0.034 T", shed 0.16 T, disposal 0.27 T) summed
USD equally, so it is dominated by levels 3/4. Small-looking leaks (holding, freight, tariff, disposal, chips left at
the end, buffer cost) may matter much more in RSS terms in level-1/2 episodes.

**Speed rule: test ONLY on the cached Full dev episodes** (unpack `cache/sbf-cache.tgz`; `full 0 dev` = 20, 5 per
level; `devpick` for quick probes). No new seeds, no Small.
1. **Weighted gap map** of mpc_best on Full dev 20 (adapt `outputs/task-17/gap17.py` + `outputs/task-34/map34.py`):
   every cost component (and shed by grid, chip lost sales split not made / disposed / rest, end stock) per level,
   in USD **and in RSS points** = p_s / n_s × gap / sum_s p_s D-bar_s. Check that the RSS points add up to 1 − RSS.
   Rank the components by RSS points.
2. **Worst calm/medium episodes:** ep7 (L1, combo 0.788), ep10 (L1, 0.797), ep6 (L2, 0.724), ep0 (L2, 0.790) (re-rank
   on mpc_best; take the 4 with the most RSS points lost at L1/L2). Week by week vs the oracle: what costs the agent
   pays that the oracle does not (which fab/grid/edge/sink, which weeks), and why (forecast, horizon, rule, bug).
3. **Build** a fix (behind a param, default off) for the biggest leak that is policy-reducible, one causal change per
   variant. Probe on devpick, then `full 0 dev` 20 vs `{"agent": "agents/mpc_best"}`; keep only an interval above 0
   that does not lose at L1/L2. Note: no fresh-seed check (overfit risk).
4. If kept: `sbf check mpc_calm2 --task=full`, `outputs/task-34/guard_test.py 0 agents/mpc_calm2`, `uv run sbf pack
   mpc_calm2` + sha256. **Do not upload.**
5. `results/task-41.md`: status line first (pushed after every run), the weighted map, the episode deep-dives,
   variant tables as printed, verdict, params.json. Branch `task-41-calm2`.

### 42. MEASURE + BUILD: act on the announcement messages (`agents/mpc_msg`)
Start from `agents/mpc_best` (`git fetch origin task-38-best && git checkout origin/task-38-best -- agents/mpc_best`).
Deadline today 23:59 Kyiv: **report within ~2 h**, push often. Tasks 40 (pulses) and 41 (gap map) run in parallel:
keep your changes in a separate, param-gated block.

Why: `messages.*` (docs/fields/full.md: channel 0 tariff_formal, 1 tariff_informal, 2 tariff_final, 3 sanction_legal,
4 ties_threat, 5 mid_threat; kind proposal / final_notice / threat / publication / withdrawal; region, target_kind,
target, k, announced_week, stated_effective_week) are never used by mpc_best. An old Small study (Oct 6) only found the
false-alarm rate "inconclusive"; nobody measured on Full **which messages precede a costly disruption and how early**.
`pending_prohibitions` (already used) cover sanctions once they are official.

**Speed rule: ONLY the cached Full dev episodes** (unpack `cache/sbf-cache.tgz`; `full 0 dev`, `devpick` probes).
1. **Measure** on Full dev 20 (play mpc_best, log observations; use the episode's omega / event list as ground truth):
   for every message thread: channel, kind sequence, target, announced / stated week, and what actually happened
   (closure of which chokepoint and how much, sanction/prohibition, tariff change, conflict demand shock, factory
   outage, nothing = false alarm), with the lead time in weeks. Table per channel: count, true-alarm rate, lead time
   (median, range), and the cost the event caused (agent vs oracle gap in the weeks after it, USD and RSS points with
   the level weights p_s / n_s as in task 41). Also: how many costly events had **no** message before them.
2. **Decide:** a channel is usable if true-alarm rate × lead time × event cost is material (rough ceiling ≥ +0.003
   RSS). If none is, stop and report (that is a fine result).
3. **Build** (if usable), behind params (default off): e.g. on a credible mid_threat/ties_threat naming a chokepoint
   or region, plan as if it closes / is cut at the stated (or typical) week — raise safety stock (safety_weeks) for
   grids fed through it, pre-ship chips/wafers ahead, avoid committing cargo to the lane; drop it on withdrawal.
   One causal change per variant; probe on devpick, then `full 0 dev` 20 vs `{"agent": "agents/mpc_best"}`. Keep only
   an interval above 0 that does not lose at L1/L2. No fresh-seed check (note the overfit risk).
4. If kept: `sbf check mpc_msg --task=full`, `outputs/task-34/guard_test.py 0 agents/mpc_msg`, `uv run sbf pack
   mpc_msg` + sha256. **Do not upload.**
5. `results/task-42.md`: status line first (pushed after every run), the message table, verdict, variant tables as
   printed, params.json. Branch `task-42-msg`.

### 43. BUILD: spend the spare CPU — longer / exact / scenario pulse planning (`agents/mpc_cpu`)
Start from `agents/mpc_best` (`git fetch origin task-38-best && git checkout origin/task-38-best -- agents/mpc_best`)
+ `"pulse_weeks": 1.0` (task 39C's only kept value; use it in the baseline too: baseline = `{"agent": "agents/mpc_best",
"params": <mpc_best params.json + pulse_weeks 1.0>}`). Deadline today 23:59 Kyiv: **report by ~16:30 Kyiv**, push often.
Task 40 also edits the pulse side (lost generation); keep your changes in separate, param-gated code paths.

Why: mpc_best uses ~0.5 s of the 4 s/week Full budget (cloud machine max 0.82 s). Bigger LP horizons gave nothing
(39A chip_H 28, 39B H 16 flat), but the pulse planner was never given more CPU: `pp_enum_H` (6) was never swept (pp_H is
a no-op under enum, task 39C), the `pp_method: "milp"` path was never compared, and the planner scores each release
option against ONE forecast of arrivals (task 14: ~0.05 T/ep generation lost = fuel held for pulses that do not pay).
An old whole-agent scenario planner (mpc_scen, Oct 6) was −0.09 on Full, but as a different, weaker agent.

**CPU guard for every variant:** `sbf check <agent> --task=full` max ≤ 2.0 s/week on this machine (2× headroom); the
planner must keep its process_time deadline (pp_deadline) and fall back to the deterministic plan when out of time.

1. **Quick part:** variants `pp_enum_H` 8, 10; `pp_method: "milp"` (with pp_H 8 and 12). Training root
   `full 20261010 20` (not dev, not the task 34/35/37/38 seeds), keep only intervals above 0, confirm once on
   `full 0 dev` 20 and fresh root 342100426.
2. **Scenario pulses:** in pplan, score each candidate release option against K sampled futures (K 8 and 16) instead
   of one: sample per-week fuel arrivals for the pulse grids from the agent's own observed history (e.g. empirical
   distribution of forecast error of arrivals: planned_arrivals vs what actually arrived, per fuel/grid), plus a
   closure/queue-delay draw for lanes through chokepoints at the rates observed so far (graph_now.open history,
   queue_lots). Pick the option with the best mean value (try also a 20%-quantile / CVaR variant). Seed the sampler
   deterministically (per episode + week) so runs are reproducible. Behind params (`pp_scen_K`, `pp_scen_risk`),
   default off. First measure on devpick that the arrivals forecast error is not zero (if it is ~0, say so: then
   scenarios cannot help and stop part 2).
3. Funnel for part 2: probe on `full 20261010` devpick-like subset, then `full 20261010 20`; winner(s) confirmed once on
   `full 0 dev` 20 and fresh root 342100426; kept only if both intervals are above 0. Then the combination of all kept
   parts on the same two confirmations.
4. If kept: sbf check Small + Full (CPU), `outputs/task-34/guard_test.py 0 agents/mpc_cpu`, `uv run sbf pack mpc_cpu` +
   sha256. **Do not upload.**
5. `results/task-43.md`: status line first (pushed after every run), every table as printed, CPU per variant, verdict,
   final params.json. Branch `task-43-cpu`.

### 44 A / B / C. VERIFY: the final candidate on fresh seeds (three sessions in parallel, one root each)
Get the code: `git fetch origin task-44-final && git checkout origin/task-44-final -- agents/mpc_final agents/mpc_pleak
agents/mpc_best`. `agents/mpc_final` = mpc_pleak (task 40) + `pulse_weeks 1.0` (39C) + code-review fixes that must not
change play (try around the term_store loop in _setup; HiGHS `time_limit` 1.5 s on the energy LP and the main chip
LP) + two options, off in its params.json: `pl_ucap` (cap task 40's releases at the terminal->grid edge capacity left:
every such edge carries lng AND crude, TW's only ~6.1k/week) and `pp_scen_K` (task 43's scenario pulses; pplan.py
copied from task-43-cpu). Deadline today 23:59 Kyiv: **report within ~1.5 h**, push after every run.
Roots: **44A = 540469033, 44B = 1730880025, 44C = 910653604** (20 episodes each; none was used to pick these options).
1. Smoke first (devpick:1,0,0,0 or one episode, all four variants below): 0 exceptions, 0 fallbacks.
   **44A only:** reproduction on `full 0 devpick:1,0,0,0`: mpc_final with mpc_pleak's params.json must give exactly
   mpc_pleak's J (the fixes are neutral); write both J. If not equal, stop and report.
2. variants.json vs baseline `{"agent": "agents/mpc_best"}`, each `{"agent": "agents/mpc_final", "params": {<full
   mpc_final params.json> + change}}`: `final` (as is), `final_cap` (+ `"pl_ucap": true`), `final_scen` (+
   `"pp_scen_K": 8`), `final_cap_scen` (both). Run `full <root> 20` (4 jobs). Print the table as is.
3. **44A only, after its root:** `small 0 dev` (no-harm), `sbf check mpc_final --task=full` and `--task=small` (CPU max
   / median, for final and final_cap_scen params), `outputs/task-34/guard_test.py 0 agents/mpc_final`,
   `uv run sbf pack mpc_final` + sha256. **Do not upload.**
4. `results/task-44X.md` (X = A/B/C): status line first, table(s), J reproduction (A), checks (A). Branch
   `task-44X-final`. No verdict needed: the team pools the three roots.

### 45 A / B. STACK + REHEARSE: last small wins on top of the uploaded final (two sessions, one new root each)
The uploaded final is `agents/mpc_final` on branch **`task-44-final`** (commit bb9674a; params.json has `pp_scen_K 8`,
`pl_ucap` off, `pulse_weeks 1.0`; zip sha256 3ef5c2e9...c2093). Get it with `git fetch origin task-44-final &&
git checkout origin/task-44-final -- agents/mpc_final`. Deadline today 23:59 Kyiv: **report within ~1.5 h**, push after
every run. Roots: **45A = 995215227, 45B = 1827351891** (new, drawn with SystemRandom; nobody used them).
Two small "leaners" were positive but never confirmed: `pl_overflow` (task 40: smart3_ovf_end4 +0.0039 vs smart3_end4
+0.0035 on dev) and the TIES-threat reaction `msg_ties_lag 4` (task 42 "ties4": +0.0021 [-0.0002, +0.0046] on dev).
1. Port `msg_ties_lag` from `agents/mpc_msg` (branch task-42-msg; diff it against agents/mpc_best) into
   agents/mpc_final behind its param (default 0). Reproduction on `full 0 devpick:1,0,0,0`: mpc_final with
   msg_ties_lag 0 must give exactly the J of the unchanged mpc_final. Push the code (both sessions do the same port;
   45B may instead wait ~10 min and take 45A's pushed agents/mpc_final from branch task-45A-stack).
2. variants vs baseline `{"agent": "agents/mpc_final"}` (its own params.json), each = full params + change:
   `ovf` (+ `"pl_overflow": true`), `ties4` (+ `"msg_ties_lag": 4`), `ovf_ties4` (both). `full <root> 20`, 4 jobs.
3. **Rehearsal** (mentor's advice): from the baseline run, report the per-episode RSS distribution of mpc_final
   (min / p10 / median / p90 / max, per level), the 3 worst and 3 best episodes with their level and top cost items
   (reuse outputs/task-41/map41.py if quick), and fallback/CPU per week (max, median) from the run.
4. 45A only: `sbf check` of mpc_final with the best variant's params, `--task=full` and `--task=small` (CPU).
5. `results/task-45X.md`: status first, tables, rehearsal summary. Branch `task-45X-stack`. **Do not upload.**

### 46. CHECK: the uploaded final on fresh Small episodes (does local match Codabench's 0.779?)
`agents/mpc_final` from branch **`task-44-final`** (commit bb9674a, the uploaded zip sha256 3ef5c2e9...c2093; get it with
`git fetch origin task-44-final && git checkout origin/task-44-final -- agents/mpc_final`). Codabench scored it
**0.779** on its 200 private Small episodes; our local Small dev 20 gave 0.8076 (earlier uploads showed the same
direction: imit_room local ~0.782 vs Codabench 0.7668). Question: is the dev split just easier, or does something differ?
1. `outputs/variants.py small 993322846 120 <json with only {"final": {"agent": "agents/mpc_final"}}> 4` (fresh root;
   the reference build is fine). Also pack the folder and confirm `sbf pack` prints the same sha256 3ef5c2e9...c2093.
2. Report: RSS, per level, episodes per level, 90% interval of the score itself if the runner gives it (else a
   bootstrap over episodes), fallback weeks. Compare with 0.779 and with dev 20 (0.8076, task 44A).
3. If time allows (≤ 40 min more): a second fresh root `small 1360000001 120` the same way.
4. `results/task-46.md`, status first, push after every run, branch `task-46-small`. **Do not upload.** Report within ~1 h.

### 47 A / B / C / D. LAST CHANCE: one-step parameter variants of the uploaded final (team decision: only 47A runs, root 895331359)
`agents/mpc_final` from branch **`task-44-final`** (commit bb9674a = the uploaded zip; `git fetch origin task-44-final &&
git checkout origin/task-44-final -- agents/mpc_final`). Its Full RSS sits right at 0.850; the team needs a reliable
+0.002..0.005. **Hard deadline: push the full table by 20:45 Kyiv (17:45 UTC)**; if time runs short, push what you have
(partial tables are useful), never wait past 21:00 Kyiv.
Roots (20 episodes each, new, nobody used them): **47A = 895331359, 47B = 1200216545, 47C = 1311782892,
47D = 2005633864**. All four sessions run the SAME variants.json, so the team can pool them.
Baseline `{"agent": "agents/mpc_final"}` (own params.json). Each variant = full params.json + ONE change:
`cover_1.0` (cover_frac 1.0), `safety_5` (safety_weeks 5.0), `scen_K16` (pp_scen_K 16), `scen_cvar` (pp_scen_risk 0.2),
`smart_2.5` (pl_smart_w 2.5), `smart_3.5` (pl_smart_w 3.5), `end_6` (pl_end 6), `burn_1.0` (imit_burn 1.0).
1. `uv run python outputs/variants.py full <root> 20 <v47.json> 4` (write v47.json exactly as above; same file in all
   four sessions). Push the printed table the moment it is done.
2. `results/task-47X.md`: status first, the table as printed, wall time. No verdict needed (the team pools the 4 roots).
   Branch `task-47X-last`. **Do not upload.**

### 48. TEST: "closure mode" on the uploaded final (one session, root 1341342961)
Code: `git fetch origin task-48-closure && git checkout origin/task-48-closure -- agents/mpc_final` (commit 945fd19 =
the uploaded mpc_final + option `cl_safety`, default 0 = unchanged). While a chokepoint on one of a fuel pool's supply
lanes is not fully open (open < cl_open 0.99), and for cl_hold weeks after, the energy LP adds cl_safety weeks of burn to
that pool's floor (fab grids only if cl_fab), so fuel is pulled in early / via longer routes before the fabs go dark.
**Hard deadline: push the table by 20:45 Kyiv (17:45 UTC).**
1. Smoke on `full 0 devpick:1,0,0,0` with `cl_safety 4`: 0 exceptions, 0 fallbacks (quick, ~2 min; skip the
   reproduction, default 0 is the uploaded code path).
2. variants vs baseline `{"agent": "agents/mpc_final"}` (own params.json), each = full params.json + change:
   `cl2` (cl_safety 2), `cl4` (cl_safety 4), `cl4_all` (cl_safety 4, cl_fab false), `cl4_h8` (cl_safety 4, cl_hold 8).
   `uv run python outputs/variants.py full 1341342961 20 <v48.json> 4`. Push the table the moment it is printed.
3. `results/task-48.md`: status first, the table as printed. Branch `task-48-closure`. **Do not upload.**
