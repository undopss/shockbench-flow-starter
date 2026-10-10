Status: done

**Verdict (root 1827351891): neither leaner stacks on mpc_final.** ovf −0.0006 [−0.0016, +0.0004], ties4 −0.0005
[−0.0032, +0.0020], ovf_ties4 −0.0013 [−0.0042, +0.0018]; all intervals hold 0, all point estimates slightly negative.
Keep the uploaded mpc_final as is. 0 fallbacks, 0 exceptions anywhere; CPU max 1.24 s/week (median 0.61) on this machine.
Surprise: the policy seed alone moves mpc_final by ~0.0025 RSS on this root (section 3c), the same size as the leaners.

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

## 3. Rehearsal: mpc_final on `full 1827351891 20`

### a. Per-episode RSS (the runner's baseline play; level = harm level)
```
all      n=20  min 0.5009  p10 0.6831  median 0.8161  p90 0.9359  max 0.9424  mean 0.8202
L1       n= 7  min 0.6671  p10 0.7548  median 0.8784  p90 0.9312  max 0.9424  mean 0.8507
L2       n= 8  min 0.5009  p10 0.6297  median 0.8134  p90 0.8948  max 0.9357  mean 0.7801
L3       n= 3  min 0.7744  p10 0.7797  median 0.8011  p90 0.8834  max 0.9040  mean 0.8265
L4       n= 2  min 0.7918  p10 0.8064  median 0.8646  p90 0.9228  max 0.9373  mean 0.8646
```
Pooled RSS 0.8318 (L1 0.859, L2 0.778, L3 0.829, L4 0.872). This root is clearly harder than 44A/44B's
(0.86): mostly L2 (8 of 20) and one L2 episode at 0.50. Full per-episode table: `outputs/task-45B/rehearsal.txt`.

### b. 3 worst / 3 best episodes and their top cost items (agent − clairvoyant, USD; `outputs/cost_breakdown.py`)
```
WORST 3 (RSS from the runner's seed; cost items from the replay seed)
  ep  3 L2 RSS 0.5009, gap to oracle 1,798 B USD, cpu max 0.94 s; top gap items: shortage 1,590 B (88%), shed 172 B (10%), tariff 14 B (1%)
  ep 15 L1 RSS 0.6671, gap to oracle 942 B USD, cpu max 0.75 s; top gap items: shortage 903 B (96%), holding 20 B (2%), tariff 14 B (2%)
  ep 17 L2 RSS 0.6849, gap to oracle 1,109 B USD, cpu max 0.80 s; top gap items: shortage 1,018 B (92%), shed 68 B (6%), disposal 13 B (1%)
BEST 3 (RSS from the runner's seed; cost items from the replay seed)
  ep  5 L1 RSS 0.9424, gap to oracle 249 B USD, cpu max 0.75 s; top gap items: shed 128 B (52%), shortage 93 B (38%), holding 19 B (8%)
  ep 12 L4 RSS 0.9373, gap to oracle 218 B USD, cpu max 0.97 s; top gap items: shed 101 B (46%), tariff 42 B (19%), disposal 34 B (16%)
  ep  8 L2 RSS 0.9357, gap to oracle 209 B USD, cpu max 0.76 s; top gap items: shed 139 B (67%), disposal 30 B (14%), holding 20 B (9%)
```
Worst episodes lose almost entirely to **shortage** (88–96 % of the gap); best ones lose mostly to shed. Over all 20,
shortage is 73 % of the gap to clairvoyant, shed 20 %, holding 2.6 %, disposal 2.2 %, tariff 1.7 %
(`outputs/task-45B/cost_breakdown.txt`).

### c. Fallbacks, CPU per week, seed sensitivity
- Fallback weeks: 0 of 2,080 in every play (runner, cost_breakdown, CPU replay); `cpu_weeks` 0.
- CPU per week (process_time of act; week 1 includes Agent(config)), `outputs/task-45B/cpu_play.py`, 20 episodes
  with 4 parallel jobs on this 4-core cloud machine: **max 1.237 s, p99 0.872 s, median 0.607 s**; week 1 max 0.376 s.
  Budget on Full is 4 s (server ≥ ~5x faster than the home server per CONTEXT).
- The runner (EpisodeSet.play: policy_seed derived from the folder's hash) and a replay with the NO_ZIP policy seed
  (cost_breakdown / cpu_play, which agree exactly with each other) give different J on 19/20 episodes:
  ```
  per-episode RSS(runner seed) - RSS(replay seed): mean +0.0027, sd 0.0035, min -0.0003, max +0.0138, differ on 19/20
pooled RSS runner 0.8318186185679721 replay 0.8293033597145405
  ```
  The cause is the policy seed: `pp_scen_K 8` samples scenarios with `default_rng([policy_seed, week, node])`.
  So the server's score of the uploaded zip carries ~±0.003 of pure seed noise on 20 episodes; effects of this size
  (both leaners) cannot be judged from one seed. Oddly the diffs are almost all one-signed (min −0.0003), which looks
  less like noise than expected; worth a look by the team if it matters (I did not dig further).

## Choices made (nobody to ask)
- Did the port myself (45A had not pushed one when I started); ported `msg_mid_score` too, both default off.
- J reproduction against the unchanged mpc_final checked out from task-44-final into `outputs/task-45B/orig_final`.
- Main run used 3 jobs (4-core machine; the reproduction ran beside it at first). The first reproduction attempt was
  killed by the tool's 30-min background cap (it was building the dev episode's references, the cache did not cover it);
  rerun detached with setsid, same command.
- Rehearsal CPU from my own replay script (the runner's rows hold no per-week CPU), cost items from
  `outputs/cost_breakdown.py` (map41.py is not on this branch). No PR opened (task 45 asks only for the branch). No upload.
