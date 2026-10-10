Status: partial (18:02 UTC): baseline 0.8404, safety_5 +0.0025 (better), cl4_all -0.0027; combo, combo_cl still playing (~20 min)

Partial results (root 662778299, 20 Full episodes, 4 jobs):
```
references ready in 2240 s (20 episodes)
  played baseline in 579 s: RSS 0.8404
  played safety_5 in 601 s: RSS 0.8429
  played cl4_all in 551 s: RSS 0.8377

PARTIAL: full, entropy 662778299, 20 episodes; diff = variant - baseline, 90% paired interval
baseline                  0.8404  0.841  0.860  0.787      -  +0.0000  [+0.0000, +0.0000]     nan%      0
safety_5                  0.8429  0.841  0.864  0.795      -  +0.0025  [+0.0004, +0.0046]    97.5%      0  <-- better
cl4_all                   0.8377  0.835  0.859  0.790      -  -0.0027  [-0.0053, -0.0001]     4.5%      0  <-- worse
```
(partial table recomputed from the runner's incremental results.json with the same bootstrap; this root has no harm-level-4 episodes, so L4 is '-')

Plan: run outputs/variants.py full 662778299 20 v49.json 4 (baseline mpc_final from task-48-closure 945fd19 + safety_5, cl4_all, combo, combo_cl) and push the table.
