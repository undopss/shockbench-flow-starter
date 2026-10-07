Status: Full 6: wafer buffer 2 weeks +0.074 vs mpc_pulse (CI +0.070..+0.079); running bigger buffers + Full dev 20

Plan: measure wasted fab power (a), fuel disposal at fab grids/terminals (b), near-full-load shortfall weeks (c) for mpc_pulse on Full devpick:2,2,1,1, convert to lost chip USD, build only if >= ~0.17 T USD/episode.

Diagnostic: `outputs/task-12/waste.py` (logs every allocate_energy call during the rollout).
