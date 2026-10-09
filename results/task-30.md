Status: Small no-harm check + sbf check (qedge_fb2: dev 20 +0.0091, fresh +0.0061)

# Task 30: more power for the JP / SEA / CN fabs (`agents/mpc_jpow`)

## So far
- Baseline mpc_imit_room, Full devpick:2,2,1,1 (root 0): RSS 0.8535.
- Measure (outputs/task-30/diag30.py, src30.py, oracle30.py, cmp30.py): the oracle gets **about the same fuel** into JP/CN/SEA as we do (JP crude +9%, LNG equal) and lifts *less* at the Gulf; its JP/SEA fab power comes from timing (and the base_first relaxation), not from more fuel.
- Bug found: the tanker-queue forecast (`pplan.queue_release`, used by the energy LP and the pulse planner with kappa_lp) ignored the simulator's next-edge capacity (chokepoint.py eta_u). In ep 5 the Taiwan -> term_jp edge is cut to ~270/wk, so the planner saw ~1,800 GWh of JP crude "arriving next week" every week, never held crude, and JP fabs stayed dark for 40+ weeks.
- Fix `jp_qedge` (off by default): Full devpick **+0.0110 [+0.0038, +0.0190]** (0.8645 vs 0.8535).
- Tried and rejected: `jp_fill` crude (never hold crude at the terminal): -0.039; crude safety stock 6 weeks: +0.001 (noise); LNG safety 5 weeks: -0.000.
- Full dev 20 (root 0): base 0.8228, **qedge 0.8278, +0.0051 [+0.0007, +0.0096]**, 97.8% better; qedge + crude safety 6 weeks -0.0006 [-0.0142, +0.0107].
- Fresh Full seed, **root 213168154** (random), 12 episodes: base 0.8401, **qedge 0.8429, +0.0028 [-0.0058, +0.0098]**, 71.9% better (L4 +0.026, L3 +0.010, L1/L2 0).
- Second option `jp_arrfb` 0.2 (pulse planner scales future arrivals by the running arrived/forecast ratio): qedge_fb2 = Full devpick +0.0134 [+0.0028, +0.0253], **dev 20 0.8319, +0.0091 [+0.0033, +0.0149]**, **fresh 213168154: 0.8462, +0.0061 [+0.0008, +0.0113]**.
