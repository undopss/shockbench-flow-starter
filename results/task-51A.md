Status: done (19:27 UTC). No variant beats final.zip on root 242617957: us_nobuf is worse, jp_pulse and safety_6 are indistinguishable from it (both point estimates slightly below).

Final table as printed (outputs/variants.py full 242617957 20 outputs/v51.json 4):
```
full, entropy 242617957, 20 episodes; diff = variant - baseline, 90% paired interval
variant                      RSS     L1     L2     L3     L4     diff  interval               better%  fallb
baseline                  0.8153  0.835  0.831  0.732      -  +0.0000  [+0.0000, +0.0000]     nan%      0
us_nobuf                  0.8107  0.829  0.830  0.726      -  -0.0046  [-0.0072, -0.0022]     0.0%      0  <-- worse
jp_pulse                  0.8149  0.835  0.831  0.731      -  -0.0004  [-0.0013, +0.0004]    23.3%      0
safety_6                  0.8132  0.835  0.829  0.725      -  -0.0021  [-0.0051, +0.0008]    12.7%      0

results: outputs/variants/v51_full_242617957_1010-1828/results.json
```

Timings: references 1712 s, then ~460 s per variant (4 jobs).

Choices made (nobody to ask):
- Skipped the separate us_nobuf smoke on dev episode 1,0,0,0 to keep time for the deadline; the main run shows 0 fallback weeks and no exceptions for us_nobuf.
- outputs/v51.json: baseline = agents/mpc_final (from origin/task-51-ideas) with its own params.json; each variant = full params.json + one change.
- L4 shows '-' because this root's 20 episodes have no harm-level-4 episode (as printed by the runner).
- Not uploaded.
