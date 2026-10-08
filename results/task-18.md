Status: running fresh-seed Full check (full random 12); funnel done, best = kce_split +0.023 on Full dev 20

Found so far (Full devpick, outputs/task-18/diag18.py, lng18.py, crude18.py):
- SEA: crude (3% of SEA load) can only reach grid_sea via chk_panama -> term_sea, capacity ~13/week vs 750 needed: SEA's home shortfall is physical, its fabs can't be powered without the oracle's homes-first relaxation.
- JP: crude max ~553/week (malacca + taiwan lanes) vs 891 needed; the planner already alternates (fabs on every other week). LNG at JP is short 20-25% in eps 0/1/53 (sanctions on au->term_jp): unreachable.
- CN: the shortfall is the LNG rationing trap (grid stock under psi*Ibar every week, ~0.8% of load). Most CN gas arrives straight from src_ru_gas through the pipeline src_ru_gas -> grid_cn, which the pulse planner could not time (it only held fuel at terminals). That is why task 16's planner missed CN.
- Built: option `pp_direct` (grid ids) in agents/mpc_fab3: the planner also times the rationed fuel's direct source -> grid pipes (source stock = buffer, lands a week later). On eps 1/53/26: CN fab energy 3.5k->22.9k, 3.7k->19.0k, 9.1k->12.2k; cost -0.15/-0.06/-0.05 T.
- Second root cause: the energy LP ignores chokepoint tanker throughput (kappa_tb). On Full ep 0 the Taiwan Strait (kappa ~673/week) holds a 19k crude queue (~28 weeks) while the LP counts queued cargo as arriving in tau. Built option `kappa_lp`: queued tanker lots drain FIFO at kappa (pulse planner and LP), and the LP's lanes through a chokepoint share kappa each week. (A first version that also made new cargo wait behind the backlog was much worse, RSS 0.764 vs 0.817 on devpick in diag18: it stopped feeding the only lanes some grids have.)

Full devpick (2,2,1,1), baseline mpc_bufplan pp20:
```
variant                      RSS     L1     L2     L3     L4     diff  interval               better%  fallb
bufplan_pp20              0.8219  0.828  0.836  0.795  0.786  +0.0000  [+0.0000, +0.0000]     nan%      0
direct_cn_eu              0.8318  0.825  0.855  0.821  0.799  +0.0099  [-0.0003, +0.0189]    94.0%      0
kappa                     0.8287  0.828  0.850  0.805  0.794  +0.0068  [+0.0033, +0.0106]   100.0%      0  <-- better
kappa_cn_eu               0.8356  0.831  0.865  0.812  0.798  +0.0138  [+0.0078, +0.0190]   100.0%      0  <-- better
```
(first run, variants18.json: direct_cn +0.0076 [-0.0015, +0.0157], direct_cn_eu +0.0099 [-0.0003, +0.0189])

Full dev 20, baseline mpc_bufplan pp20:
```
variant                      RSS     L1     L2     L3     L4     diff  interval               better%  fallb
bufplan_pp20              0.7820  0.767  0.834  0.764  0.704  +0.0000  [+0.0000, +0.0000]     nan%      0
direct_cn_eu              0.7857  0.768  0.841  0.772  0.704  +0.0037  [-0.0012, +0.0085]    89.1%      0
kappa                     0.7902  0.778  0.841  0.770  0.709  +0.0082  [+0.0015, +0.0170]    99.9%      0  <-- better
kappa_cn_eu               0.7924  0.779  0.846  0.771  0.706  +0.0104  [+0.0028, +0.0187]    99.6%      0  <-- better
```
- Third limiter: the planner used one release mode per week for all fuels of a grid, so a gas "recharge" week also released crude that the next fab week needed. Option `pp_split`: a 5th mode (gas recharges, crude held at the terminal). diag18 replay on devpick: RSS 0.8435 vs 0.8356 (kappa_cn_eu) vs 0.817 (baseline); JP fab power share 0.44 -> 0.50, CN 0.54 -> 0.57.

Full dev 20 round 2:
```
variant                      RSS     L1     L2     L3     L4     diff  interval               better%  fallb
bufplan_pp20              0.7820  0.767  0.834  0.764  0.704  +0.0000  [+0.0000, +0.0000]     nan%      0
kappa_cn_eu               0.7924  0.779  0.846  0.771  0.706  +0.0104  [+0.0028, +0.0187]    99.6%      0  <-- better
kce_split                 0.8050  0.795  0.850  0.784  0.734  +0.0230  [+0.0090, +0.0411]   100.0%      0  <-- better
kce_split_H7              0.8038  0.793  0.848  0.785  0.734  +0.0218  [+0.0079, +0.0397]   100.0%      0  <-- better
```

Small random 20 (no-harm check, entropy 289346776):
```
variant                      RSS     L1     L2     L3     L4     diff  interval               better%  fallb
bufplan_pp20              0.7319  0.690  0.785  0.752  0.754  +0.0000  [+0.0000, +0.0000]     nan%      0
kappa_cn_eu               0.7323  0.695  0.784  0.741  0.754  +0.0004  [-0.0045, +0.0058]    56.0%      0
kce_split                 0.7476  0.706  0.801  0.762  0.780  +0.0157  [+0.0084, +0.0230]   100.0%      0  <-- better
```
A 6th planner mode (gas exact-full + crude held, pp_split 2) gave only +0.002 in the diag18 replay: not pursued.

sbf check of outputs/task-18/best_agent (= agents/mpc_fab3 + params.json {"kappa_lp": true, "pp_direct": ["grid_cn", "grid_eu"], "pp_split": true}), this cloud machine:
- Small (budget 2 s): week 1 0.119 s, median 0.099 s, max 0.160 s. All checks passed.
- Full (budget 4 s): week 1 0.341 s, median 0.246 s, max 0.369 s. All checks passed.
