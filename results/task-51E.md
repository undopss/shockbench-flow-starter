Status: done (table pushed 19:11 UTC)

Task 51E: v51b.json on `full 419979470 20`, 4 jobs, code = origin/task-51-ideas agents/mpc_final (params.json = final.zip, safety_weeks 5).
Variants = full params.json + one change: `tw_safety_7` (jp_grids ["grid_tw"], jp_safety lng/crude 7.0), `pulse_w075` (pulse_weeks 0.75).

Command: `uv run python outputs/variants.py full 419979470 20 outputs/v51b.json 4`
Wall time: references 1337 s (new root), then ~5.2 min per variant (final 312 s, tw_safety_7 315 s, pulse_w075 321 s); total ~38 min.

```
full, entropy 419979470, 20 episodes; diff = variant - final, 90% paired interval
variant                      RSS     L1     L2     L3     L4     diff  interval               better%  fallb
final                     0.8483  0.883  0.835  0.820  0.664  +0.0000  [+0.0000, +0.0000]     nan%      0
tw_safety_7               0.8468  0.881  0.833  0.819  0.667  -0.0015  [-0.0039, +0.0006]    12.7%      0
pulse_w075                0.8485  0.883  0.836  0.818  0.664  +0.0003  [-0.0007, +0.0012]    66.6%      0
```

Notes / choices made without asking:
- No smoke run (the 51 D/E/F steps don't ask for one; the runner reported 0 fallback weeks for every variant).
- Variant JSON built from agents/mpc_final/params.json with Python (outputs/v51b.json, committed). Results: outputs/variants/v51b_full_419979470_1010-1829/results.json.
- Neither interval is above 0 on this root: tw_safety_7 leans worse, pulse_w075 is flat. No upload.
