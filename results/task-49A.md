Status: done (table pushed 17:43 UTC)

Task 49A: `uv run python outputs/variants.py full 295197412 20 outputs/v49.json 4`. Code: agents/mpc_final from task-48-closure (945fd19), baseline = its own params.json; variants = full params.json + the changes in CLOUD_TASKS.md (file: outputs/v49.json). Wall time ~47 min (references 1260 s, ~300 s per variant). 0 fallback weeks everywhere.

```
references ready in 1260 s (20 episodes)
  played baseline in 326 s: RSS 0.8376
  played safety_5 in 302 s: RSS 0.8378
  played cl4_all in 296 s: RSS 0.8365
  played combo in 298 s: RSS 0.8374
  played combo_cl in 304 s: RSS 0.8377

full, entropy 295197412, 20 episodes; diff = variant - baseline, 90% paired interval
variant                      RSS     L1     L2     L3     L4     diff  interval               better%  fallb
baseline                  0.8376  0.864  0.835  0.785  0.743  +0.0000  [+0.0000, +0.0000]     nan%      0
safety_5                  0.8378  0.866  0.833  0.786  0.742  +0.0003  [-0.0022, +0.0030]    56.2%      0
cl4_all                   0.8365  0.865  0.829  0.787  0.742  -0.0011  [-0.0048, +0.0020]    31.6%      0
combo                     0.8374  0.866  0.829  0.791  0.741  -0.0002  [-0.0033, +0.0030]    47.2%      0
combo_cl                  0.8377  0.865  0.833  0.788  0.741  +0.0001  [-0.0019, +0.0020]    54.4%      0

results: outputs/variants/v49_full_295197412_1010-1655/results.json
```

No interval excludes 0 on this root; all diffs within +-0.0011.

Choices made (nobody to ask): variants written as the full mpc_final params.json plus each change; results.json copied to outputs/task-49A/.
