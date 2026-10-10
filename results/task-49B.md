Status: done (full table pushed 18:21 UTC, 21 min after the 18:00 UTC deadline; partial tables were pushed at 17:53 and 18:02)

Plan: outputs/variants.py full 662778299 20 v49.json 4 (baseline mpc_final from task-48-closure 945fd19, own params.json;
variants = full params.json + changes: safety_5, cl4_all, combo, combo_cl). v49.json: results/v49.json.

## Result (root 662778299, 20 Full episodes, 4 jobs; wall: references 2240 s + 5 x ~580 s, 16:55-18:21 UTC)

```
round v49_full_662778299_1010-1655: task full, entropy 662778299, episodes 20, baseline baseline
references ready in 2240 s (20 episodes)
  played baseline in 579 s: RSS 0.8404
  played safety_5 in 601 s: RSS 0.8429
  played cl4_all in 551 s: RSS 0.8377
  played combo in 602 s: RSS 0.8388
  played combo_cl in 570 s: RSS 0.8392

full, entropy 662778299, 20 episodes; diff = variant - baseline, 90% paired interval
variant                      RSS     L1     L2     L3     L4     diff  interval               better%  fallb
baseline                  0.8404  0.841  0.860  0.787      -  +0.0000  [+0.0000, +0.0000]     nan%      0
safety_5                  0.8429  0.841  0.864  0.795      -  +0.0025  [+0.0004, +0.0046]    97.5%      0  <-- better
cl4_all                   0.8377  0.835  0.859  0.790      -  -0.0027  [-0.0053, -0.0001]     4.5%      0  <-- worse
combo                     0.8388  0.836  0.860  0.794      -  -0.0017  [-0.0062, +0.0026]    28.9%      0
combo_cl                  0.8392  0.837  0.861  0.792      -  -0.0012  [-0.0041, +0.0015]    25.6%      0

results: outputs/variants/v49_full_662778299_1010-1655/results.json
```

Notes / choices (nobody to ask):
- This root has no harm-level-4 episodes (L4 '-').
- 0 fallback weeks in every variant.
- References took 2240 s here (37 min, about twice task 48's 1037 s), so the full table missed 18:00 UTC. I kept the run going
  instead of stopping it and pushed partial tables (recomputed from the runner's incremental results.json with the same
  bootstrap) at 17:53 and 18:02 UTC.
- Raw results: results/task-49B-results.json. Log: results/task-49B.log. No upload.
