Status: done

Task 44B: verify mpc_final (+cap, +scen, +cap_scen) vs mpc_best on Full root 1730880025, 20 episodes.

## Root 1730880025: `full 1730880025 20` (4 jobs; references 447 s; 0 exceptions, 0 fallbacks)

```
full, entropy 1730880025, 20 episodes; diff = variant - best, 90% paired interval
variant                      RSS     L1     L2     L3     L4     diff  interval               better%  fallb
best                      0.8562  0.852  0.863  0.858      -  +0.0000  [+0.0000, +0.0000]     nan%      0
final                     0.8591  0.855  0.863  0.863      -  +0.0029  [+0.0011, +0.0048]   100.0%      0  <-- better
final_cap                 0.8588  0.855  0.863  0.863      -  +0.0026  [+0.0008, +0.0046]    99.8%      0  <-- better
final_scen                0.8621  0.857  0.870  0.865      -  +0.0060  [+0.0034, +0.0088]   100.0%      0  <-- better
final_cap_scen            0.8612  0.857  0.868  0.865      -  +0.0051  [+0.0027, +0.0078]   100.0%      0  <-- better
```
No harm-level-4 episodes among these 20 (L4 column empty).
Play time for 20 episodes (4 jobs): best 147 s, final 147 s, final_cap 148 s, final_scen 305 s, final_cap_scen 320 s.
Results: `outputs/variants/variants_full_1730880025_1010-1253/results.json`.

## Smoke: `full 0 devpick:1,0,0,0` (0 exceptions, 0 fallbacks)

Note: references for this one dev episode took 1318 s here (the cache did not cover it on this machine).

```
full, entropy 0, 1 episodes; diff = variant - best, 90% paired interval
variant                      RSS     L1     L2     L3     L4     diff  interval               better%  fallb
best                      0.8855  0.886      -      -      -  +0.0000  [+0.0000, +0.0000]     nan%      0
final                     0.8881  0.888      -      -      -  +0.0026  [+0.0026, +0.0026]   100.0%      0  <-- better
final_cap                 0.8874  0.887      -      -      -  +0.0019  [+0.0019, +0.0019]   100.0%      0  <-- better
final_scen                0.8902  0.890      -      -      -  +0.0047  [+0.0047, +0.0047]   100.0%      0  <-- better
final_cap_scen            0.8895  0.890      -      -      -  +0.0040  [+0.0040, +0.0040]   100.0%      0  <-- better
```
Play time per episode: best 27 s, final 26 s, final_cap 25 s, final_scen 64 s, final_cap_scen 63 s.

## Choices made (nobody to ask)
- Variants JSON: `outputs/task-44B/variants.json` (baseline `best` = agents/mpc_best; others = full mpc_final params.json + change).
- Smoke used the dev episode (devpick:1,0,0,0) as the task suggests, not an episode of root 1730880025.
