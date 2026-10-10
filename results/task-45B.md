Status: main test done (no variant helps); rehearsal cost breakdown running

## 1. Port + J reproduction (full 0 devpick:1,0,0,0)

`msg_ties_lag` (and its sibling `msg_mid_score`, both default off) ported from agents/mpc_msg (task-42-msg) into
agents/mpc_final (commit 865c24c). J reproduction: **equal**. Unchanged mpc_final (task-44-final) J = 471653178604352;
ported mpc_final with msg_ties_lag 0 J = 471653178604352. 0 fallbacks, no exceptions.

```
full, entropy 0, 1 episodes; diff = variant - orig, 90% paired interval
variant                      RSS     L1     L2     L3     L4     diff  interval               better%  fallb
orig                      0.8902  0.890      -      -      -  +0.0000  [+0.0000, +0.0000]     nan%      0
ported0                   0.8902  0.890      -      -      -  +0.0000  [+0.0000, +0.0000]     0.0%      0
ties4                     0.8887  0.889      -      -      -  -0.0015  [-0.0015, -0.0015]     0.0%      0  <-- worse
```

## 2. Variants vs mpc_final, `full 1827351891 20` (3 jobs; references 827 s; 0 exceptions, 0 fallbacks)

```
full, entropy 1827351891, 20 episodes; diff = variant - mpc_final, 90% paired interval
variant                      RSS     L1     L2     L3     L4     diff  interval               better%  fallb
mpc_final                 0.8318  0.859  0.778  0.829  0.872  +0.0000  [+0.0000, +0.0000]     nan%      0
ovf                       0.8312  0.859  0.776  0.829  0.874  -0.0006  [-0.0016, +0.0004]    14.7%      0
ties4                     0.8313  0.858  0.777  0.832  0.873  -0.0005  [-0.0032, +0.0020]    37.9%      0
ovf_ties4                 0.8306  0.858  0.774  0.834  0.869  -0.0013  [-0.0042, +0.0018]    24.6%      0
```
Play time for 20 episodes (3 jobs): mpc_final 430 s, ovf 419 s, ties4 409 s, ovf_ties4 412 s.
Results: `outputs/task-45B/main_results.json` (copy of outputs/variants/variants_full_1827351891_1010-1440/results.json).
