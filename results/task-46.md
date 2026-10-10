Status: building references (Small root 993322846, 120 episodes; fq + cut-point caches missed and were rebuilt, 13+6 min, references started 15:11 UTC)

Plan: run the uploaded mpc_final (task-44-final, bb9674a) on fresh Small root 993322846 x120, compare with Codabench 0.779 and dev 0.8076.

## Pack / sha256
- Source files of agents/mpc_final here are byte-identical to bb9674a (git blobs; unpacked 117,740 bytes, 5 files).
- `uv run sbf pack mpc_final` on this machine prints **c20a9e7587b81d6ed1d2dfc75cbefd66bb5d6ecd310ddd5980fd915aa7f94e4b**,
  NOT 3ef5c2e9...c2093. The id is the SHA-256 of the zip bytes (ZIP_DEFLATED, fixed 1980 timestamps), so the same files
  can give a different id if the deflate implementation differs (here: Linux, Python 3.13.16, zlib 1.3). A CRLF copy
  gives f25ffa80..., also not it. I can't confirm which cause without the uploaded zip.
- Why it matters a little: the id salts `config["policy_seed"]`, and mpc_final uses it (pplan.py scenario pulses,
  `pp_scen_K 8`, rng seeded from policy_seed). So local and Codabench differ in that noise only, not in the code.
