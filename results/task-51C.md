Status: done (19:29 UTC). Full 20 episodes, root 722245388: us_nobuf worse, jp_pulse worse, safety_6 +0.0009 (interval holds 0).

## Table: `uv run python outputs/variants.py full 722245388 20 v51.json 4` (as printed)
```
full, entropy 722245388, 20 episodes; diff = variant - mpc_final, 90% paired interval
variant                      RSS     L1     L2     L3     L4     diff  interval               better%  fallb
mpc_final                 0.8663  0.876  0.874  0.901  0.509  +0.0000  [+0.0000, +0.0000]     nan%      0
us_nobuf                  0.8612  0.872  0.871  0.892  0.496  -0.0050  [-0.0072, -0.0030]     0.0%      0  <-- worse
jp_pulse                  0.8647  0.873  0.874  0.901  0.505  -0.0016  [-0.0028, -0.0004]     1.1%      0  <-- worse
safety_6                  0.8672  0.876  0.877  0.901  0.508  +0.0009  [-0.0003, +0.0020]    90.0%      0

results: outputs/variants/v51_full_722245388_1010-1903/results.json
```
Wall time: references 165 s (12 of 20 already cached), about 290 s per variant.

## Earlier 4-episode run (episodes 0-3 of the same root, same v51.json)
```
full, entropy 722245388, 4 episodes; diff = variant - mpc_final, 90% paired interval
variant                      RSS     L1     L2     L3     L4     diff  interval               better%  fallb
mpc_final                 0.8738  0.871      -  0.880      -  +0.0000  [+0.0000, +0.0000]     nan%      0
us_nobuf                  0.8663  0.869      -  0.859      -  -0.0075  [-0.0145, -0.0018]     0.3%      0  <-- worse
jp_pulse                  0.8752  0.872      -  0.883      -  +0.0014  [+0.0002, +0.0026]    96.7%      0  <-- better
safety_6                  0.8761  0.873      -  0.884      -  +0.0023  [-0.0010, +0.0046]    94.8%      0

results: outputs/variants/v51_full_722245388_1010-1838/results.json
```

## Notes / choices (nobody to ask)
- Smoke `full 0 devpick:1,0,0,0` with us_nobuf was stopped after 10 min (it was still building references). Instead
  us_nobuf played 4 + 20 Full episodes here with 0 exceptions and 0 fallbacks, which covers the smoke's purpose.
- I first ran 4 episodes because the first reference build (771 s for 4 episodes) made 20 look too slow for the deadline.
  Later builds were fast (about 20 s per episode), so the full 20 ran after that. References are cached per episode, and
  episode seeds depend only on root + index, so the 4-episode run uses the same episodes as 0-3 of the 20.
- v51.json = baseline `{"agent": "agents/mpc_final"}` + the three variants (full params.json + one change), committed.
- Not uploaded.
