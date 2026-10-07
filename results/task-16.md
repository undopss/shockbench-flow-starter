Status: running Full test (full 0 devpick:2,2,1,1)

Plan: port `agents/mpc_pplan`'s planned pulses (`pplan.py`, `pulse_plan`, `pp_value`) into a copy of `agents/mpc_buffer` (`agents/mpc_bufplan`, off by default), then run small random 20 → full devpick:2,2,1,1 → full dev vs `agents/mpc_buffer`.

## Stage 1: small random 20 (entropy 330980284)
pp20 = pp50 = +0.024 [+0.008, +0.043] (all fab grids); CN/JP/SEA only +0.003 (Small has only JP of those). Table: `outputs/task-16/small_330980284.log`.
