Status: root 1 done (fresh Small 120: RSS 0.7969, 90% [0.779, 0.814]); root 2 (1360000001) running

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
