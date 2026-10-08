Status: done — kce_split (agents/mpc_fab3 + 3 new options) is +0.023 on Full dev 20 (0.8050 vs 0.7820), +0.012 on fresh Full 12, +0.016 on Small 20

## Verdict
Better at every stage, but **below the team's +0.05 bar**: Full dev 20 **0.8050 vs 0.7820, +0.023 [+0.009, +0.041]**; fresh Full 12
+0.012 [+0.006, +0.019]; Small random 20 +0.016 [+0.008, +0.023]; 0 fallbacks anywhere; CPU max 0.37 s/week on Full.
Candidate: `agents/mpc_fab3` with `params.json` = `{"kappa_lp": true, "pp_direct": ["grid_cn", "grid_eu"], "pp_split": true}`
(ready-made copy: `outputs/task-18/best_agent`). All new options are off by default; with no params.json, mpc_fab3 = mpc_bufplan + pp20.
It doesn't touch the chip LP, so it should combine with task 19 (not tested).

## Why the CN/JP/SEA fabs stayed dark, and why the pulse planner missed it (Full devpick, `outputs/task-18/diag18.py`, `lng18.py`, `crude18.py`)
1. **SEA: physically unreachable.** Crude is 3% of SEA's load and can only reach grid_sea via chk_panama -> term_sea, capacity ~13/week vs
   750 needed. SEA sheds ~2.5% every week whatever the agent does. In eps 1/26/53 SEA's gas is also cut by sanctions on au_lng -> term_sea.
   The oracle's SEA lots (4.6M) come from the base_first relaxation.
2. **CN: the rationing trap, on a lane the planner couldn't control.** CN's gas stock sits under psi*Ibar every week (shortfall ~0.8% of
   load), but most CN gas comes straight from src_ru_gas through the pipe src_ru_gas -> grid_cn (au -> term_cn is sanctioned in those
   episodes). Task 16's planner could only hold fuel at terminals, so it couldn't make the "drain, then refill above psi*Ibar, then full
   weeks" cycle. **Fix `pp_direct`**: the planner also times the rationed fuel's direct source -> grid pipes (source stock as the buffer,
   storage 15.5k = 4 weeks; lands a week later). On eps 1/53/26 CN fab energy went 3.5k->22.9k, 3.7k->19.0k, 9.1k->12.2k.
3. **The energy LP ignored chokepoint tanker throughput.** On ep 0 the Taiwan Strait (kappa_tb ~673/week) holds a 19k crude queue
   (~28 weeks) while the LP counted queued cargo as arriving after tau, so it under-shipped. **Fix `kappa_lp`**: queued tanker lots drain FIFO at
   kappa_tb (in the LP and the planner), and the LP's lanes through a chokepoint share kappa_tb each week. (A first version that also
   made new cargo wait behind the backlog was much worse: devpick replay RSS 0.764 vs 0.817; it stopped feeding the only lanes some grids have.)
4. **One release mode per week for all fuels.** A gas "recharge" week also released the crude that the next fab week needed (CN/JP/KR fabs
   were crude-short in 25-50 weeks per episode). **Fix `pp_split`**: a 5th mode (gas recharges, crude held at the terminal).
5. What remains is real scarcity: JP crude can arrive at most ~553/week vs 891 needed (Malacca + Taiwan lanes; in ep 5 Malacca's kappa
   is cut to 1000/week and shared with TW/KR gas), and JP gas is cut 20-25% by sanctions in eps 0/1/53. So JP fabs can be full in ~60% of weeks at most.

## Fab lots and shed, before vs after (Full dev 20, `outputs/task-18/report18.py`; oracle from task 17's run on the same episodes)
```
## Fab lots started per episode (mean over Full dev 20, millions)
fab                      bufplan_pp20 kappa_cneu_spl    oracle
fab_tw_leading_1                 7.52           7.47      6.40
fab_tw_mature_1                  5.64           5.66      4.27
fab_us_leading_1                 1.37           1.37      0.93
fab_kr_leading_1                 1.76           1.85      0.74
fab_kr_memory_1                 13.39          13.89     14.11
fab_us_leading_2                 1.07           1.07      0.72
fab_jp_memory_1                  2.90           3.34      6.77
fab_us_leading_3                 1.28           1.28      0.54
fab_eu_leading_1                 0.82           1.04      0.76
fab_row_leading_1                0.47           0.60      0.61
fab_cn_mature_1                 17.10          20.74     22.75
fab_us_mature_1                  6.79           6.77      2.62
fab_eu_mature_1                  6.43           8.03      4.79
fab_sea_mature_1                 1.18           1.71      4.58
fab_tw_mature_2                  5.51           5.54      4.12
fab_us_mature_2                  6.90           6.88      5.03

## Shed per grid (T USD per episode, mean; VOLL 4.125 M)
grid                     bufplan_pp20 kappa_cneu_spl    oracle
grid_tw                        0.1952         0.1940    0.1357
grid_kr                        0.3799         0.3884    0.3551
grid_jp                        0.8241         0.8194    0.7920
grid_cn                        0.7356         0.7465    0.7105
grid_us                        0.4247         0.4247    0.4200
grid_eu                        0.4675         0.4796    0.4553
grid_sea                       1.0743         1.0765    1.0799
grid_in                        0.1400         0.1395    0.1070
```
Surprise: the baseline (mpc_bufplan pp20) already starts 17.1M lots/episode at CN; task 17 measured 6.0M for mpc_buffer. So task 16's
planner had already fixed most of CN, and the CN lever left is small (20.7M now vs the oracle's 22.8M). JP memory (3.3M vs 6.8M, about
50k USD per chip) is the biggest gap left at these grids, limited by the scarcity in point 5.

## Runner tables
Full devpick (2,2,1,1), root 0 (`variants18.json`, then `variants18b.json`):
```
direct_cn                 0.8295  0.823  0.857  0.808  0.800  +0.0076  [-0.0015, +0.0157]    94.0%      0
direct_cn_eu              0.8318  0.825  0.855  0.821  0.799  +0.0099  [-0.0003, +0.0189]    94.0%      0

variant                      RSS     L1     L2     L3     L4     diff  interval               better%  fallb
bufplan_pp20              0.8219  0.828  0.836  0.795  0.786  +0.0000  [+0.0000, +0.0000]     nan%      0
direct_cn_eu              0.8318  0.825  0.855  0.821  0.799  +0.0099  [-0.0003, +0.0189]    94.0%      0
kappa                     0.8287  0.828  0.850  0.805  0.794  +0.0068  [+0.0033, +0.0106]   100.0%      0  <-- better
kappa_cn_eu               0.8356  0.831  0.865  0.812  0.798  +0.0138  [+0.0078, +0.0190]   100.0%      0  <-- better
```
Full dev 20, root 0 (`variants18b.json`, `variants18c.json`; the split variants went straight to dev 20):
```
variant                      RSS     L1     L2     L3     L4     diff  interval               better%  fallb
bufplan_pp20              0.7820  0.767  0.834  0.764  0.704  +0.0000  [+0.0000, +0.0000]     nan%      0
direct_cn_eu              0.7857  0.768  0.841  0.772  0.704  +0.0037  [-0.0012, +0.0085]    89.1%      0
kappa                     0.7902  0.778  0.841  0.770  0.709  +0.0082  [+0.0015, +0.0170]    99.9%      0  <-- better
kappa_cn_eu               0.7924  0.779  0.846  0.771  0.706  +0.0104  [+0.0028, +0.0187]    99.6%      0  <-- better

bufplan_pp20              0.7820  0.767  0.834  0.764  0.704  +0.0000  [+0.0000, +0.0000]     nan%      0
kappa_cn_eu               0.7924  0.779  0.846  0.771  0.706  +0.0104  [+0.0028, +0.0187]    99.6%      0  <-- better
kce_split                 0.8050  0.795  0.850  0.784  0.734  +0.0230  [+0.0090, +0.0411]   100.0%      0  <-- better
kce_split_H7              0.8038  0.793  0.848  0.785  0.734  +0.0218  [+0.0079, +0.0397]   100.0%      0  <-- better
```
Small random 20, entropy 289346776 (`variants18s.json`, no-harm check):
```
bufplan_pp20              0.7319  0.690  0.785  0.752  0.754  +0.0000  [+0.0000, +0.0000]     nan%      0
kappa_cn_eu               0.7323  0.695  0.784  0.741  0.754  +0.0004  [-0.0045, +0.0058]    56.0%      0
kce_split                 0.7476  0.706  0.801  0.762  0.780  +0.0157  [+0.0084, +0.0230]   100.0%      0  <-- better
```
Fresh Full 12, entropy 1777177508 (`variants18f.json`, overfitting guard; this sample has no level-4 episode):
```
bufplan_pp20              0.7797  0.850  0.622  0.505      -  +0.0000  [+0.0000, +0.0000]     nan%      0
kce_split                 0.7920  0.858  0.634  0.553      -  +0.0123  [+0.0056, +0.0193]   100.0%      0  <-- better
```

## CPU (`uv run sbf check outputs/task-18/best_agent`, this cloud machine)
- Small (budget 2 s): week 1 0.119 s, median 0.099 s, max 0.160 s. All checks passed.
- Full (budget 4 s): week 1 0.341 s, median 0.246 s, max 0.369 s. All checks passed (task 16's pp20: max 0.29 s).

## Choices made (nobody to ask)
- Went straight to Full (CN/SEA exist only there), as the task said. The split variants went from the devpick *replay* (diag18) straight
  to Full dev 20, without a devpick runner stage; dev 20 is the deciding stage anyway.
- `pp_direct` only times pipes with tau 1 that carry the grid's rationed fuel (gas). CN's nuclear pipes (tau 8) are left alone.
- `pp_split` value 2 (a 6th mode) is in the code but was only +0.002 in the replay. Not recommended.
- `pp_enum_H` 7 (with split): no gain (−0.001), so it stays at 6.
- diag18's RSS (cost_breakdown's play path) differs a little from the runner's for the same agent (0.817 vs 0.822 on devpick). I only
  compared within one path.
