Status: running fresh Full seed 20

agents/mpc_combo = mpc_jpow (agent.py, pplan.py) + mpc_final (chips.py, fb_kappa_ct option). Changes are disjoint (jpow: energy LP / pulse planner; final: chip LP + params), so the merge is mechanical. Running the reproduction check on Full dev (devpick:1,0,0,0).

Cache note (verified): on this cloud machine the reference cache key (`generator_id`) for Full is `7740c8824dd9c8ed`
(Small `d9adeaf8805a6767`), not the tgz's `93b801effce44fbf` / `d8f72ccef883e24c`, and the omega hashes differ too, so
the tgz cache is NOT used here and Full dev references were rebuilt (~28 min). But the episodes are the same: J_naive and
harm are identical on episodes 0, 5, 102 and J_oracle differs by 2 cents; dev RSS below matches tasks 30/33 exactly.
Next sessions can reuse the home cache by copying `full/93b801effce44fbf` to `full/7740c8824dd9c8ed` (and Small
`d8f72ccef883e24c` to `d9adeaf8805a6767`) under `~/.cache/shockbench-flow/references/v0.1.2-39ec701c95ac/` (not tested).

## 1. Reproduction check (Full dev episode 0 here = devpick:1,0,0,0, cloud generator)
mpc_combo with only jpow's params.json: J = 478022210632130 = mpc_jpow's J exactly (RSS 0.8706).
mpc_combo with only final's params.json: J = 473664773267382 = mpc_final's J exactly (RSS 0.8840). 0 fallbacks.

## 2. Full dev 20 (root 0), baseline agents/mpc_imit_room
```
full, entropy 0, 20 episodes; diff = variant - base, 90% paired interval
variant                      RSS     L1     L2     L3     L4     diff  interval               better%  fallb
base                      0.8228  0.821  0.858  0.791  0.755  +0.0000  [+0.0000, +0.0000]     nan%      0
combo                     0.8322  0.837  0.857  0.799  0.761  +0.0094  [+0.0030, +0.0165]    99.9%      0  <-- better
combo_safe                0.8331  0.841  0.858  0.792  0.759  +0.0103  [+0.0054, +0.0154]   100.0%      0  <-- better
jpow                      0.8319  0.840  0.853  0.797  0.759  +0.0091  [+0.0033, +0.0149]    99.9%      0  <-- better
final                     0.8270  0.826  0.861  0.797  0.757  +0.0043  [+0.0003, +0.0082]    96.4%      0  <-- better
```
combo = jpow + final params (union); combo_safe = jpow params + fb_kappa_ct only. Wins don't add: combo +0.0094 ≈ jpow
+0.0091; final's safety_weeks/pp_end/warn_gain add nothing on top of jpow. Fresh seed root: 540469033.
