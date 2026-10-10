Status: done (table printed 19:20 UTC)

Run: `uv run python outputs/variants.py full 242617957 20 outputs/v51b.json 4` (v51b.json copied to results/task-51D-v51b.json; full final params + one change each).

```
round v51b_full_242617957_1010-1829: task full, entropy 242617957, episodes 20, baseline final
references ready in 1642 s (20 episodes)
  played final in 439 s: RSS 0.8153
  played tw_safety_7 in 442 s: RSS 0.8147
  played pulse_w075 in 461 s: RSS 0.8148

full, entropy 242617957, 20 episodes; diff = variant - final, 90% paired interval
variant                      RSS     L1     L2     L3     L4     diff  interval               better%  fallb
final                     0.8153  0.835  0.831  0.732      -  +0.0000  [+0.0000, +0.0000]     nan%      0
tw_safety_7               0.8147  0.835  0.831  0.730      -  -0.0006  [-0.0017, +0.0008]    22.5%      0
pulse_w075                0.8148  0.835  0.830  0.731      -  -0.0005  [-0.0020, +0.0006]    25.7%      0

results: outputs/variants/v51b_full_242617957_1010-1829/results.json
```
