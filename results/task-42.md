Status: Full dev 20 done for lags 4/8/16 + mid2 (ties4 +0.0021, interval touches 0; mid2 worse); running lags 1/2/3

# Task 42: act on the announcement messages (`agents/mpc_msg`)

Baseline `agents/mpc_best` (branch task-38-best, its params.json). Only the Full dev episodes (root 0), as asked.
Note: the tgz reference cache does not match this machine's generator id (known since tasks 15/34/38), so the Full dev
20 references were rebuilt here (2501 s); J_naive / strata are the same episodes (base RSS 0.8454 = task 38's dev 20).

## 1. Measurement (Full dev 20, mpc_best)

Script `outputs/task-42/msg42.py full 0 dev agents/mpc_best 4 mil_closure,sanction,tariff` (raw rows
`msg42_full_0_dev.json`, log `msg42_dev20.log`).
- Threads: mpc_best is played as the scorer plays it and every live message is logged; a thread is "real" when a real
  omega event of its channel's type, region and target has its first announcement on that channel in the thread's first
  week (else a decoy). Lead = event onset week − week the agent first saw the thread.
- Cost: task 15's method (`voi.py`): drop the events of a class whose onset is inside the episode from omega (their
  messages go too, decoys stay), replay mpc_best and re-solve the clairvoyant LP. Ceiling of *perfect* foresight on the
  class = (J_agent − J_agent(−class)) − (J_oracle − J_oracle(−class)). RSS points use the official level weights:
  rss(J_agent − ceiling) − rss(J_agent) on the dev EpisodeSet (so a level-1 USD counts 10× a level-4 USD).
  Per-episode ceilings are noisy (mpc_best's reaction to a missing event can go either way: negative entries).

```
base: mpc_best RSS 0.8454 on 20 episodes, fallback weeks 0

message threads seen by the agent (real = matched to a real event; lead = onset week - first seen week)
  channels                           threads   /ep   real lead med     range withdrawn with stated
  mid_threat                              32   1.6  90.6%      0.0    -1..17      0.0%        0.0%
  sanction_legal                          27   1.4  48.1%      5.0      0..8      0.0%      100.0%
  sanction_legal+ties_threat              23   1.1  43.5%     11.0     6..98      0.0%      100.0%
  tariff_formal                           41   2.0  87.8%      4.5     0..32      0.0%      100.0%
  tariff_formal+tariff_final              96   4.8  75.0%      7.5     0..52      0.0%      100.0%
  tariff_informal                         36   1.8  55.6%      2.5    -1..13      0.0%      100.0%
  tariff_informal+tariff_final            79   4.0  74.7%      2.0     0..17      0.0%      100.0%
  ties_threat                            193   9.7  56.5%     16.0   -1..101      0.0%        0.0%

  mid_threat threads: target kinds {np.int64(0): np.int64(32)}, real leads [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 2, 2, 3, 3, 4, 13, 15, 17, 17]

events starting inside the episode (dev 20): count, share with a message thread the agent saw first
  energy_shock          117 ( 5.8/ep)  with a message   0.0%  lead med   nan w
  material_outage        21 ( 1.1/ep)  with a message   0.0%  lead med   nan w
  militarised_closure    29 ( 1.4/ep)  with a message 100.0%  lead med   0.0 w
  piracy                 17 ( 0.8/ep)  with a message   0.0%  lead med   nan w
  port_strike            43 ( 2.1/ep)  with a message   0.0%  lead med   nan w
  regional_conflict       7 ( 0.3/ep)  with a message   0.0%  lead med   nan w
  sanction              231 (11.6/ep)  with a message  57.1%  lead med  11.0 w
  tariff                198 ( 9.9/ep)  with a message  94.4%  lead med   4.0 w
  weather_closure        49 ( 2.5/ep)  with a message   0.0%  lead med   nan w

ceiling of perfect foresight per class (T USD/ep; RSS points with the level weights, = rss(J_agent - ceiling) - rss(J_agent))
  class        dropped/ep  dAgent T dOracle T ceiling T  RSS pts      L1      L2      L3      L4   per episode (ceiling T)
  tariff: missing episodes [7], counted as ceiling 0
  tariff              9.9     0.008     0.005     0.003  +0.0010 +0.0003 +0.0006 +0.0000 +0.0000   +0.009 +0.003 +0.004 +0.001 +0.007 +0.002 +0.014 +0.000 +0.000 +0.003 -0.000 +0.004 +0.000 +0.003 +0.000 +0.000 +0.001 +0.000 +0.000 +0.011
  sanction           11.6     0.719     0.663     0.057  +0.0171 +0.0042 +0.0089 +0.0038 +0.0003   +0.211 +0.052 +0.035 +0.028 -0.041 +0.009 +0.238 +0.000 -0.004 +0.097 -0.002 +0.040 -0.146 +0.171 -0.113 +0.328 +0.028 +0.000 -0.226 +0.426
  mil_closure         1.4     0.084     0.026     0.059  +0.0077 +0.0017 +0.0016 +0.0018 +0.0025   +0.004 +0.000 +0.000 -0.003 +0.087 +0.000 +0.000 +0.000 +0.051 +0.006 -0.079 +0.689 -0.010 +0.000 +0.000 -0.000 +0.201 +0.001 +0.146 +0.081
  (episodes in order [0, 1, 2, 3, 4, 5, 6, 7, 10, 14, 26, 41, 44, 53, 57, 61, 69, 76, 80, 102] levels [2, 2, 1, 2, 2, 1, 2, 1, 1, 1, 4, 4, 4, 3, 3, 3, 3, 3, 4, 4] )
```

Reading:
- **Tariffs: dead.** 94% are announced (lead median 4 w) and 75-88% of formal threads are real, but even perfect
  foresight of every tariff is worth **+0.0010 RSS** (0.003 T/ep). Nothing to build.
- **Militarised closures (mid_threat):** 91% of MID threads are real, but the agent sees them at lead **−1..0 weeks in
  17 of 29** (median 0): the closure is already visible in `graph_now.open`. Perfect-foresight ceiling **+0.0077 RSS**,
  ~all from ep 41 (L4, +0.69 T) and ep 69 (L3, +0.20 T), where the reachable part needs leads we mostly don't get.
  MID threats name a chokepoint (target kind 0) and no date.
- **Sanctions: the only material one.** Ceiling **+0.0171 RSS** (0.057 T/ep; L1 +0.004, L2 +0.009). 57% of sanctions
  have a thread the agent saw; TIES threats come early (median lead 16 w for real ones; `sanction_legal` 5 w, which
  `pending_prohibitions` already covers) but only **56% of TIES threads are real** (44% decoys, withdrawn only at
  their effect time, so not separable in advance). A TIES threat names one **edge** (target kind 1) and no date.
  Sanctioned edges are mostly chip-side: air/sea wafer and material lanes into fabs (mat_jp_resist → fab_kr/us,
  mat_cn_neon → fab_kr, mat_de_wafer → fab_us_mature), fab → OSAT lanes, plus AU LNG → JP/KR/SEA terminals.
- **Costly events with no message at all** (dev 20, per episode): energy shocks 5.8, weather closures 2.5, port
  strikes 2.1, material outages 1.1, piracy 0.8, regional conflicts 0.3 — never announced on any channel (by design:
  `codes.TYPE_CHANNELS`); and 43% of sanctions had no thread.

## 2. Decision
Rough ceiling = true-alarm × usable-lead × cost: sanctions 0.017 × ~0.5 (seen ahead) × ~0.56 (real) ≈ +0.005 RSS,
MID ≈ 0.0077 × (12/29 with lead ≥ 1) ≈ +0.003, tariffs ≪ 0.003. So sanctions (TIES threats) are worth one build,
MID threats a cheap one, tariffs none.

## 3. Build: `agents/mpc_msg` = mpc_best + `_msg_obs` (agent.py; off by default, mpc_best behaviour unchanged)
- `msg_ties_lag` L (0 = off): every live, not withdrawn TIES threat naming an edge becomes a pending prohibition of
  every commodity of that edge from week max(t + 1, announced_week + L). Both LPs (energy and chips) already plan
  around `pending_prohibitions` (pre-ship ahead, avoid the lane), so the change is one obs augmentation.
- `msg_mid_score` s (0 = off): a live MID threat naming a chokepoint raises its warning score to ≥ s; with mpc_best's
  `warn_gain` 0.5 the energy LP cuts the chokepoint's lanes from next week by 0.5·s (s = 2: closed).
- Smoke (`outputs/task-42/smoke42.py`): ep 0 with L = 8 adds 403 pending (edge, k, week) entries over 104 weeks, ep 41
  with s = 2 raises 290 chokepoint-week scores; 0 errors, 0 fallbacks.

## 4. Variants (vs `{"agent": "agents/mpc_best"}`; each = mpc_best's params.json + one change)

Probe, devpick:2,2,1,1 (the runner was stopped by my 10-min timeout before `mid2`; mid2 is in the dev-20 run):
```
round v42a_full_0_1010-1106: task full, entropy 0, episodes devpick:2,2,1,1, baseline best
references ready in 2 s (6 episodes)
  played best in 116 s: RSS 0.8864
  played ties4 in 107 s: RSS 0.8922
  played ties8 in 106 s: RSS 0.8899
  played ties16 in 115 s: RSS 0.8903
  played mid1 in 113 s: RSS 0.8865
/home/user/shockbench-flow-starter/.venv/lib/python3.13/site-packages/joblib/externals/loky/backend/resource_tracker.py:359: UserWarning: resource_tracker: There appear to be 10 leaked semlock objects to clean up at shutdown
  warnings.warn(
/home/user/shockbench-flow-starter/.venv/lib/python3.13/site-packages/joblib/externals/loky/backend/resource_tracker.py:359: UserWarning: resource_tracker: There appear to be 7 leaked folder objects to clean up at shutdown
  warnings.warn(
```

Full dev 20:
```
round v42b_full_0_1010-1116: task full, entropy 0, episodes dev, baseline best
references ready in 2 s (20 episodes)
  played best in 266 s: RSS 0.8454
  played ties4 in 271 s: RSS 0.8475
  played ties8 in 276 s: RSS 0.8463
  played ties16 in 267 s: RSS 0.8463
  played mid2 in 268 s: RSS 0.8442

full, entropy 0, 20 episodes; diff = variant - best, 90% paired interval
variant                      RSS     L1     L2     L3     L4     diff  interval               better%  fallb
best                      0.8454  0.850  0.874  0.810  0.767  +0.0000  [+0.0000, +0.0000]     nan%      0
ties4                     0.8475  0.852  0.877  0.811  0.769  +0.0021  [-0.0002, +0.0046]    92.5%      0
ties8                     0.8463  0.851  0.875  0.811  0.768  +0.0009  [-0.0008, +0.0025]    81.0%      0
ties16                    0.8463  0.851  0.875  0.811  0.769  +0.0009  [-0.0006, +0.0026]    81.0%      0
mid2                      0.8442  0.848  0.873  0.810  0.768  -0.0012  [-0.0025, -0.0001]     3.4%      0  <-- worse

results: outputs/variants/v42b_full_0_1010-1116/results.json
```
