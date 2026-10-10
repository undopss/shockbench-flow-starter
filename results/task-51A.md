Status: playing variants (baseline RSS 0.8153 in 462 s; references took 1712 s)

Plan: task 51A, variants us_nobuf / jp_pulse / safety_6 vs mpc_final (final.zip params, from origin/task-51-ideas) on full root 242617957, 20 episodes.

Choices made (nobody to ask):
- Skipped the separate us_nobuf smoke on dev episode to save time for the deadline (~80 min left at start); exceptions/fallback weeks for us_nobuf are read from the main run's table instead.
- outputs/v51.json: baseline = agents/mpc_final with its own params.json; each variant = full params.json + one change.
