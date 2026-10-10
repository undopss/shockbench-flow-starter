Status: running Full dev 20

## 1. Build + reproduction
`agents/mpc_best` = `agents/mpc_combo` (agent.py, pplan.py, fallback.py) + mpc_nodisp's chips.py changes (cq_edges,
cq_drain, cq_kappa, nd_open, nd_openq, sell_buffer args) merged by hand into combo's chips.py (fb_kappa_ct), with
a three-way merge against mpc_jpow (the common source) and each of the 9 conflicts resolved by hand; agent.py gets
nodisp's PARAMS (all off) and ChipPlanner arguments, plus `nd_open_e` (off). Where both chip-queue models apply
(fb_kappa_ct and cq_drain on), cq_drain's schedule (next edge + kappa_ct) is used for the arrivals, and kappa_ct's
cumulative LP rows (queue0) are kept alongside cq_kappa's per-week rows. Diagnostic `self.last` of task 37 dropped.

params.json: `{"kappa_lp": true, "pp_direct": ["grid_cn", "grid_eu"], "pp_split": true, "sell_end": true, "imit_grid": "room", "jp_qedge": true, "jp_arrfb": 0.2, "fb_kappa_ct": true, "safety_weeks": 4.0, "pp_end": 0.7, "warn_gain": 0.5, "cq_edges": true, "cq_drain": true, "cq_kappa": true, "nd_open": true}`

Reproduction, Full dev devpick:1,0,0,0 (`outputs/task-38/run_repro.log`):
- mpc_combo J = 476070749797006; mpc_best with combo's params.json J = 476070749797006 (exact).
- mpc_nodisp J = 476787324292725; mpc_best with nodisp's params.json J = 476787324292725 (exact).
- mpc_best (all) J = 473182951504551 (RSS 0.8855 vs combo 0.8766). 0 fallbacks.

Smoke (`outputs/task-38/smoke38.py full 0 3`, all options on): chip LP solved 104/104 weeks, 0 exceptions, 0 None,
CPU mean 0.163 s, max 0.433 s.
