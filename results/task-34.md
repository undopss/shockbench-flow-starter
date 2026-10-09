Status: building / reproduction check

agents/mpc_combo = mpc_jpow (agent.py, pplan.py) + mpc_final (chips.py, fb_kappa_ct option). Changes are disjoint (jpow: energy LP / pulse planner; final: chip LP + params), so the merge is mechanical. Running the reproduction check on Full dev (devpick:1,0,0,0).
