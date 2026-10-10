Status: running main test (baseline played: mpc_final RSS 0.8318 on root 1827351891; 3 variants playing)

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
