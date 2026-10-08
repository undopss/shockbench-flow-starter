Status: running Full devpick test (direct-pipe pulse at CN, CN+EU)

Found so far (Full devpick, outputs/task-18/diag18.py, lng18.py, crude18.py):
- SEA: crude (3% of SEA load) can only reach grid_sea via chk_panama -> term_sea, capacity ~13/week vs 750 needed: SEA's home shortfall is physical, its fabs can't be powered without the oracle's homes-first relaxation.
- JP: crude max ~553/week (malacca + taiwan lanes) vs 891 needed; the planner already alternates (fabs on every other week). LNG at JP is short 20-25% in eps 0/1/53 (sanctions on au->term_jp): unreachable.
- CN: the shortfall is the LNG rationing trap (grid stock under psi*Ibar every week, ~0.8% of load). Most CN gas arrives straight from src_ru_gas through the pipeline src_ru_gas -> grid_cn, which the pulse planner could not time (it only held fuel at terminals). That is why task 16's planner missed CN.
- Built: option `pp_direct` (grid ids) in agents/mpc_fab3: the planner also times the rationed fuel's direct source -> grid pipes (source stock = buffer, lands a week later). On eps 1/53/26: CN fab energy 3.5k->22.9k, 3.7k->19.0k, 9.1k->12.2k; cost -0.15/-0.06/-0.05 T.
