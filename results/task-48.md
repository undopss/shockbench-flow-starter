Status: playing variants (references ready in 1037 s at ~16:22 UTC; expect table ~17:00-17:15 UTC)

Plan: smoke mpc_final cl_safety 4 on full 0 devpick:1,0,0,0, then v48.json (cl2, cl4, cl4_all, cl4_h8 vs mpc_final) on full 1341342961 20, 4 jobs.

Branch note: origin/task-48-closure (945fd19) was not based on cloud; merged origin/cloud into it (no conflicts, agents/mpc_final untouched).

Choice (no one to ask): the smoke on `full 0 devpick:1,0,0,0` was still busy after ~10 min on 2 cores (apparently
building the dev references in this container), which risked pushing the main run past the 17:45 UTC deadline. I
stopped it at 16:04 UTC and started the main run directly (`full 1341342961 20`, 4 jobs); its exception/fallback
counts for the cl variants serve as the smoke check.
