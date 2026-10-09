Status: running Full dev 20

agents/mpc_combo = mpc_jpow (agent.py, pplan.py) + mpc_final (chips.py, fb_kappa_ct option). Changes are disjoint (jpow: energy LP / pulse planner; final: chip LP + params), so the merge is mechanical. Running the reproduction check on Full dev (devpick:1,0,0,0).

Surprise (verified): on this cloud machine `generator_id` for Full is `7740c8824dd9c8ed` (Small `d9adeaf8805a6767`), not the
home cache's `93b801effce44fbf` / `d8f72ccef883e24c`, and episode 0's omega hash differs (`39cc75cc...` here vs `a65422a1...`
in the home cache). Same package version / numpy 2.4.5 / scipy 1.18.1. So the scenarios themselves differ between the
machines: cloud "Full dev 20" numbers are NOT the same episodes as the home server's, and the cache tgz does not help here.
References are rebuilt (the dev split indices are the same: 0..7, 10, 14, 26, ...).

## 1. Reproduction check (Full dev episode 0 here = devpick:1,0,0,0, cloud generator)
mpc_combo with only jpow's params.json: J = 478022210632130 = mpc_jpow's J exactly (RSS 0.8706).
mpc_combo with only final's params.json: J = 473664773267382 = mpc_final's J exactly (RSS 0.8840). 0 fallbacks.
