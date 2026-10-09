Status: measuring (Full devpick 1,1,0,0, agent in "measure" mode: logs pplan's V and the chip-LP-dual V per grid/week)

Plan: measure pplan's fab-energy value V (pp_value x estimate) vs the chip LP's marginal value per grid/week on Full,
then feed the planner that value (`agents/mpc_pval`, options `pv_dual`, `pv_scale`, `pv_release`, off by default) and run the funnel.

Built so far: `agents/mpc_pval` = copy of `agents/mpc_imit_room` (same params.json) +
- `chips.py`: after the chip LP solves, `fab_val[fab][t]` = dual of each fab's start upper bound (USD per extra wafer start).
- `pplan.py`: with `fab_val`, V[t] = pv_scale * sum_f draw_f * fab_val_f * R/e / sum_f draw_f / VOLL (same fab draw estimate
  as before, only the USD per start changes from pp_value(20) * pi to the LP's dual). `pv_release`: if that V never beats
  VOLL in the window, release the grid's fuel (no pulse) instead of the fixed TW/KR pulse rule.
