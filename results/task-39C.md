Status: training sweep done; confirming pulse_weeks 1.0 on full 0 dev and fresh root 342100426

# Task 39C: re-tune the pulse / JP parameters of `agents/mpc_best`

Agent: `agents/mpc_best` from `task-38-best` (params.json:
`{"kappa_lp": true, "pp_direct": ["grid_cn", "grid_eu"], "pp_split": true, "sell_end": true, "imit_grid": "room", "jp_qedge": true, "jp_arrfb": 0.2, "fb_kappa_ct": true, "safety_weeks": 4.0, "pp_end": 0.7, "warn_gain": 0.5, "cq_edges": true, "cq_drain": true, "cq_kappa": true, "nd_open": true}`).
Each variant = that params.json + one change (`outputs/task-39C/v39c.json`).

## 1. Training root: `full 20261010 20` (references built here in 1635 s)
```
full, entropy 20261010, 20 episodes; diff = variant - best, 90% paired interval
variant                      RSS     L1     L2     L3     L4     diff  interval               better%  fallb
best                      0.8144  0.807  0.819  0.818      -  +0.0000  [+0.0000, +0.0000]     nan%      0
pulse_weeks_1.0           0.8147  0.807  0.819  0.819      -  +0.0003  [+0.0001, +0.0005]    99.0%      0  <-- better
pulse_weeks_2.0           0.8133  0.806  0.817  0.818      -  -0.0011  [-0.0016, -0.0006]     0.0%      0  <-- worse
jp_arrfb_0.1              0.8137  0.808  0.817  0.819      -  -0.0007  [-0.0024, +0.0006]    20.6%      0
jp_arrfb_0.35             0.8127  0.806  0.817  0.817      -  -0.0017  [-0.0029, -0.0006]     0.2%      0  <-- worse
pp_end_0.5                0.8148  0.809  0.818  0.817      -  +0.0004  [-0.0014, +0.0021]    63.6%      0
pp_end_0.9                0.8129  0.807  0.816  0.818      -  -0.0015  [-0.0036, +0.0006]    10.9%      0
pp_H_6                    0.8144  0.807  0.819  0.818      -  +0.0000  [+0.0000, +0.0000]     0.0%      0
pp_H_10                   0.8144  0.807  0.819  0.818      -  +0.0000  [+0.0000, +0.0000]     0.0%      0
```
(`outputs/task-39C/results_train.json`; no level-4 episode was drawn on this root.)

- Only winner (interval > 0): **pulse_weeks 1.0**, +0.0003 — far below the +0.05 bar, a near-flat parameter.
- The current values of jp_arrfb (0.2) and pp_end (0.7) are at or near the top; moving away is flat or worse.
- **pp_H is a no-op** with the default `pp_method: "enum"`: `PulsePlanner._enum` uses `H = min(enum_H, H)` = 6, and
  pp_H only lengthens the arrivals window beyond what enum reads. Same J on every episode for 6, 8 and 10, so no CPU
  check was needed (play is identical; pp_H would matter only with `pp_method: "milp"`).
- Combination of winners = pulse_weeks 1.0 alone (a single winner), so the training-root "combination" run is the
  row above; it went straight to the two confirmations.
