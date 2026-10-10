Status: done. Neither leaner confirmed on root 995215227: ovf +0.0005 [-0.0003, +0.0012] (holds 0), ties4 -0.0010 [-0.0020, -0.0001] (worse), ovf_ties4 -0.0002. Recommendation: keep the uploaded mpc_final as is.

# Task 45A — stack leaners on mpc_final, root 995215227

Code: `agents/mpc_final` = task-44-final (bb9674a) + `msg_ties_lag` ported from agents/mpc_msg (task 42), TIES part
only (`msg_mid_score` not ported, the task asked for ties). Default 0; with 0 the new `_msg_obs` is never called.
params.json unchanged (still the uploaded one).

## 1. J reproduction (full 0 devpick:1,0,0,0)

With the uploaded params (pp_scen_K 8) the J is **not** identical, and with pp_scen_K 0 it **is** identical:

```
full, entropy 0, episodes devpick:1,0,0,0, baseline final_unchanged
references ready in 1808 s (1 episodes)
  played final_unchanged in 66 s: RSS 0.8902
  played final_ported in 66 s: RSS 0.8905
  played ties4 in 70 s: RSS 0.8883

full, entropy 0, 1 episodes; diff = variant - final_unchanged, 90% paired interval
variant                      RSS     L1     L2     L3     L4     diff  interval               better%  fallb
final_unchanged           0.8902  0.890      -      -      -  +0.0000  [+0.0000, +0.0000]     nan%      0
final_ported              0.8905  0.890      -      -      -  +0.0003  [+0.0003, +0.0003]   100.0%      0  <-- better
ties4                     0.8883  0.888      -      -      -  -0.0019  [-0.0019, -0.0019]     0.0%      0  <-- worse
```
J: final_unchanged 471653178604352, final_ported 471559576107768.

```
full, entropy 0, episodes devpick:1,0,0,0, baseline unchanged_K0
references ready in 1 s (1 episodes)
  played unchanged_K0 in 29 s: RSS 0.8881
  played ported_K0 in 28 s: RSS 0.8881

full, entropy 0, 1 episodes; diff = variant - unchanged_K0, 90% paired interval
variant                      RSS     L1     L2     L3     L4     diff  interval               better%  fallb
unchanged_K0              0.8881  0.888      -      -      -  +0.0000  [+0.0000, +0.0000]     nan%      0
ported_K0                 0.8881  0.888      -      -      -  +0.0000  [+0.0000, +0.0000]     0.0%      0
```
J: unchanged_K0 472343460048138 = ported_K0 472343460048138 (identical, cents).

Why: the scenario-pulse sampler (pplan.py:529) is seeded from `config["policy_seed"]`, and the scorer salts
policy_seed with the submission's sha256 (sbf check says so). Any byte change in the zip (here the port; in
variants.py also each variant's params.json) reseeds the K=8 scenarios. With the sampler off the port is exactly
neutral. Side finding: on this episode a pure reseed moved RSS by +0.0003 — the same size as the ovf effect below,
so differences of a few 1e-4 between pp_scen_K variants are partly seed noise.

## 2. Full, root 995215227, 20 episodes (4 jobs)

```
full, entropy 995215227, episodes 20, baseline final
references ready in 1417 s (20 episodes)
  played final in 432 s: RSS 0.8613
  played ovf in 442 s: RSS 0.8618
  played ties4 in 430 s: RSS 0.8603
  played ovf_ties4 in 477 s: RSS 0.8611

full, entropy 995215227, 20 episodes; diff = variant - final, 90% paired interval
variant                      RSS     L1     L2     L3     L4     diff  interval               better%  fallb
final                     0.8613  0.888  0.881  0.763  0.753  +0.0000  [+0.0000, +0.0000]     nan%      0
ovf                       0.8618  0.887  0.885  0.762  0.752  +0.0005  [-0.0003, +0.0012]    85.9%      0
ties4                     0.8603  0.887  0.880  0.763  0.750  -0.0010  [-0.0020, -0.0001]     4.2%      0  <-- worse
ovf_ties4                 0.8611  0.886  0.881  0.763  0.761  -0.0002  [-0.0016, +0.0011]    41.4%      0
```
References for this new root took 1417 s (the dev reference for the smoke 1808 s: joblib cache miss, as in 44A).
Wall per variant ~430-480 s. 0 fallback weeks everywhere.

## 3. Rehearsal (baseline mpc_final from the run above)

```
per-episode RSS of mpc_final (baseline), full 995215227
all   n=20 min 0.692 p10 0.752 med 0.892 p90 0.925 max 0.928 mean 0.865
L1    n=10 min 0.764 p10 0.869 med 0.892 p90 0.918 max 0.925 mean 0.886
L2    n= 7 min 0.735 p10 0.821 med 0.902 p90 0.927 max 0.928 mean 0.880
L3    n= 2 min 0.692 p10 0.706 med 0.761 p90 0.817 max 0.831 mean 0.761
L4    n= 1 min 0.753 p10 0.753 med 0.753 p90 0.753 max 0.753 mean 0.753
excluded: []

ep  L   RSS     naive USD      oracle USD     agent USD      gap-to-oracle USD   harm USD
 0  3  0.6917       8.262e+12      5.473e+12      6.333e+12        8.6e+11      5.522e+12
12  2  0.7346       8.294e+12      4.833e+12      5.752e+12      9.185e+11       5.04e+12
17  4  0.7534        1.03e+13      6.261e+12      7.258e+12      9.968e+11      6.981e+12
15  1  0.7641       8.174e+12       4.63e+12      5.466e+12      8.359e+11      3.822e+12
10  3  0.8309       1.037e+13      7.438e+12      7.934e+12      4.957e+11      6.249e+12
 7  2  0.8783       5.531e+12      3.355e+12      3.619e+12      2.648e+11      4.254e+12
 3  1  0.8801       5.806e+12      3.078e+12      3.405e+12       3.27e+11      3.705e+12
 8  2  0.8814       6.963e+12        3.3e+12      3.734e+12      4.346e+11      4.316e+12
 4  1  0.8833       6.736e+12      4.546e+12      4.801e+12      2.556e+11      3.672e+12
16  1  0.8914       5.784e+12      2.479e+12      2.838e+12       3.59e+11      3.093e+12
 2  1  0.8921       6.981e+12      3.099e+12      3.518e+12       4.19e+11      1.657e+12
 1  1  0.8929        3.54e+12      2.103e+12      2.257e+12      1.539e+11      2.306e+12
18  2  0.9017        6.24e+12      3.366e+12      3.648e+12      2.824e+11      4.111e+12
11  1  0.9027       9.394e+12      4.673e+12      5.132e+12      4.595e+11      1.623e+12
 9  1  0.9083       8.114e+12      5.172e+12      5.441e+12      2.697e+11      3.775e+12
14  2  0.9101       6.123e+12      3.069e+12      3.344e+12      2.746e+11      4.957e+12
 6  1  0.9167       5.171e+12      1.647e+12      1.941e+12      2.935e+11      3.264e+12
19  1  0.9250       7.366e+12      2.225e+12      2.611e+12      3.857e+11      2.206e+12
13  2  0.9259       7.934e+12      2.803e+12      3.184e+12      3.804e+11      4.678e+12
 5  2  0.9284       7.651e+12      4.616e+12      4.833e+12      2.173e+11      5.047e+12
```

3 worst (0 L3, 12 L2, 17 L4) and 3 best (5, 13 L2; 19 L1) replayed with outputs/task-17/gap17.py + task-41 map41.py
(`outputs/task-45A/map45.txt`; the replay uses the NO_ZIP policy seed, so J differs from the run by <0.1%; the
"pts" column is weighted within these 6 episodes only, use the items):

```
Per-episode: RSS points lost (x100), episode RSS, J gap T, top 4 items (T)
  ep 19 L1 pts  4.371 RSS_e 0.926 gap 0.381  short/le/a_notmade -0.489, short/le/b_disposed +0.290, short/le/c_endstock +0.110, shed/eu +0.106
  ep  0 L3 pts  2.956 RSS_e 0.692 gap 0.858  shed/tw +0.156, shed/cn +0.151, short/le/b_disposed +0.147, shed/jp +0.119
  ep 12 L2 pts  2.038 RSS_e 0.744 gap 0.887  short/le/a_notmade +0.660, short/mat/a_notmade -0.349, short/mat/b_disposed +0.169, shed/kr -0.112
  ep 17 L4 pts  1.109 RSS_e 0.761 gap 0.966  short/le/b_disposed +0.430, short/le/a_notmade +0.176, shed/tw +0.076, short/mat/b_disposed +0.072
  ep 13 L2 pts  0.907 RSS_e 0.923 gap 0.395  short/le/b_disposed +0.141, short/le/c_rest +0.099, short/le/a_notmade -0.079, shed/tw +0.075
  ep  5 L2 pts  0.483 RSS_e 0.931 gap 0.210  short/le/a_notmade -0.596, short/le/b_disposed +0.422, short/le/c_endstock +0.107, short/le/c_rest +0.073
```
Reading: the worst episodes are chip (le = leading-edge) lost sales from lots disposed / not made and grid shed in
TW/CN/JP (ep 0, L3: shed tw/cn/jp + disposed le chips); ep 12 (L2): le chips not made; ep 17 (L4): le chips disposed.
Pooled over the 6: shortage 62% and shed 31% of the gap to the oracle; freight/tariff/holding/disposal < 3% each.
Even the best episodes lose mostly on le chip disposal/end stock.

Fallback / CPU from the run: 0 fallback weeks in all 80 episode-plays. The runner does not record per-week CPU, so
per-week CPU comes from sbf check (below): Full median act 0.59-0.61 s, max 0.86-0.92 s (budget 4 s).

## 4. sbf check (best variant = ovf params; copy in outputs/task-45A/mpc_final_ovf)

| check | week 1 | median act | max | result |
|---|---|---|---|---|
| ovf params, `--task=full` | 0.363 s | 0.590 s | 0.860 s | all checks passed |
| ovf params, `--task=small` | 0.138 s | 0.427 s | 0.570 s | all checks passed |
| mpc_final own params (ported code), `--task=full` | 0.331 s | 0.605 s | 0.921 s | all checks passed |

(1 dev episode each, this cloud machine; budgets Small 2 s / Full 4 s.)

## Choices made (nobody to ask)
- Ported only `msg_ties_lag` (not `msg_mid_score`), per the task text.
- J reproduction: since exact equality failed with pp_scen_K 8, I added a second smoke with pp_scen_K 0 on both
  sides to show the port is neutral; the difference with K 8 is the sha-salted seed, not the code path.
- "Best variant" for step 4 = ovf (highest diff, though its interval holds 0).
- Rehearsal breakdown done on 6 episodes only (3 worst + 3 best) to keep within the 1.5 h deadline.
- No PR opened (the scheduled prompt asked only for pushes to task-45A-stack). Not uploaded.
