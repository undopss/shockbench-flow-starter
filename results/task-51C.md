Status: 4-episode table done (root 722245388, episodes 0-3); now extending to 12 episodes

## Table: full 722245388, 4 episodes (first 4 of the 20-episode root; episode seeds depend only on root + index, so they pool)
```
full, entropy 722245388, 4 episodes; diff = variant - mpc_final, 90% paired interval
variant                      RSS     L1     L2     L3     L4     diff  interval               better%  fallb
mpc_final                 0.8738  0.871      -  0.880      -  +0.0000  [+0.0000, +0.0000]     nan%      0
us_nobuf                  0.8663  0.869      -  0.859      -  -0.0075  [-0.0145, -0.0018]     0.3%      0  <-- worse
jp_pulse                  0.8752  0.872      -  0.883      -  +0.0014  [+0.0002, +0.0026]    96.7%      0  <-- better
safety_6                  0.8761  0.873      -  0.884      -  +0.0023  [-0.0010, +0.0046]    94.8%      0

results: outputs/variants/v51_full_722245388_1010-1838/results.json
```
Choices made (nobody to ask): one Full reference build took 771 s for 4 episodes on this 4-core machine, so 20 episodes
(~65 min of references alone) did not fit the 19:50 UTC deadline; ran 4 first, then a 12-episode run.
Smoke on full 0 devpick:1,0,0,0 was cut (it spent 10 min building references); us_nobuf played 4 Full episodes here with
0 exceptions / 0 fallbacks, which covers the smoke's purpose.
