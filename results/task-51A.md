Status: playing jp_pulse, safety_6 (partial table below, 2 of 4 rows)

Plan: task 51A, variants us_nobuf / jp_pulse / safety_6 vs mpc_final (final.zip params, from origin/task-51-ideas) on full root 242617957, 20 episodes.

Choices made (nobody to ask):
- Skipped the separate us_nobuf smoke on dev episode to save time for the deadline (~80 min left at start); exceptions/fallback weeks for us_nobuf are read from the main run's table instead.
- outputs/v51.json: baseline = agents/mpc_final with its own params.json; each variant = full params.json + one change.

Partial table (outputs/partial51.py, same bootstrap as variants.py), 19:13 UTC:
```
variant                     RSS     L1     L2     L3     L4     diff  interval               better%  fallb
baseline                  0.8153  0.835  0.831  0.732      -  +0.0000  [+0.0000, +0.0000]     nan%      0
us_nobuf                  0.8107  0.829  0.830  0.726      -  -0.0046  [-0.0072, -0.0022]     0.0%      0
```
us_nobuf: 0 fallback weeks and no exceptions in the run (stands in for the skipped smoke); it is worse (interval below 0).
