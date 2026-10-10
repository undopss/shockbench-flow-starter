Status: done (table pushed 16:50 UTC)

Plan: smoke mpc_final cl_safety 4 on full 0 devpick:1,0,0,0, then v48.json (cl2, cl4, cl4_all, cl4_h8 vs mpc_final) on full 1341342961 20, 4 jobs.

Branch note: origin/task-48-closure (945fd19) was not based on cloud; merged origin/cloud into it (no conflicts, agents/mpc_final untouched).

Choice (no one to ask): the smoke on `full 0 devpick:1,0,0,0` was still busy after ~10 min on 2 cores (apparently
building the dev references in this container), which risked pushing the main run past the 17:45 UTC deadline. I
stopped it at 16:04 UTC and started the main run directly (`full 1341342961 20`, 4 jobs); its exception/fallback
counts for the cl variants serve as the smoke check.

## Result (root 1341342961, 20 Full episodes, 4 jobs; wall: references 1037 s + 5 x ~305 s, 16:04-16:49 UTC)

```
references ready in 1037 s (20 episodes)
  played final in 306 s: RSS 0.8196
  played cl2 in 305 s: RSS 0.8206
  played cl4 in 306 s: RSS 0.8204
  played cl4_all in 315 s: RSS 0.8218
  played cl4_h8 in 306 s: RSS 0.8207

full, entropy 1341342961, 20 episodes; diff = variant - final, 90% paired interval
variant                      RSS     L1     L2     L3     L4     diff  interval               better%  fallb
final                     0.8196  0.861  0.760  0.844  0.654  +0.0000  [+0.0000, +0.0000]     nan%      0
cl2                       0.8206  0.862  0.760  0.844  0.659  +0.0011  [+0.0001, +0.0020]    96.4%      0  <-- better
cl4                       0.8204  0.862  0.760  0.844  0.657  +0.0008  [-0.0004, +0.0020]    85.0%      0
cl4_all                   0.8218  0.863  0.764  0.843  0.657  +0.0022  [+0.0011, +0.0034]   100.0%      0  <-- better
cl4_h8                    0.8207  0.862  0.763  0.843  0.657  +0.0011  [+0.0001, +0.0022]    95.8%      0  <-- better

results: outputs/variants/v48_full_1341342961_1010-1604/results.json
```

Smoke (from this run): 0 fallback weeks in every variant, no exceptions/tracebacks in the log.

Reading (not a verdict; one root): all four cl variants are >= baseline. The best is `cl4_all` (cl_safety 4 on every
pool, not only fab grids): +0.0022 [+0.0011, +0.0034], 100% of bootstrap draws better, gain mostly in L2 (+0.004) and
L4. cl2 / cl4_h8 about +0.001 (intervals just above 0); cl4 (fab-only, hold 4) +0.0008, interval holds 0.
Far below the +0.05 bar, but in the +0.002..0.005 range the team asked for in task 47; worth pooling with another root.
