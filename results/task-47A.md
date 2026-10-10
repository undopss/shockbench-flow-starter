Status: playing variants (3/9 done at 16:08 UTC)

Task 47A: `uv run python outputs/variants.py full 895331359 20 outputs/v47.json 4`, started 15:26 UTC.
Baseline = `agents/mpc_final` from task-44-final (bb9674a, own params.json). v47.json = full params.json + one change
(cover_1.0, safety_5, scen_K16, scen_cvar, smart_2.5, smart_3.5, end_6, burn_1.0); committed as outputs/v47.json.

Partial table (paired 90% intervals vs final, same bootstrap as the runner):
```
variant          RSS     L1     L2     L3     L4     diff  interval  better% fallb s
final         0.8253  0.869  0.781  0.734      -  +0.0000  [+0.0000, +0.0000]    nan%     0 316
cover_1.0     0.8264  0.866  0.789  0.736      -  +0.0011  [-0.0022, +0.0049]   67.7%     0 325
safety_5      0.8273  0.871  0.782  0.738      -  +0.0020  [+0.0002, +0.0040]   96.9%     0 342
```
