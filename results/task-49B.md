Status: partial (17:53 UTC): baseline 0.8404, safety_5 0.8429 (+0.0025 [+0.0004, +0.0046]); cl4_all, combo, combo_cl playing (~10 min each)

Partial results (root 662778299, 20 Full episodes, 4 jobs):
```
references ready in 2240 s (20 episodes)
  played baseline in 579 s: RSS 0.8404
  played safety_5 in 601 s: RSS 0.8429

PARTIAL: full, entropy 662778299, 20 episodes; diff = variant - baseline, 90% paired interval
baseline                  0.8404  0.841  0.860  0.787      -  +0.0000  [+0.0000, +0.0000]     nan%      0
safety_5                  0.8429  0.841  0.864  0.795      -  +0.0025  [+0.0004, +0.0046]    97.5%      0  <-- better
```
(partial table recomputed from the runner's incremental results.json with the same bootstrap; this root has no harm-level-4 episodes, so L4 is '-')

Plan: run outputs/variants.py full 662778299 20 v49.json 4 (baseline mpc_final from task-48-closure 945fd19 + safety_5, cl4_all, combo, combo_cl) and push the table.
