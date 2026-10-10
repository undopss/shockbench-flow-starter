Status: running sbf check + guard + pack

## 1. Build + reproduction
`agents/mpc_best` = `agents/mpc_combo` (agent.py, pplan.py, fallback.py) + mpc_nodisp's chips.py changes (cq_edges,
cq_drain, cq_kappa, nd_open, nd_openq, sell_buffer args) merged by hand into combo's chips.py (fb_kappa_ct), with
a three-way merge against mpc_jpow (the common source) and each of the 9 conflicts resolved by hand; agent.py gets
nodisp's PARAMS (all off) and ChipPlanner arguments, plus `nd_open_e` (off). Where both chip-queue models apply
(fb_kappa_ct and cq_drain on), cq_drain's schedule (next edge + kappa_ct) is used for the arrivals, and kappa_ct's
cumulative LP rows (queue0) are kept alongside cq_kappa's per-week rows. Diagnostic `self.last` of task 37 dropped.

params.json: `{"kappa_lp": true, "pp_direct": ["grid_cn", "grid_eu"], "pp_split": true, "sell_end": true, "imit_grid": "room", "jp_qedge": true, "jp_arrfb": 0.2, "fb_kappa_ct": true, "safety_weeks": 4.0, "pp_end": 0.7, "warn_gain": 0.5, "cq_edges": true, "cq_drain": true, "cq_kappa": true, "nd_open": true}`

Reproduction, Full dev devpick:1,0,0,0 (`outputs/task-38/run_repro.log`):
- mpc_combo J = 476070749797006; mpc_best with combo's params.json J = 476070749797006 (exact).
- mpc_nodisp J = 476787324292725; mpc_best with nodisp's params.json J = 476787324292725 (exact).
- mpc_best (all) J = 473182951504551 (RSS 0.8855 vs combo 0.8766). 0 fallbacks.

Smoke (`outputs/task-38/smoke38.py full 0 3`, all options on): chip LP solved 104/104 weeks, 0 exceptions, 0 None,
CPU mean 0.163 s, max 0.433 s.

## 2. Variants vs `{"agent": "agents/mpc_combo"}` (`outputs/task-38/v38.json`)

### Full dev 20 (root 0)
```
full, entropy 0, 20 episodes; diff = variant - combo, 90% paired interval
variant                      RSS     L1     L2     L3     L4     diff  interval               better%  fallb
combo                     0.8322  0.837  0.857  0.799  0.761  +0.0000  [+0.0000, +0.0000]     nan%      0
best                      0.8454  0.850  0.874  0.810  0.767  +0.0132  [+0.0082, +0.0187]   100.0%      0  <-- better
best_no_nd                0.8399  0.848  0.862  0.807  0.761  +0.0077  [+0.0044, +0.0112]   100.0%      0  <-- better
nodisp                    0.8456  0.855  0.872  0.802  0.764  +0.0134  [+0.0073, +0.0196]   100.0%      0  <-- better

```

### task full, entropy 540469033, episodes 20
```
full, entropy 540469033, 20 episodes; diff = variant - combo, 90% paired interval
variant                      RSS     L1     L2     L3     L4     diff  interval               better%  fallb
combo                     0.8482  0.853  0.823  0.875      -  +0.0000  [+0.0000, +0.0000]     nan%      0
best                      0.8589  0.866  0.829  0.885      -  +0.0107  [+0.0078, +0.0142]   100.0%      0  <-- better
best_no_nd                0.8571  0.865  0.826  0.881      -  +0.0089  [+0.0060, +0.0123]   100.0%      0  <-- better
nodisp                    0.8543  0.862  0.823  0.882      -  +0.0061  [+0.0004, +0.0114]    96.0%      0  <-- better

```
(outputs/variants/v38_full_540469033_1010-0704/results.json)

### task full, entropy 1730880025, episodes 20
```
full, entropy 1730880025, 20 episodes; diff = variant - combo, 90% paired interval
variant                      RSS     L1     L2     L3     L4     diff  interval               better%  fallb
combo                     0.8444  0.836  0.855  0.854      -  +0.0000  [+0.0000, +0.0000]     nan%      0
best                      0.8562  0.852  0.863  0.858      -  +0.0118  [+0.0055, +0.0191]   100.0%      0  <-- better
best_no_nd                0.8537  0.850  0.860  0.855      -  +0.0093  [+0.0032, +0.0167]   100.0%      0  <-- better
nodisp                    0.8557  0.851  0.866  0.855      -  +0.0114  [+0.0033, +0.0203]    99.6%      0  <-- better

```
(outputs/variants/v38_full_1730880025_1010-0723/results.json)

### task full, entropy 910653604, episodes 20
```
full, entropy 910653604, 20 episodes; diff = variant - combo, 90% paired interval
variant                      RSS     L1     L2     L3     L4     diff  interval               better%  fallb
combo                     0.8364  0.805  0.883  0.832  0.779  +0.0000  [+0.0000, +0.0000]     nan%      0
best                      0.8485  0.822  0.892  0.843  0.781  +0.0122  [+0.0087, +0.0160]   100.0%      0  <-- better
best_no_nd                0.8457  0.817  0.889  0.844  0.782  +0.0093  [+0.0064, +0.0129]   100.0%      0  <-- better
nodisp                    0.8470  0.815  0.893  0.844  0.787  +0.0106  [+0.0060, +0.0160]   100.0%      0  <-- better

```
(outputs/variants/v38_full_910653604_1010-0742/results.json)

### task full, entropy 342100426, episodes 20
```
full, entropy 342100426, 20 episodes; diff = variant - combo, 90% paired interval
variant                      RSS     L1     L2     L3     L4     diff  interval               better%  fallb
combo                     0.8149  0.815  0.841  0.801  0.714  +0.0000  [+0.0000, +0.0000]     nan%      0
best                      0.8248  0.828  0.852  0.806  0.716  +0.0099  [+0.0073, +0.0125]   100.0%      0  <-- better
best_no_nd                0.8221  0.825  0.851  0.800  0.716  +0.0072  [+0.0046, +0.0096]   100.0%      0  <-- better
nodisp                    0.8276  0.826  0.860  0.811  0.716  +0.0126  [+0.0088, +0.0166]   100.0%      0  <-- better

```
(outputs/variants/v38_full_342100426_1010-0800/results.json)

### task small, entropy 0, episodes dev
```
small, entropy 0, 20 episodes; diff = variant - combo, 90% paired interval
variant                      RSS     L1     L2     L3     L4     diff  interval               better%  fallb
combo                     0.8003  0.839  0.760  0.807  0.677  +0.0000  [+0.0000, +0.0000]     nan%      0
best                      0.8042  0.835  0.764  0.828  0.685  +0.0039  [-0.0011, +0.0088]    90.0%      0
best_no_nd                0.7958  0.836  0.753  0.802  0.670  -0.0045  [-0.0067, -0.0026]     0.0%      0  <-- worse
nodisp                    0.8026  0.836  0.759  0.829  0.683  +0.0023  [-0.0032, +0.0084]    75.1%      0

```
(outputs/variants/v38_small_0_1010-0819/results.json)
