Status: done

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
No harm-level-4 episode was drawn in these 20 (L4 column empty). Wall: mpc_best 206 s, final 201 s, final_cap 193 s, final_scen 500 s, final_cap_scen 492 s.

## 3. No-harm: small 0 dev (20 episodes)

```
small, entropy 0, 20 episodes; diff = variant - mpc_best, 90% paired interval
variant                      RSS     L1     L2     L3     L4     diff  interval               better%  fallb
mpc_best                  0.8042  0.835  0.764  0.828  0.685  +0.0000  [+0.0000, +0.0000]     nan%      0
final                     0.8072  0.839  0.766  0.832  0.686  +0.0030  [+0.0002, +0.0064]    96.5%      0  <-- better
final_cap                 0.8064  0.837  0.766  0.832  0.686  +0.0022  [-0.0000, +0.0049]    94.5%      0
final_scen                0.8076  0.837  0.771  0.830  0.681  +0.0034  [-0.0013, +0.0080]    88.6%      0
final_cap_scen            0.8083  0.838  0.770  0.833  0.685  +0.0041  [+0.0017, +0.0067]    99.7%      0  <-- better
```

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

## 4. Checks (this cloud machine, 4 vCPU; 1 dev episode each)

| agent / params | task | week 1 (init + act) | median act | max act | budget | result |
|---|---|---|---|---|---|---|
| mpc_final (params.json as is) | full | 0.406 s | 0.390 s | 0.581 s | 4 s | all checks passed |
| mpc_final + pl_ucap + pp_scen_K 8 | full | 0.481 s | 0.929 s | 1.377 s | 4 s | all checks passed |
| mpc_final (params.json as is) | small | 0.222 s | 0.121 s | 0.222 s | 2 s | all checks passed |
| mpc_final + pl_ucap + pp_scen_K 8 | small | 0.195 s | 0.694 s | 0.892 s | 2 s | all checks passed |

Full output: `outputs/task-44A/checks.log`.

Guard test `outputs/task-34/guard_test.py 0 agents/mpc_final` (exit 0):
```
A J 465024298066392 fallback_weeks 0
B J 465024298066392 fallback_weeks 0
C components: True True True
C J 467367227590693 fallback_weeks 0
D J 467367227590693 fallback_weeks 0
```
A = B and C = D as required.

Pack: `uv run sbf pack mpc_final` -> outputs/mpc_final.zip (not committed, outputs/*.zip is gitignored), 5 files,
117,724 bytes unpacked, **sha256 88e9fb07df2855425bbb9aa2179f09c3571a9f1b303b75c6b078d1874406eb21**
(params.json as shipped: pl_ucap and pp_scen_K off). The final_cap_scen folder would be
e85326ed634b8d34a8e8ef41d7acd47683522e0e7e687753c6cac53a3eb9a08b. **Not uploaded.**

## Choices I made (no one to ask)

- Smoke and J reproduction done in one runner call (baseline mpc_pleak with its own params.json, then mpc_final with
  mpc_pleak's params, then the four variants) on `full 0 devpick:1,0,0,0`.
- `small 0 dev` no-harm run uses the same variants.json as the Full root (baseline mpc_best, 4 variants).
- sbf check for final_cap_scen: a copy of agents/mpc_final with the changed params.json in
  `outputs/task-44A/mpc_final_cap_scen/`.
