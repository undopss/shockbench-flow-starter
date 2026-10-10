Status: Full root done; running small 0 dev

# Task 44A — final candidate on fresh root 540469033

## 2. Full, root 540469033, 20 episodes (4 jobs)

```
full, entropy 540469033, 20 episodes; diff = variant - mpc_best, 90% paired interval
variant                      RSS     L1     L2     L3     L4     diff  interval               better%  fallb
mpc_best                  0.8589  0.866  0.829  0.885      -  +0.0000  [+0.0000, +0.0000]     nan%      0
final                     0.8605  0.869  0.829  0.885      -  +0.0016  [-0.0001, +0.0033]    93.5%      0
final_cap                 0.8603  0.868  0.829  0.885      -  +0.0015  [-0.0002, +0.0031]    92.5%      0
final_scen                0.8613  0.869  0.831  0.884      -  +0.0025  [+0.0002, +0.0047]    96.4%      0  <-- better
final_cap_scen            0.8613  0.869  0.831  0.884      -  +0.0025  [+0.0004, +0.0045]    97.6%      0  <-- better
```
No harm-level-4 episode was drawn in these 20 (L4 column empty). Wall: mpc_best 206 s, final 201 s, final_cap 193 s, final_scen 500 s, final_cap_scen see log.

## 1. Smoke + J reproduction (full 0 devpick:1,0,0,0, the first L1 dev episode)

J reproduction: **equal**. mpc_pleak (own params.json) J = 472673747613092; mpc_final with mpc_pleak's params.json
J = 472673747613092 (identical, cents). The code-review fixes are neutral on this episode.
Smoke: 0 fallback weeks in all 6 runs, no traceback/exception in the log.

```
full, entropy 0, 1 episodes; diff = variant - pleak, 90% paired interval
variant                      RSS     L1     L2     L3     L4     diff  interval               better%  fallb
pleak                     0.8871  0.887      -      -      -  +0.0000  [+0.0000, +0.0000]     nan%      0
final_pleakparams         0.8871  0.887      -      -      -  +0.0000  [+0.0000, +0.0000]     0.0%      0
final                     0.8881  0.888      -      -      -  +0.0010  [+0.0010, +0.0010]   100.0%      0  <-- better
final_cap                 0.8874  0.887      -      -      -  +0.0003  [+0.0003, +0.0003]   100.0%      0  <-- better
final_scen                0.8902  0.890      -      -      -  +0.0031  [+0.0031, +0.0031]   100.0%      0  <-- better
final_cap_scen            0.8895  0.890      -      -      -  +0.0025  [+0.0025, +0.0025]   100.0%      0  <-- better

results: outputs/variants/smoke_full_0_1010-1224/results.json
```
(per-episode wall: final/final_cap ~33 s, scen variants ~95 s.)
Note: building the reference for this one dev episode took 1865 s here although cache/sbf-cache.tgz was unpacked
(joblib _cuts_compute missed and was recomputed).
