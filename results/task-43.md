Status: done. Verdict: nothing kept. Scenario pulses (`pp_scen_K 8`) are a small, consistent plus (+0.0009..+0.0026 RSS on 3 roots) but fail the dev-20 confirmation (interval includes 0); milp is −0.08; enum H 8/10 break the CPU guard.

# Task 43: spend the spare CPU on pulse planning (`agents/mpc_cpu`)

Baseline everywhere: `{"agent": "agents/mpc_best", "params": mpc_best params.json + "pulse_weeks": 1.0}` (mpc_best
from branch task-38-best). Every variant = the same params + one change, played with `agents/mpc_cpu`. With the new
options off, mpc_cpu plays the same code as mpc_best.

## What was built (`agents/mpc_cpu`, everything off by default)
- `pp_scen_K` (0 = off), `pp_scen_risk` (0 = mean; a in (0,1) = CVaR, the mean of the worst a share), in `pplan.py`:
  - Every week the planner records, per destination (terminal or grid, fuel), the ratio between what arrived this week
    and what it forecast a week earlier (last 52 weeks, clipped at 3).
  - In the enumeration, each release sequence is simulated against K futures instead of the one forecast. Future 0
    is the forecast itself. In each other future, the forecast arrivals of week + o (o ≥ 1) are multiplied by ratios
    drawn from that destination's own history, divided by the history's mean. So the futures add spread only; the
    level stays set by `jp_arrfb`. The sequence with the best mean (or CVaR) value is played.
  - Week 0 does not depend on the future, so its releases are the same in every future. For direct pipes (grid_cn,
    grid_eu), the week-0 release is taken from future 0. Grids fed by planned direct pipes keep their grid arrivals
    at the forecast, because their history mixes in the planner's own pipe releases and is not forecast error.
  - Seeded by `np.random.default_rng([config["policy_seed"], week, grid node])`, so runs are reproducible.
  - When all of a grid's histories have zero spread, or there are fewer than 4 samples, the planner uses the old
    one-forecast path. Scenarios only run while the week has room before `pp_deadline` (2× the last scenario cost);
    otherwise it uses the one-forecast plan.
- Tools: `outputs/task-43/timing.py` (CPU per week + forecast-error stats), `sanity.py` (exceptions / changed
  releases), `iv.py` (paired interval from a partial results.json), `build_refs.py`.

## Part 1 (quick): pp_enum_H, pp_method milp

CPU per week, one Full dev episode on this cloud machine (`timing.py`, 3 other processes running):

| variant (+pulse_weeks 1.0) | act max | act med | pplan max | pplan med |
|---|---|---|---|---|
| baseline (enum H6) | 0.52 | 0.32 | 0.09 | 0.06 |
| pp_enum_H 8 | **2.19** | 1.70 | 2.12 | 1.42 |
| pp_method milp, pp_H 8 | 0.99 | 0.50 | 0.74 | 0.24 |
| pp_method milp, pp_H 12 | 1.17 | 0.62 | 0.83 | 0.35 |
| pp_scen_K 8 (ep 0) | 1.25 | 0.96 | 1.00 | 0.67 |
| pp_scen_K 16 (ep 0) | 1.52 | 1.15 | 1.42 | 0.81 |

- **pp_enum_H 8 fails the CPU guard** (max 2.19 > 2.0 s/week). With pp_split there are 5 modes, so 5^8 = 390k
  sequences per grid. One grid's enumeration cannot be interrupted, so pp_deadline cannot stop it. pp_enum_H 10
  (5^10, 25× more, ~40 s/week) was not run. Both were dropped from the scored runs.
- milp: scored below, −0.08.

## Part 2: is the arrivals forecast error non-zero? (devpick check)

Measured as the ratio arrived / forecast a week earlier, per destination, over the last 52 weeks, Full dev episodes
0 and 7. It is **zero at most terminals**: std 0.000 at TW, CN, US, SEA, JP lng (dev ep 0). It is non-zero at a few:

| destination | ep 0 std | ep 0 share of weeks off by >10% | ep 7 std |
|---|---|---|---|
| term_kr k0 | 0.139 | 0.25 | 0.000 |
| term_kr k1 | 0.839 | 0.92 | 0.000 |
| term_jp k1 | 0.024 | 0.00 | 0.206 (25% off) |
| term_cn k1 | 0.053 | 0.13 | 0.000 |
| term_eu k0 | 0.060 | 0.04 | 0.000 |

grid_cn / grid_eu also show large "errors", but they come from the planner's own pipe releases, so they are not used.
Sanity check (`sanity.py`, dev ep 0, 60 weeks, K 8): 420 grid enumerations, 0 exceptions, **only 1 release differs**
from the one-forecast plan. So scenarios change very little, and that matches what the scored runs found.

## Runs (runner tables exactly as printed)

Training root `full 20261010 20` (no level-4 episode was drawn):
```
full, entropy 20261010, 20 episodes; diff = variant - base_pw1, 90% paired interval
variant                      RSS     L1     L2     L3     L4     diff  interval               better%  fallb
base_pw1                  0.8147  0.807  0.819  0.819      -  +0.0000  [+0.0000, +0.0000]     nan%      0
milp_H8                   0.7376  0.751  0.729  0.730      -  -0.0771  [-0.1019, -0.0545]     0.0%      0  <-- worse
milp_H12                  0.7325  0.749  0.725  0.716      -  -0.0822  [-0.1088, -0.0586]     0.0%      0  <-- worse
scen_K8                   0.8173  0.809  0.820  0.827      -  +0.0026  [+0.0010, +0.0044]    99.8%      0  <-- better
scen_K16                  0.8165  0.808  0.821  0.825      -  +0.0018  [+0.0000, +0.0036]    95.7%      0  <-- better
scen_K8_cvar20            0.8165  0.807  0.821  0.827      -  +0.0018  [-0.0002, +0.0038]    93.0%      0
```
scen_K16's lower bound rounds to +0.0000, and it costs more CPU than K8, so only scen_K8 went on to confirmation. No
part-1 value was kept, so "the combination of all kept parts" is scen_K8 alone.

Confirmation, Full dev 20 (`full 0 dev`):
```
full, entropy 0, 20 episodes; diff = variant - base_pw1, 90% paired interval
variant                      RSS     L1     L2     L3     L4     diff  interval               better%  fallb
base_pw1                  0.8459  0.851  0.873  0.810  0.768  +0.0000  [+0.0000, +0.0000]     nan%      0
scen_K8                   0.8468  0.852  0.874  0.812  0.773  +0.0009  [-0.0021, +0.0038]    71.1%      0
```
Confirmation, fresh root `full 342100426 20`:
```
full, entropy 342100426, 20 episodes; diff = variant - base_pw1, 90% paired interval
variant                      RSS     L1     L2     L3     L4     diff  interval               better%  fallb
base_pw1                  0.8250  0.828  0.852  0.806  0.716  +0.0000  [+0.0000, +0.0000]     nan%      0
scen_K8                   0.8265  0.829  0.856  0.804  0.721  +0.0015  [+0.0005, +0.0026]    99.7%      0  <-- better
```

## Verdict
- **pp_method milp: out** (−0.08 on training; it is much worse than enum). **pp_enum_H 8 / 10: out on CPU.**
- **pp_scen_K 8: not kept** under the task's rule. It is positive on the training root and the fresh root, but the
  dev-20 interval [−0.0021, +0.0038] includes 0. All three point estimates are positive (+0.0026, +0.0009, +0.0015),
  so it is probably a real but tiny gain (~+0.002). That is far below the +0.05 bar, and it doubles to triples
  CPU per week. If the team wants it anyway: `"pp_scen_K": 8` in params.json.
- The reason it cannot be big: the planner's arrival forecasts for the pulse grids are almost exact (tanker
  arrivals are known from the pipeline over the planner's 6-week window). So the "~0.05 T/ep generation lost" from
  task 14 is not caused by forecast uncertainty that sampling could hedge.

## Checks (on scen_K8, i.e. mpc_cpu with `pp_scen_K 8`, the candidate at the time)
- `sbf check mpc_cpu --task=full`: passed. Week 1 0.438 s, median act 0.886 s, **max 1.456 s** (≤ 2.0 guard; 2 other runs
  in parallel). `--task=small`: passed, median 0.665 s, max 0.833 s.
- `guard_test.py 0 agents/mpc_cpu`: A 466698522647475, B 467466971339443, C 468928707602958, D 467698114506806, all
  0 fallback weeks. **A ≠ B and C ≠ D is expected with scenarios on, and is not a guard failure.** EpisodeSet.play
  salts `policy_seed` with the submission folder's sha256 (scoring.py 565–576, `resolved.sha256`), so a different
  params.json gives different scenario draws. With the scenarios off, mpc_cpu is the same code as mpc_best (the
  grid-name handling is unchanged). Not re-run with K 0 (not verified here). This also means the zip uploaded to the
  board would get its own draws.
- Not packed (nothing kept). **Not uploaded.**

## Final params.json (`agents/mpc_cpu/params.json` = the baseline, scenarios off)
```json
{"kappa_lp": true, "pp_direct": ["grid_cn", "grid_eu"], "pp_split": true, "sell_end": true, "imit_grid": "room", "jp_qedge": true, "jp_arrfb": 0.2, "fb_kappa_ct": true, "safety_weeks": 4.0, "pp_end": 0.7, "warn_gain": 0.5, "cq_edges": true, "cq_drain": true, "cq_kappa": true, "nd_open": true, "pulse_weeks": 1.0}
```

## Notes / surprises
- The reference cache `cache/sbf-cache.tgz` was not used on this machine. References landed in generator dir
  `full/7740c8824dd9c8ed` instead of `93b801effce44fbf` (same shockbench-flow 0.1.2), so the naive quantiles, cut
  points and the dev references were rebuilt (~35 min plus ~35 min for the dev split). The dev baseline here is
  0.8459, against 0.8454 reported for mpc_best in task 38.
- Choices made without asking: K16 was not confirmed (lower bound +0.0000, more CPU); the CVaR variant was not
  confirmed; enum H 8 / 10 were not scored (CPU guard).
