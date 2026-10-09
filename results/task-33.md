Status: running Full devpick 6 (stage 1: 12 single changes vs mpc_imit_room)

Plan: `agents/mpc_final` = copy of `agents/mpc_imit_room` + the `fb_kappa_ct` option from task-25-feedback (chip LP
knows container queues drain at kappa_ct; off by default). Test (a) pulse_grids TW+KR+JP+SEA, (b) fb_kappa_ct,
(c) imit_target, (d) one-at-a-time sweep on Full devpick (pp_value 10/40 [20], pulse_weeks 1.0/2.0 [1.5],
wafer_buffer 2/4 [3], buffer_cost 500/2000 [1000], pp_direct + JP/SEA [CN, EU]); then stack the positives, Full dev 20,
fresh Full seed 12.

Notes:
- The repo's `cache/sbf-cache.tgz` did NOT match this environment's Full instance digest (cached `93b801effce44fbf`,
  here `7740c8824dd9c8ed`), so the Full dev references were rebuilt (1541 s for all 20 dev episodes on 4 cores).
