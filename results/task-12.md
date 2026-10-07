Status: Full dev 20: wafer buffer 3 weeks +0.061 vs mpc_pulse (0.7363 vs 0.6752, CI +0.049..+0.075, 20/20 better); next: sbf check, Small + fresh-seed check

Plan: measure wasted fab power (a), fuel disposal at fab grids/terminals (b), near-full-load shortfall weeks (c) for mpc_pulse on Full devpick:2,2,1,1, convert to lost chip USD, build only if >= ~0.17 T USD/episode.

Diagnostic: `outputs/task-12/waste.py` (logs every allocate_energy call during the rollout).
