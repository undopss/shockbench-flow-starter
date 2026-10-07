# Cloud tasks

You are a Claude cloud session working for the Mantis team. The person who started you said **"you are task N"**.
Do task N from the list below, and only that task. Everything you need is in this repo (branch `cloud`).

## Before you start

1. Read `CONTEXT.md` (rules, what we know, how the game works). The hard rules there apply: never guess numbers,
   never upload to Codabench, never push to `main`.
2. `uv sync`
3. The current best agent is `agents/mpc_chip`. Its options are in `PARAMS` at the top of `agents/mpc_chip/agent.py` and
   can be overridden by a `params.json` next to it. The test runner uses that to make variants without copying code.

## How to test (the same for every task)

Runner: `uv run python outputs/variants.py <small|full> <entropy|random> <episodes> <variants.json> 4`

- The first entry of `variants.json` is the **baseline** (always `{"agent": "agents/mpc_chip"}` unless the task says
  otherwise). Every other entry is compared with it **on the same episodes**, with a 90% paired interval.
- Stage 1 (filter): `small random 20`. Stage 2: `full 0 devpick:2,2,1,1` (6 Full dev episodes, all four harm levels).
  The first Full run builds the reference cache (~10-20 min); that is expected.
- An idea is promising if its Full stage interval is above 0 (the runner prints `<-- better`).
- **The bar:** we only care about ideas that can plausibly add **+0.05 RSS on Full**. Don't spend time on small tuning.

## How to hand back

1. Work on a new branch `task-N-<short-name>` from `cloud`.
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
