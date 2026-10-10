# Task 51F: two more ideas on final.zip, root 722245388, 20 Full episodes

**Status: DONE** (table printed 19:08 UTC). Neither variant separates from final: both 90% paired intervals hold 0.
tw_safety_7 -0.0007 [-0.0030, +0.0012]; pulse_w075 +0.0006 [-0.0005, +0.0016] (better on 79.6% of bootstraps).
0 fallback weeks everywhere. Not uploaded.

Command: `uv run python outputs/variants.py full 722245388 20 outputs/v51b.json 4`
(references 1273 s; each variant ~300 s.)

```
full, entropy 722245388, 20 episodes; diff = variant - final, 90% paired interval
variant                      RSS     L1     L2     L3     L4     diff  interval               better%  fallb
final                     0.8663  0.876  0.874  0.901  0.509  +0.0000  [+0.0000, +0.0000]     nan%      0
tw_safety_7               0.8656  0.874  0.876  0.901  0.501  -0.0007  [-0.0030, +0.0012]    32.9%      0
pulse_w075                0.8669  0.877  0.875  0.902  0.501  +0.0006  [-0.0005, +0.0016]    79.6%      0
```

Choices: variants.py writes "params" as the whole params.json (no merge), so each variant in `outputs/v51b.json` is
the full agents/mpc_final/params.json (from origin/task-51-ideas) plus its one change. 4 jobs (nproc = 4).
