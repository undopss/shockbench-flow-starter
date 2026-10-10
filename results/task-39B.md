Status: done. Verdict: nothing kept; mpc_best's energy params stay as they are

Plan: one-at-a-time sweep of mpc_best's energy params (H, safety_weeks, cover_frac, imit_burn, end_weeks) on the
training root `full 20261010 20`, then the winners' combination, confirmed once on `full 0 dev` and fresh root 342100426.

## 1. Training sweep: `full 20261010 20` (`outputs/task-39B/v39b.json`)
Baseline `agents/mpc_best` with its own params.json; each variant = that params.json + one change.
References for this root took 2131 s here; each variant ~250 s (4 jobs).
```
full, entropy 20261010, 20 episodes; diff = variant - best, 90% paired interval
variant                      RSS     L1     L2     L3     L4     diff  interval               better%  fallb
best                      0.8144  0.807  0.819  0.818      -  +0.0000  [+0.0000, +0.0000]     nan%      0
H_10                      0.8130  0.803  0.819  0.818      -  -0.0014  [-0.0043, +0.0012]    19.1%      0
H_16                      0.8143  0.808  0.818  0.819      -  -0.0001  [-0.0035, +0.0029]    46.7%      0
safety_weeks_3.0          0.8128  0.805  0.817  0.820      -  -0.0016  [-0.0036, +0.0004]     9.8%      0
safety_weeks_5.0          0.8156  0.809  0.819  0.821      -  +0.0012  [-0.0014, +0.0037]    74.4%      0
cover_frac_0.6            0.8073  0.789  0.820  0.813      -  -0.0071  [-0.0167, +0.0006]     8.3%      0
cover_frac_1.0            0.8205  0.824  0.818  0.820      -  +0.0060  [-0.0008, +0.0142]    89.1%      0
imit_burn_0.8             0.8145  0.808  0.819  0.818      -  +0.0001  [-0.0008, +0.0010]    54.1%      0
imit_burn_1.0             0.8150  0.808  0.819  0.820      -  +0.0006  [-0.0003, +0.0017]    82.6%      0
end_weeks_2.0             0.8118  0.804  0.816  0.818      -  -0.0026  [-0.0047, -0.0007]     0.9%      0  <-- worse
end_weeks_4.0             0.8141  0.808  0.817  0.818      -  -0.0003  [-0.0023, +0.0015]    36.8%      0
```
(outputs/variants/v39b_full_20261010_1010-0730/results.json)

No interval is above 0, so by the task's rule **no value is kept**. end_weeks 2 is worse (interval below 0).
H 10/16, imit_burn 0.8/1.0, end_weeks 4, safety_weeks 3/5 are flat (|diff| <= 0.0016).
cover_frac is the only one that moves: 0.6 -0.0071 (8% better), 1.0 +0.0060 [-0.0008, +0.0142] (89% better), i.e.
a monotone trend toward more cover.

## 2. Follow-up on the training root (my choice, not in the task list) (`outputs/task-39B/v39b_follow.json`)
Since cover_frac was the only parameter with a trend, I tried two larger values and a "combination of the leaners"
(cover_frac 1.0 + safety_weeks 5 + imit_burn 1.0; none of them passed the bar, so this is not the task's winners combo).
```
full, entropy 20261010, 20 episodes; diff = variant - best, 90% paired interval
variant                      RSS     L1     L2     L3     L4     diff  interval               better%  fallb
best                      0.8144  0.807  0.819  0.818      -  +0.0000  [+0.0000, +0.0000]     nan%      0
cover_frac_1.2            0.8197  0.823  0.817  0.820      -  +0.0053  [-0.0017, +0.0138]    87.2%      0
cover_frac_1.4            0.8194  0.823  0.817  0.818      -  +0.0050  [-0.0021, +0.0135]    84.8%      0
lean_combo                0.8194  0.823  0.816  0.819      -  +0.0050  [-0.0020, +0.0130]    85.0%      0
```
(outputs/variants/v39b_follow_full_20261010_1010-0900/results.json)

Plateau at about +0.005 from cover_frac >= 1.0 (all of it in harm level 1); the leaners add nothing on top.
Still no interval above 0, so **nothing is kept** by the rule.

## 3. Diagnostic confirmation of cover_frac 1.0 (not a "kept" candidate)
Because cover_frac 1.0 was the closest to the bar (89% better share), I ran it once on `full 0 dev` and fresh root
342100426 so the team knows whether the lean is real. These runs do not change the verdict above unless both are
clearly positive, and even then the gain is far under the +0.05 bar.

### full 0 dev (20)
```
full, entropy 0, 20 episodes; diff = variant - best, 90% paired interval
variant                      RSS     L1     L2     L3     L4     diff  interval               better%  fallb
best                      0.8454  0.850  0.874  0.810  0.767  +0.0000  [+0.0000, +0.0000]     nan%      0
cover_frac_1.0            0.8443  0.849  0.872  0.808  0.769  -0.0011  [-0.0019, -0.0002]     2.5%      0  <-- worse
```
(outputs/variants/v39b_conf_full_0_1010-0920/results.json)

cover_frac 1.0 is **worse** on dev 20 (-0.0011, interval below 0), so the training-root lean did not carry over.
It would have needed to be positive on both confirmations, so I **skipped the 342100426 run** (it cannot change the
verdict, and that seed stays unused by this task).

## 4. CPU (H raises the LP size)
`sbf check --task=full` (1 dev episode, this machine, budget 4 s): mpc_best (H 12) week 1 0.493 s, median 0.516 s,
max 0.819 s; mpc_best with H 16 week 1 0.636 s, median 0.555 s, max 0.869 s. Both pass. (H 16 not kept anyway.)

## Every value tried (training root full 20261010 20, diff vs mpc_best)
| param | values (diff) | kept |
|---|---|---|
| H (12) | 10 -0.0014, 16 -0.0001 | no |
| safety_weeks (4) | 3 -0.0016, 5 +0.0012 | no |
| cover_frac (0.8) | 0.6 -0.0071, 1.0 +0.0060, 1.2 +0.0053, 1.4 +0.0050 | no (1.0 worse on dev 20: -0.0011) |
| imit_burn (0.9) | 0.8 +0.0001, 1.0 +0.0006 | no |
| end_weeks (3) | 2 -0.0026 (worse), 4 -0.0003 | no |
| leaners combo | cover_frac 1.0 + safety_weeks 5 + imit_burn 1.0: +0.0050 | no |

## Verdict
The energy side of mpc_best is at a flat optimum: no listed value has an interval above 0 on the training root, the one
lean (cover_frac >= 1.0, all in harm level 1) reverses on Full dev 20, and every effect is ~10x below the +0.05 bar.
**Final kept params = mpc_best's params.json unchanged** (no combination or confirmation of winners to run).

Choices I made without asking (nobody could answer during the run):
- Ran an extra follow-up on the training root (cover_frac 1.2/1.4, leaners combo) because cover_frac was the only trend.
- Ran one diagnostic confirmation of cover_frac 1.0 on full 0 dev even though it did not pass the training bar, and
  skipped the 342100426 run once dev came out negative.
- No upload (sbf check suggests one; ignored as the rules say).
