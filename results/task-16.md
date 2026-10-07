Status: sbf check (CPU) on pp20

## Small random 20 (entropy 148337082)
```
small, entropy 148337082, 20 episodes; diff = variant - mpc_buffer, 90% paired interval
variant                      RSS     L1     L2     L3     L4     diff  interval               better%  fallb
mpc_buffer                0.7441  0.667  0.775  0.849  0.799  +0.0000  [+0.0000, +0.0000]     nan%      0
pp20                      0.7694  0.724  0.781  0.835  0.832  +0.0253  [+0.0110, +0.0401]   100.0%      0  <-- better
pp50                      0.7697  0.724  0.782  0.835  0.832  +0.0256  [+0.0111, +0.0404]   100.0%      0  <-- better

results: outputs/variants/v16_small_small_148337082_1007-2102/results.json
```
Both all-grid planners pass Small (+0.025, interval above 0).
