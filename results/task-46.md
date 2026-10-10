Status: done. Fresh Small (2 roots x 120) pooled RSS 0.7927, 90% [0.7805, 0.8055]; Codabench 0.779 is ~1.2 SE below, dev 0.8076 ~1.9 SE above: noise, no sign that anything differs.

Plan: run the uploaded mpc_final (task-44-final, bb9674a) on fresh Small root 993322846 x120, compare with Codabench 0.779 and dev 0.8076.

## Pack / sha256
- Source files of agents/mpc_final here are byte-identical to bb9674a (git blobs; unpacked 117,740 bytes, 5 files).
- `uv run sbf pack mpc_final` on this machine prints **c20a9e7587b81d6ed1d2dfc75cbefd66bb5d6ecd310ddd5980fd915aa7f94e4b**,
  NOT 3ef5c2e9...c2093. The id is the SHA-256 of the zip bytes (ZIP_DEFLATED, fixed 1980 timestamps), so the same files
  can give a different id if the deflate implementation differs (here: Linux, Python 3.13.16, zlib 1.3). A CRLF copy
  gives f25ffa80..., also not it. I can't confirm which cause without the uploaded zip.
- Why it matters a little: the id salts `config["policy_seed"]`, and mpc_final uses it (pplan.py scenario pulses,
  `pp_scen_K 8`, rng seeded from policy_seed). So local and Codabench differ in that noise only, not in the code.

## Run 1: fresh Small root 993322846, 120 episodes

`uv run python outputs/variants.py small 993322846 120 outputs/task-46/v46.json 4` (references 1361 s incl. rebuilt
fq + cut-point caches; play 816 s)
```
small, entropy 993322846, 120 episodes; diff = variant - final, 90% paired interval
variant                      RSS     L1     L2     L3     L4     diff  interval               better%  fallb
final                     0.7969  0.795  0.799  0.771  0.869  +0.0000  [+0.0000, +0.0000]     nan%      0
```
`uv run python outputs/task-46/an46.py <results.json>` (bootstrap: the scorer's own stratified `_boot_stats`, 2000 draws):
```
RSS 0.7969  90% bootstrap [0.7786, 0.8136]  SE 0.0108  (rss_all unweighted 0.7985)
per level: {1: 0.7952, 2: 0.7988, 3: 0.7714, 4: 0.8686}
episodes per level: {1: 62, 2: 35, 3: 15, 4: 8}  kept: {1: 62, 2: 35, 3: 15, 4: 8}  excluded 0
fallback weeks: 0
per-episode (naive-J)/(naive-oracle), kept episodes:
  L1 n=62: min +0.395 p10 +0.587 med +0.816 p90 +0.933 max +0.964
  L2 n=35: min +0.455 p10 +0.640 med +0.774 p90 +0.912 max +0.930
  L3 n=15: min +0.595 p10 +0.605 med +0.760 p90 +0.877 max +0.912
  L4 n=8: min +0.727 p10 +0.782 med +0.850 p90 +0.947 max +0.957
```
How noisy is the dev split (5 episodes per level)? `outputs/task-46/dev5.py`: resampling 5 per level from this pool:
```
dev-shaped (5/level) score from this pool: mean 0.7958 SD 0.0336 5-95% [0.7376, 0.8484]; P(>=0.8076) 0.377
```
Comparison: dev 20 (task 44A, final_scen = these params) 0.8076 (L1 .837 L2 .771 L3 .830 L4 .681); Codabench 0.779 (200).

## Run 2: fresh Small root 1360000001, 120 episodes

`uv run python outputs/variants.py small 1360000001 120 outputs/task-46/v46.json 4` (references 189 s, play 871 s)
```
small, entropy 1360000001, 120 episodes; diff = variant - final, 90% paired interval
variant                      RSS     L1     L2     L3     L4     diff  interval               better%  fallb
final                     0.7898  0.806  0.810  0.681  0.799  +0.0000  [+0.0000, +0.0000]     nan%      0
```
```
RSS 0.7898  90% bootstrap [0.7716, 0.8077]  SE 0.0109  (rss_all unweighted 0.7912)
per level: {1: 0.8059, 2: 0.8096, 3: 0.6811, 4: 0.7991}
episodes per level: {1: 60, 2: 32, 3: 16, 4: 12}  kept: {1: 60, 2: 32, 3: 16, 4: 12}  excluded 0
fallback weeks: 0
per-episode (naive-J)/(naive-oracle), kept episodes:
  L1 n=60: min +0.218 p10 +0.668 med +0.799 p90 +0.924 max +0.963
  L2 n=32: min +0.490 p10 +0.602 med +0.809 p90 +0.916 max +0.934
  L3 n=16: min +0.453 p10 +0.480 med +0.682 p90 +0.825 max +0.867
  L4 n=12: min +0.214 p10 +0.606 med +0.788 p90 +0.921 max +0.925
dev-shaped (5/level) score from this pool: mean 0.7890 SD 0.0327 5-95% [0.7306, 0.8377]; P(>=0.8076) 0.300
```

## Both roots pooled (`outputs/task-46/pool46.py`, board weights 0.5/0.3/0.15/0.05, stratified bootstrap)
```
pooled 240 episodes: RSS 0.7927 90% [0.7805, 0.8055] SE 0.0078; per level {'1': 0.8004, '2': 0.804, '3': 0.722, '4': 0.8282}
```

## Verdict

| set | episodes | RSS | note |
|---|---|---|---|
| local dev (root 0) | 20 (5/level) | 0.8076 | task 44A; SD of a 5/level score is ~0.033 |
| fresh root 993322846 | 120 | 0.7969 [0.779, 0.814] | 0 fallback weeks |
| fresh root 1360000001 | 120 | 0.7898 [0.772, 0.808] | 0 fallback weeks |
| fresh, pooled | 240 | **0.7927** [0.7805, 0.8055], SE 0.0078 | |
| Codabench private | 200 | 0.779 | SE about 0.008 if it is like ours (0.0108 x sqrt(120/200)) |

- **The dev split is a bit easy, mostly at L1** (dev L1 0.837 vs 0.795 / 0.806 fresh; L1 is half the score), and with
  5 episodes per level it is very noisy (SD ~0.033). A dev score ≥ 0.8076 happens 30-38% of the time from the fresh pools.
  So dev 20 overstates this agent by ~0.015, and that's just luck.
- **Codabench 0.779 vs local fresh 0.7927:** a gap of 0.014. With both SEs (~0.008 each) that is ~1.2 SE, and 0.779
  sits right at the lower edge of root 1's 90% interval. That fits noise in the 200 private episodes. I see no sign
  that the server plays differently: 0 fallback weeks locally, no excluded episodes. The imit_room gap (local ~0.782 vs
  0.7668) points the same way, but both uploads were scored on the **same** 200 private episodes, so the two gaps
  aren't independent evidence. They are consistent with that private set simply being ~0.01-0.015 harder than average.
- One thing I can't rule out from here: CPU fallbacks on the server. Codabench's per-week timing is not visible to
  us. Locally there were 0 fallback weeks (no CPU budget metered in this runner). If the Codabench result page shows
  fallback weeks, that would be the place to look.
- Per level, the fresh roots disagree most at L3 (0.771 vs 0.681, 15-16 episodes each). L3 is the weakest level
  pooled (0.722), so that's where to look if anyone has time after the deadline.

## Choices I made (no one to ask)
- The task asked for the interval of the score itself: the runner gives only paired intervals, so `an46.py` uses
  the scorer's own stratified `_boot_stats` on the single J vector (2000 draws, seed 0).
- Pooling the roots: concatenated the references and used `episode_rss` with the board weights (`pool46.py`).
- I ran the second root because the first took ~38 min end to end (most of it rebuilding the fq and cut-point caches,
  which missed like in task 44A); the second took ~18 min.
- Sha256 mismatch: reported (see top). I didn't try other zip tools; the source files are byte-identical to bb9674a.
- Not uploaded.
