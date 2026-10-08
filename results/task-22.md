Status: running Full devpick (mpc_det H=L, L+8, max(26,2L), mpc_det_safety vs mpc_fab3sell)

Plan: run the joint LP family vs mpc_fab3sell on Full devpick:2,2,1,1 (episodes 2,5,0,1,53,26) with per-component/grid/fab/sink detail; build a hybrid only if a joint-LP win is >= 0.15 T/episode.

Note: this container had to rebuild the Full F_Q cache (Python patch version, ~10 min) and redraw the dev split (~10 min), as tasks 15/19 saw.
