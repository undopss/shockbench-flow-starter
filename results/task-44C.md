Status: done

## Main: `full 910653604 20` (4 jobs, references 472 s)

```
full, entropy 910653604, episodes 20, baseline best
references ready in 472 s (20 episodes)
  played best in 189 s: RSS 0.8485
  played final in 190 s: RSS 0.8519
  played final_cap in 208 s: RSS 0.8518
  played final_scen in 435 s: RSS 0.8534
  played final_cap_scen in 430 s: RSS 0.8529

full, entropy 910653604, 20 episodes; diff = variant - best, 90% paired interval
variant                      RSS     L1     L2     L3     L4     diff  interval               better%  fallb
best                      0.8485  0.822  0.892  0.843  0.781  +0.0000  [+0.0000, +0.0000]     nan%      0
final                     0.8519  0.823  0.895  0.852  0.787  +0.0033  [+0.0022, +0.0048]   100.0%      0  <-- better
final_cap                 0.8518  0.823  0.894  0.852  0.787  +0.0033  [+0.0021, +0.0047]   100.0%      0  <-- better
final_scen                0.8534  0.825  0.894  0.855  0.797  +0.0049  [+0.0036, +0.0062]   100.0%      0  <-- better
final_cap_scen            0.8529  0.824  0.894  0.853  0.802  +0.0044  [+0.0027, +0.0059]   100.0%      0  <-- better
```

Play times (20 episodes, 4 jobs):

```
  played best in 189 s: RSS 0.8485
  played final in 190 s: RSS 0.8519
  played final_cap in 208 s: RSS 0.8518
  played final_scen in 435 s: RSS 0.8534
  played final_cap_scen in 430 s: RSS 0.8529
```

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
- The unpacked cache did not cover the smoke dev episode (1767 s to build that reference); the fresh root built 20
  references in 472 s.
