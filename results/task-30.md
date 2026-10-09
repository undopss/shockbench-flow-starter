Status: running Full dev 20 (qedge: +0.011 on Full devpick)

# Task 30: more power for the JP / SEA / CN fabs (`agents/mpc_jpow`)

## So far
- Baseline mpc_imit_room, Full devpick:2,2,1,1 (root 0): RSS 0.8535.
- Measure (outputs/task-30/diag30.py, src30.py, oracle30.py, cmp30.py): the oracle gets **about the same fuel** into JP/CN/SEA as we do (JP crude +9%, LNG equal) and lifts *less* at the Gulf; its JP/SEA fab power comes from timing (and the base_first relaxation), not from more fuel.
- Bug found: the tanker-queue forecast (`pplan.queue_release`, used by the energy LP and the pulse planner with kappa_lp) ignored the simulator's next-edge capacity (chokepoint.py eta_u). In ep 5 the Taiwan -> term_jp edge is cut to ~270/wk, so the planner saw ~1,800 GWh of JP crude "arriving next week" every week, never held crude, and JP fabs stayed dark for 40+ weeks.
- Fix `jp_qedge` (off by default): Full devpick **+0.0110 [+0.0038, +0.0190]** (0.8645 vs 0.8535).
- Tried and rejected: `jp_fill` crude (never hold crude at the terminal): -0.039; crude safety stock 6 weeks: +0.001 (noise); LNG safety 5 weeks: -0.000.
