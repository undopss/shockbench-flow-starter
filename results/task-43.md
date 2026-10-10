Status: running the training run (full 20261010 20: base, milp_H8, milp_H12, scen_K8, scen_K16, scen_K8_cvar20)

## So far
- `agents/mpc_cpu` = copy of mpc_best (task-38-best) + new params `pp_scen_K`, `pp_scen_risk` (default off).
- CPU per week (one Full dev episode, this cloud machine, 3 other processes running; `outputs/task-43/timing.py`):

| variant (+pulse_weeks 1.0) | act max | act med | pplan max | pplan med |
|---|---|---|---|---|
| baseline (enum H6) | 0.52 | 0.32 | 0.09 | 0.06 |
| pp_enum_H 8 | 2.19 | 1.70 | 2.12 | 1.42 |
| pp_method milp, pp_H 8 | 0.99 | 0.50 | 0.74 | 0.24 |
| pp_method milp, pp_H 12 | 1.17 | 0.62 | 0.83 | 0.35 |
| pp_scen_K 8 (ep 0) | 1.25 | 0.96 | 1.00 | 0.67 |
| pp_scen_K 16 (ep 0) | 1.52 | 1.15 | 1.42 | 0.81 |

- **pp_enum_H 8 fails the CPU guard** (max 2.19 > 2.0 s; one grid's enumeration is atomic, so pp_deadline cannot stop
  it). pp_enum_H 10 = 5^10 sequences (25x enum 8, ~40 s/week): not run. Both dropped from the score runs.
- Arrival forecast error (ratio arrived / forecast a week earlier, per destination, last 52 weeks): **zero at most
  terminals** (std 0.000 at TW, CN, US, SEA; JP k0), non-zero at a few: dev ep 0 term_kr k1 std 0.84 (92% of weeks off
  by >10%), term_kr k0 std 0.14; dev ep 7 term_jp k1 std 0.21. Grid_cn / grid_eu ratios are polluted by the planner's
  own pipe releases, so scenarios leave those grids' arrivals at the forecast.
- Sanity (`outputs/task-43/sanity.py`, dev ep 0, 60 weeks, K 8): 420 grid enumerations, 0 exceptions, **only 1 changed
  release** vs the one-forecast plan. Expect scenarios to be close to a no-op.
- Note: the reference cache in `cache/sbf-cache.tgz` was not used on this machine (a different generator digest dir
  `full/7740c8824dd9c8ed` instead of `93b801effce44fbf`, same shockbench-flow 0.1.2), so the naive quantiles, cut points
  and the dev references are rebuilt here (~40 min).
- Partial (training root 20261010, 20 ep): base 0.8147, **milp_H8 0.7376, milp_H12 0.7325 (−0.08: out)**. Baseline on
  Full dev 20 (this machine): 0.8459.
