Status: done (19:43 UTC). No variant is better: us_nobuf worse (-0.0040, interval below 0), jp_pulse and safety_6 tie (intervals hold 0). 0 fallback weeks, 0 exceptions.

Task 51B: root 419979470, 20 Full episodes, `uv run python outputs/variants.py full 419979470 20 v51.json 4`
(v51.json committed as results/task-51B-v51.json; each variant = mpc_final params.json + one change).

Choices made (no one to ask):
- The smoke (`full 0 devpick:1,0,0,0`, us_nobuf) was started first but killed after 10 min without finishing (it builds
  the whole dev set's references); skipped it to protect the 19:50 UTC deadline. The main run counts exceptions anyway
  (a crash would show as fallback weeks / a traceback).

## Table as printed

References took 1784 s; each variant ~8 min.

```
full, entropy 419979470, 20 episodes; diff = variant - baseline, 90% paired interval
variant                      RSS     L1     L2     L3     L4     diff  interval               better%  fallb
baseline                  0.8483  0.883  0.835  0.820  0.664  +0.0000  [+0.0000, +0.0000]     nan%      0
us_nobuf                  0.8442  0.880  0.832  0.811  0.658  -0.0040  [-0.0053, -0.0029]     0.0%      0  <-- worse
jp_pulse                  0.8477  0.882  0.835  0.818  0.661  -0.0005  [-0.0017, +0.0005]    19.3%      0
safety_6                  0.8485  0.881  0.840  0.816  0.663  +0.0002  [-0.0019, +0.0022]    54.3%      0

results: outputs/variants/v51_full_419979470_1010-1838/results.json
```
