Status: partial (2 of 4 rows; jp_pulse, safety_6 still playing)

Task 51B: root 419979470, 20 Full episodes, `uv run python outputs/variants.py full 419979470 20 v51.json 4`
(v51.json committed as results/task-51B-v51.json; each variant = mpc_final params.json + one change).

Choices made (no one to ask):
- The smoke (`full 0 devpick:1,0,0,0`, us_nobuf) was started first but killed after 10 min without finishing (it builds
  the whole dev set's references); skipped it to protect the 19:50 UTC deadline. The main run counts exceptions anyway
  (a crash would show as fallback weeks / a traceback).

## Partial table (outputs/t51/partial.py on results.json, same maths as variants.py)

```
variant          RSS     L1     L2     L3     L4     diff  interval  better%  fallb
baseline      0.8483  0.883  0.835  0.820  0.664  +0.0000  [+0.0000, +0.0000]    nan%      0
us_nobuf      0.8442  0.880  0.832  0.811  0.658  -0.0040  [-0.0053, -0.0029]    0.0%      0  <-- worse
```
