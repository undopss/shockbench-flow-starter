Status: running the measurement (base play + drop mil_closure / sanction / tariff, 80 runs); references built in 2501 s

Plan: log every announcement message on Full dev 20 while playing mpc_best, match them to the ground-truth events (omega), measure true-alarm rate / lead time per channel, and the value of perfect foresight per announced event class (task 15's "drop the class from omega" method, now on mpc_best with the official level weights). Build a param-gated reaction in agents/mpc_msg only if a channel is worth >= +0.003 RSS.

Script: `outputs/task-42/msg42.py full 0 dev agents/mpc_best 4`.
