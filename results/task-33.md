Status: stage 1 done (only fb_kappa_ct positive); running stage 2 sweep on top of kct (Full devpick 6)

Plan: `agents/mpc_final` = copy of `agents/mpc_imit_room` + the `fb_kappa_ct` option from task-25-feedback (chip LP
knows container queues drain at kappa_ct; off by default). Test (a) pulse_grids TW+KR+JP+SEA, (b) fb_kappa_ct,
(c) imit_target, (d) one-at-a-time sweep on Full devpick (pp_value 10/40 [20], pulse_weeks 1.0/2.0 [1.5],
wafer_buffer 2/4 [3], buffer_cost 500/2000 [1000], pp_direct + JP/SEA [CN, EU]); then stack the positives, Full dev 20,
fresh Full seed 12.

Notes:
- The repo's `cache/sbf-cache.tgz` did NOT match this environment's Full instance digest (cached `93b801effce44fbf`,
  here `7740c8824dd9c8ed`), so the Full dev references were rebuilt (1541 s for all 20 dev episodes on 4 cores).

## Stage 1: Full devpick 6 (entropy 0, devpick:2,2,1,1), `outputs/task-33/v33_s1.json`, round v33_s1_full_0_1009-0803
```
full, entropy 0, 6 episodes; diff = variant - base, 90% paired interval
variant                      RSS     L1     L2     L3     L4     diff  interval               better%  fallb
base                      0.8535  0.845  0.875  0.842  0.846  +0.0000  [+0.0000, +0.0000]     nan%      0
a_pulse4                  0.8513  0.842  0.875  0.837  0.846  -0.0022  [-0.0036, -0.0008]     0.0%      0  <-- worse
b_kct                     0.8555  0.846  0.882  0.839  0.846  +0.0020  [+0.0011, +0.0030]   100.0%      0  <-- better
c_target                  0.8505  0.841  0.873  0.840  0.844  -0.0030  [-0.0045, -0.0016]     0.0%      0  <-- worse
d_ppv10                   0.8527  0.845  0.875  0.839  0.844  -0.0008  [-0.0015, +0.0000]    25.5%      0
d_ppv40                   0.8520  0.842  0.875  0.842  0.846  -0.0015  [-0.0032, +0.0001]    18.9%      0
d_pw1.0                   0.8535  0.845  0.875  0.842  0.846  +0.0000  [+0.0000, +0.0000]     0.0%      0
d_pw2.0                   0.8535  0.845  0.875  0.842  0.846  +0.0000  [+0.0000, +0.0000]     0.0%      0
d_wb2                     0.8397  0.839  0.869  0.802  0.818  -0.0138  [-0.0249, -0.0041]     0.0%      0  <-- worse
d_wb4                     0.8516  0.839  0.877  0.843  0.850  -0.0019  [-0.0093, +0.0064]    24.9%      0
d_bc500                   0.8535  0.845  0.874  0.843  0.846  -0.0000  [-0.0004, +0.0004]    25.5%      0
d_bc2000                  0.8533  0.846  0.874  0.840  0.846  -0.0002  [-0.0011, +0.0007]    32.1%      0
d_ppd_all                 0.8535  0.845  0.875  0.842  0.846  +0.0000  [+0.0000, +0.0000]     0.0%      0

```
- pulse_weeks 1.0/2.0 and pp_direct + JP/SEA: bit-identical to the baseline. The pulse planner (pulse_plan, every fab
  grid) overwrites the simple pulse's releases, so `pulse_weeks` is dead; JP/SEA have no direct pipelines it times.
- (a) pulse_grids TW+KR+JP+SEA: worse (-0.0022) on this agent (its +0.0098 was on mpc_pulse, before the planner).
- (c) imit_target: worse (-0.0030), as in task 26. (d) wafer_buffer 2: much worse (-0.0138).
