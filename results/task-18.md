Status: running Full dev 20 (kappa_lp + pp_direct CN/EU)

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
