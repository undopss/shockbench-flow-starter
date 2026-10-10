Status: done (table pushed 16:48 UTC, before the 17:45 UTC deadline)

Task 47A: `uv run python outputs/variants.py full 895331359 20 outputs/v47.json 4`.
Baseline = `agents/mpc_final` from task-44-final (bb9674a, its own params.json). Every variant = that full params.json + one
change (cover_1.0, safety_5, scen_K16, scen_cvar, smart_2.5, smart_3.5, end_6, burn_1.0); the file is outputs/v47.json.

Wall time: started 15:26 UTC, references 1332 s (cache did not cover this fresh root, as expected), plays ~59 min,
finished 16:47 UTC (81 min total). Per variant: final 316 s, cover_1.0 325, safety_5 342, scen_K16 629, scen_cvar 354,
smart_2.5 348, smart_3.5 343, end_6 348, burn_1.0 321. 0 fallback weeks everywhere. No harm-level-4 episode in these 20.

```
full, entropy 895331359, 20 episodes; diff = variant - final, 90% paired interval
variant                      RSS     L1     L2     L3     L4     diff  interval               better%  fallb
final                     0.8253  0.869  0.781  0.734      -  +0.0000  [+0.0000, +0.0000]     nan%      0
cover_1.0                 0.8264  0.866  0.789  0.736      -  +0.0011  [-0.0022, +0.0049]    67.7%      0
safety_5                  0.8273  0.871  0.782  0.738      -  +0.0020  [+0.0002, +0.0040]    96.9%      0  <-- better
scen_K16                  0.8264  0.869  0.784  0.735      -  +0.0011  [+0.0000, +0.0025]    95.2%      0  <-- better
scen_cvar                 0.8220  0.869  0.779  0.711      -  -0.0033  [-0.0072, -0.0007]     0.4%      0  <-- worse
smart_2.5                 0.8252  0.869  0.782  0.733      -  -0.0001  [-0.0014, +0.0012]    43.5%      0
smart_3.5                 0.8270  0.871  0.784  0.735      -  +0.0017  [+0.0005, +0.0029]    99.3%      0  <-- better
end_6                     0.8269  0.870  0.784  0.735      -  +0.0016  [+0.0001, +0.0031]    96.5%      0  <-- better
burn_1.0                  0.8261  0.868  0.784  0.738      -  +0.0008  [-0.0009, +0.0026]    77.0%      0

results: outputs/variants/v47_full_895331359_1010-1526/results.json
```

Choices made with nobody to ask: v47.json built from bb9674a's params.json with a script, each variant
being the full dict with one key overridden. Per-variant results.json copied to results/task-47A-results.json (J per episode, for pooling).
