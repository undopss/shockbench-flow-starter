Status: done — nothing kept (mpc_best's params.json stays as is)

Task 39A: one-at-a-time re-tune of the chip parameters of `agents/mpc_best` (branch task-38-best, params.json
unchanged). Training root `full 20261010 20` (entropy 20261010, episodes 0..19; no harm-level-4 episode was drawn).
Variants file `outputs/task-39A/v39a_train.json` (each variant = mpc_best's full params.json + the one change).

## Training root (full, entropy 20261010, 20 episodes)
```
full, entropy 20261010, 20 episodes; diff = variant - best, 90% paired interval
variant                      RSS     L1     L2     L3     L4     diff  interval               better%  fallb
best                      0.8144  0.807  0.819  0.818      -  +0.0000  [+0.0000, +0.0000]     nan%      0
wafer_buffer_2            0.7971  0.793  0.803  0.788      -  -0.0173  [-0.0236, -0.0117]     0.0%      0  <-- worse
wafer_buffer_2.5          0.8069  0.804  0.809  0.805      -  -0.0075  [-0.0128, -0.0032]     0.0%      0  <-- worse
wafer_buffer_3.5          0.8179  0.809  0.824  0.821      -  +0.0035  [+0.0011, +0.0059]    98.7%      0  <-- better
wafer_buffer_4            0.8179  0.809  0.824  0.821      -  +0.0035  [+0.0011, +0.0059]    98.7%      0  <-- better
buffer_cost_300           0.8139  0.808  0.818  0.817      -  -0.0005  [-0.0015, +0.0004]    17.1%      0
buffer_cost_3000          0.8146  0.808  0.819  0.818      -  +0.0002  [-0.0009, +0.0015]    60.0%      0
chip_H_20                 0.8111  0.805  0.815  0.814      -  -0.0033  [-0.0061, -0.0008]     1.0%      0  <-- worse
chip_H_28                 0.8155  0.808  0.821  0.818      -  +0.0010  [-0.0006, +0.0026]    84.8%      0
```
(outputs/variants/v39a_train_full_20261010_1010-0730/results.json; references took 1361 s, each variant ~150 s)

- `wafer_buffer` is monotone: smaller is clearly worse, 3.5 and 4 are **identical** (same RSS to 4 digits). Reason
  (read in chips.py ~line 583): the buffer target is `min(wafer_buffer * starts, 0.95 * storage cap)`, so from ~3.5
  weeks on the fab's wafer storage binds everywhere — 3.5 effectively means "fill wafer storage to 95%".
- `buffer_cost` flat (300 and 3000 both hold 0). `chip_H` 20 hurts, 28 holds 0 (+0.0010).
- Only winner (interval > 0): **wafer_buffer 3.5** (I took the smaller of the two equal values). With one winner the
  "combination of winners" is that same variant, already measured above, so I did not re-run it.

## Confirmation (variants file `outputs/task-39A/v39a_confirm.json`: best vs wafer_buffer 3.5)
### Full dev 20 (root 0)
```
full, entropy 0, 20 episodes; diff = variant - best, 90% paired interval
variant                      RSS     L1     L2     L3     L4     diff  interval               better%  fallb
best                      0.8454  0.850  0.874  0.810  0.767  +0.0000  [+0.0000, +0.0000]     nan%      0
wafer_buffer_3.5          0.8454  0.849  0.874  0.813  0.769  +0.0000  [-0.0028, +0.0025]    51.7%      0
```
(outputs/variants/v39a_confirm_full_0_1010-0816/results.json; the baseline reproduces task 38's 0.8454)

### Fresh root 342100426 (task 38's untouched seed), 20 episodes
```
full, entropy 342100426, 20 episodes; diff = variant - best, 90% paired interval
variant                      RSS     L1     L2     L3     L4     diff  interval               better%  fallb
best                      0.8248  0.828  0.852  0.806  0.716  +0.0000  [+0.0000, +0.0000]     nan%      0
wafer_buffer_3.5          0.8270  0.827  0.857  0.810  0.717  +0.0022  [+0.0004, +0.0040]    97.7%      0  <-- better
```
(outputs/variants/v39a_confirm_full_342100426_1010-0829/results.json)

## Verdict
**Nothing kept.** wafer_buffer 3.5 is positive on the training root (+0.0035) and on fresh 342100426 (+0.0022), but
exactly flat on Full dev 20 (+0.0000, [-0.0028, +0.0025]), so by the rule (positive on both confirmations) it is not
kept. If the team wants a lean: it never lost on any of the three sets (pooled ≈ +0.002, L1 slightly negative on dev
and fresh, gains in L2-L4), so it is a harmless optional change, far below the +0.05 bar. mpc_best's params.json
is unchanged on this branch.

## CPU (sbf check --task=full, this container, 1 dev episode)
- mpc_best (as is): week 1 0.317 s, median 0.3035 s, max 0.432 s — all checks passed (`outputs/task-39A/check_best_full.log`)
- chip_H 28: week 1 0.413 s, median 0.3589 s, max 0.512 s — all checks passed (`outputs/task-39A/check_chipH28_full.log`)
  (chip_H 28 not kept anyway.) wafer_buffer/buffer_cost don't change the LP size.

## Choices made without asking
- Did not try extra values beyond the list (e.g. 3.25) since 3.5 = storage-cap saturation and the rule is one honest
  pass; did not re-run a one-member "combination".
- `agents/mpc_best` is checked out from task-38-best onto this branch unchanged (needed by the runner).
