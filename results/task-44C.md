Status: running `full 910653604 20` (building references; ~30 min per episode on this box, 4 jobs)

## Smoke: `full 0 devpick:1,0,0,0` (0 exceptions, 0 fallbacks)

```
full, entropy 0, 1 episodes; diff = variant - best, 90% paired interval
variant                      RSS     L1     L2     L3     L4     diff  interval               better%  fallb
best                      0.8855  0.886      -      -      -  +0.0000  [+0.0000, +0.0000]     nan%      0
final                     0.8881  0.888      -      -      -  +0.0026  [+0.0026, +0.0026]   100.0%      0  <-- better
final_cap                 0.8874  0.887      -      -      -  +0.0019  [+0.0019, +0.0019]   100.0%      0  <-- better
final_scen                0.8902  0.890      -      -      -  +0.0047  [+0.0047, +0.0047]   100.0%      0  <-- better
final_cap_scen            0.8895  0.890      -      -      -  +0.0040  [+0.0040, +0.0040]   100.0%      0  <-- better

results: outputs/variants/v44c_full_0_1010-1223/results.json
```

Notes / choices:
- Variants file: `results/task-44C-variants.json` (baseline `agents/mpc_best`; the four mpc_final variants as specified).
- The unpacked cache did not cover this dev episode's reference (1767 s to build), so the fresh root's 20 references
  will take a while on 4 cores (~2.5 h estimated) — this run will likely finish after the ~1.5 h target.
