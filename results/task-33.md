Status: fresh seed done; mpc_final = stack3; running Small dev no-harm check, then sbf check

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
- pulse_weeks 1.0/2.0 and pp_direct + JP/SEA: same RSS as the baseline to 4 decimals. Likely reason (not verified
  line by line): the pulse planner overwrites the simple pulse's TW/KR releases, so `pulse_weeks` has no effect there;
  JP/SEA have no direct pipelines for the planner to time. Adding JP/SEA to pulse_grids does change play, so the simple
  pulse is not overwritten everywhere at JP/SEA.
- (a) pulse_grids TW+KR+JP+SEA: worse (-0.0022) on this agent (its +0.0098 was on mpc_pulse, before the planner).
- (c) imit_target: worse (-0.0030), as in task 26. (d) wafer_buffer 2: much worse (-0.0138).

## Stage 2: params on top of kct, Full devpick 6, `outputs/task-33/v33_s2.json`, round v33_s2_full_0_1009-0849
Ranges tried (defaults in brackets): wafer_buffer 2.5/3.5 [3], safety_weeks 2/4 [3], cover_frac 0.6 [0.8], end_weeks 2 [3],
pp_H 10 [8], pp_end 0.7/1.1 [0.9], imit_burn 0.8/1.0 [0.9], chip_H 30 [24], safety_cost 0.5 [0.2], warn_gain 0.5 [0].
```
full, entropy 0, 6 episodes; diff = variant - base, 90% paired interval
variant                      RSS     L1     L2     L3     L4     diff  interval               better%  fallb
base                      0.8535  0.845  0.875  0.842  0.846  +0.0000  [+0.0000, +0.0000]     nan%      0
kct                       0.8555  0.846  0.882  0.839  0.846  +0.0020  [+0.0011, +0.0030]   100.0%      0  <-- better
k_wb3.5                   0.8538  0.842  0.878  0.845  0.848  +0.0003  [-0.0038, +0.0045]    76.5%      0
k_wb2.5                   0.8566  0.854  0.882  0.831  0.828  +0.0031  [+0.0015, +0.0049]   100.0%      0  <-- better
k_sw2                     0.8480  0.846  0.878  0.811  0.836  -0.0055  [-0.0094, -0.0019]     0.0%      0  <-- worse
k_sw4                     0.8576  0.847  0.879  0.853  0.840  +0.0041  [-0.0020, +0.0109]    81.0%      0
k_cf0.6                   0.8559  0.848  0.881  0.840  0.839  +0.0024  [+0.0008, +0.0043]   100.0%      0  <-- better
k_end2                    0.8529  0.848  0.879  0.825  0.848  -0.0006  [-0.0013, +0.0001]     5.8%      0
k_ppH10                   0.8555  0.846  0.882  0.839  0.846  +0.0020  [+0.0011, +0.0030]   100.0%      0  <-- better
k_ppend0.7                0.8566  0.850  0.878  0.841  0.847  +0.0031  [+0.0024, +0.0039]   100.0%      0  <-- better
k_ppend1.1                0.8259  0.828  0.849  0.796  0.785  -0.0276  [-0.0442, -0.0122]     0.0%      0  <-- worse
k_iburn0.8                0.8549  0.845  0.882  0.839  0.846  +0.0014  [+0.0011, +0.0018]   100.0%      0  <-- better
k_iburn1.0                0.8550  0.845  0.883  0.839  0.846  +0.0015  [+0.0011, +0.0020]   100.0%      0  <-- better
k_chipH30                 0.8537  0.844  0.882  0.837  0.837  +0.0002  [-0.0017, +0.0022]    62.3%      0
k_safc0.5                 0.8544  0.850  0.876  0.834  0.841  +0.0009  [-0.0027, +0.0040]    74.5%      0
k_warn0.5                 0.8569  0.844  0.875  0.861  0.849  +0.0034  [+0.0017, +0.0051]   100.0%      0  <-- better

```
Over kct (+0.0020) the gains are all small: warn_gain 0.5 +0.0014, pp_end 0.7 +0.0011, wafer_buffer 2.5 +0.0011
(but L3/L4 down), safety_weeks 4 +0.0021 (wide interval). pp_end 1.1 is very bad (-0.0276), safety_weeks 2 bad.

## Stage 3: stacks, Full devpick 6, `outputs/task-33/v33_s3.json`, round v33_s3_full_0_1009-0909
stack3 = kct + safety_weeks 4 + pp_end 0.7 + warn_gain 0.5.
```
full, entropy 0, 6 episodes; diff = variant - base, 90% paired interval
variant                      RSS     L1     L2     L3     L4     diff  interval               better%  fallb
base                      0.8535  0.845  0.875  0.842  0.846  +0.0000  [+0.0000, +0.0000]     nan%      0
kct                       0.8555  0.846  0.882  0.839  0.846  +0.0020  [+0.0011, +0.0030]   100.0%      0  <-- better
k_ppend0.5                0.8584  0.856  0.877  0.839  0.842  +0.0049  [+0.0030, +0.0070]   100.0%      0  <-- better
k_warn1.0                 0.8569  0.846  0.875  0.860  0.836  +0.0034  [-0.0002, +0.0066]    94.0%      0
k_sw5                     0.8649  0.857  0.875  0.873  0.841  +0.0114  [+0.0092, +0.0137]   100.0%      0  <-- better
stack3                    0.8677  0.857  0.882  0.876  0.847  +0.0142  [+0.0124, +0.0161]   100.0%      0  <-- better
stack3_wb2.5              0.8609  0.854  0.873  0.866  0.826  +0.0074  [+0.0053, +0.0097]   100.0%      0  <-- better
stack3_cf0.6              0.8683  0.859  0.881  0.877  0.839  +0.0148  [+0.0125, +0.0173]   100.0%      0  <-- better
stack3_ib1.0              0.8674  0.856  0.882  0.876  0.847  +0.0139  [+0.0117, +0.0163]   100.0%      0  <-- better
stack_all                 0.8618  0.857  0.872  0.869  0.818  +0.0083  [+0.0057, +0.0112]   100.0%      0  <-- better
s2_pe_wg                  0.8600  0.848  0.879  0.863  0.840  +0.0065  [+0.0037, +0.0095]   100.0%      0  <-- better

```
safety_weeks keeps paying as it grows (2: -0.0055, 4: +0.0041, 5: +0.0114 vs base); pp_end 0.5 > 0.7. wafer_buffer
2.5 and the all-in stack hurt L4.

## Stage 4: safety_weeks range, Full devpick 6, `outputs/task-33/v33_s4.json`, round v33_s4_full_0_1009-0919
```
full, entropy 0, 6 episodes; diff = variant - base, 90% paired interval
variant                      RSS     L1     L2     L3     L4     diff  interval               better%  fallb
base                      0.8535  0.845  0.875  0.842  0.846  +0.0000  [+0.0000, +0.0000]     nan%      0
k_sw6                     0.8622  0.856  0.873  0.868  0.834  +0.0087  [+0.0064, +0.0114]   100.0%      0  <-- better
k_sw8                     0.8729  0.871  0.879  0.879  0.827  +0.0194  [+0.0133, +0.0262]   100.0%      0  <-- better
k_sw10                    0.8594  0.858  0.862  0.869  0.823  +0.0059  [+0.0021, +0.0093]   100.0%      0  <-- better
k_sw6_pe0.5               0.8651  0.857  0.876  0.873  0.840  +0.0116  [+0.0087, +0.0148]   100.0%      0  <-- better
k_sw6_pe0.5_wg0.5         0.8649  0.854  0.875  0.880  0.841  +0.0114  [+0.0101, +0.0129]   100.0%      0  <-- better
k_sw8_pe0.5_wg0.5         0.8703  0.865  0.876  0.882  0.837  +0.0168  [+0.0112, +0.0231]   100.0%      0  <-- better
k_sw5_pe0.5_wg0.5         0.8646  0.855  0.875  0.877  0.843  +0.0111  [+0.0080, +0.0145]   100.0%      0  <-- better
k_sw6_pe0.3_wg0.5         0.8645  0.854  0.878  0.876  0.839  +0.0110  [+0.0083, +0.0142]   100.0%      0  <-- better
k_sw6_pe0.5_wg0.5_cf0.6   0.8656  0.857  0.874  0.881  0.833  +0.0121  [+0.0102, +0.0141]   100.0%      0  <-- better
k_sw6_pe0.5_wg0.5_sc0.5   0.8659  0.856  0.877  0.878  0.843  +0.0124  [+0.0104, +0.0146]   100.0%      0  <-- better

```
safety_weeks is not monotone on 6 episodes (5: +0.011, 6: +0.009, 8: +0.019, 10: +0.006); L4 drops as it grows.

## Full dev 20, `outputs/task-33/v33_dev20.json`, round v33_dev20_full_0_1009-0931
```
full, entropy 0, 20 episodes; diff = variant - base, 90% paired interval
variant                      RSS     L1     L2     L3     L4     diff  interval               better%  fallb
base                      0.8228  0.821  0.858  0.791  0.755  +0.0000  [+0.0000, +0.0000]     nan%      0
kct                       0.8251  0.823  0.863  0.790  0.757  +0.0023  [+0.0011, +0.0036]    99.9%      0  <-- better
k_sw5                     0.8241  0.821  0.859  0.798  0.753  +0.0014  [-0.0054, +0.0072]    65.5%      0
k_sw8                     0.8283  0.832  0.860  0.794  0.741  +0.0056  [-0.0019, +0.0127]    88.3%      0
stack3                    0.8270  0.826  0.861  0.797  0.757  +0.0043  [+0.0003, +0.0082]    96.4%      0  <-- better
k_sw6_pe0.5_wg0.5         0.8240  0.821  0.857  0.800  0.756  +0.0013  [-0.0049, +0.0079]    62.5%      0
k_sw8_pe0.5_wg0.5         0.8256  0.825  0.858  0.800  0.749  +0.0028  [-0.0057, +0.0117]    68.0%      0

```
The devpick gains of the safety_weeks variants mostly vanish on dev 20 (devpick fit). kct and stack3 stay above 0.

## Guard (renamed / missing grid names), `outputs/task-33/guard_test.py`, Full dev episode 0
```
A J 483699973623863 fallback_weeks 0   params as shipped
B J 483699973623863 fallback_weeks 0   + "grid_nope" in pulse_grids and pp_direct  -> identical to A
C J 480973011179722 fallback_weeks 0   config with grid_cn renamed everywhere (planners all built: True True True)
D J 480973011179722 fallback_weeks 0   pp_direct without grid_cn                      -> identical to C
```
Missing grid names are skipped silently; no crash, no fallback week. No code change was needed.

## Fresh Full seed, entropy 1255168353 (random), 12 episodes, round v33_fresh_full_1255168353_1009-0954
```
full, entropy 1255168353, 12 episodes; diff = variant - base, 90% paired interval
variant                      RSS     L1     L2     L3     L4     diff  interval               better%  fallb
base                      0.8110  0.798  0.862  0.817  0.478  +0.0000  [+0.0000, +0.0000]     nan%      0
kct                       0.8132  0.801  0.866  0.815  0.479  +0.0022  [-0.0012, +0.0054]    85.2%      0
stack3                    0.8139  0.801  0.868  0.812  0.492  +0.0029  [-0.0019, +0.0081]    84.0%      0
k_sw8                     0.8128  0.804  0.869  0.792  0.493  +0.0018  [-0.0054, +0.0082]    66.5%      0

```
All three positive in point estimate, every interval holds 0.
