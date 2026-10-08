Status: Small 20 done; running Full dev 20 (clim_off, risk_safety, all_clim, sw5)

Plan: measure disruption statistics on 300 own-root episodes (Full and Small), build agents/mpc_clim (climate options off by default) and run the funnel vs mpc_fab3sell.

- (a) `closure_end` is **never shown** in the scored regime (`standard`, theta.chi = False): 0 observed entries in 5 Full + 5 Small gym episodes with 428 + 232 closed chokepoint-weeks. Impossible to use.
- (b) statistics done (outputs/task-27/climate_*_300.txt, hazard.txt). Energy sources never lose supply; open straits almost never close (≤2% within 12 weeks); a freshly closed big strait reopens within 4 weeks ~50% of the time, after 3+ weeks closed only ~10-20%.

- Full 6 (devpick:2,2,1,1) vs `clim_off` (= mpc_fab3sell with its params.json): reopen −0.002, risk-based safety +0.006, flat safety_weeks 5 +0.008. Tables: outputs/task-27/run_full6*.txt. NB: `variants.py` drops params.json, so a plain `agents/mpc_fab3sell` baseline plays without its params (0.822 vs 0.850 on Full 6).

- Small random 20 (root 1604362749) vs clim_off: reopen +0.002, reopen+derate +0.0045, risk_safety +0.007, sw5 +0.0015.
