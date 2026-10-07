# Team context for Claude (cloud sessions and Andrii's AI)

Maintained from Botan's local Claude memory. Last update: **2026-10-07 19:00**. Full test log: `EXPERIMENTS.md`. Read `AGENTS.md` and `docs/GUIDE.md`
too. Team: Botan (Codabench `botan_krutan`) and Andrii (GitHub `undopss`, owns this fork). Short Ukrainian status for
humans: `STATUS_UA.md`. Write anything meant for the team in Ukrainian, short and clear.

## Hard rules

1. **Never guess.** Don't invent scores, timings, or how code behaves ("should work on Full"). Run it or read it, or
   say "not verified" and ask. Keep verified facts and assumptions clearly apart.
2. **Never upload to Codabench.** Uploads are done by Botan only (5 a day). Never commit `.env` or tokens.
   `sbf upload --help` does NOT print help, it really uploads.
3. **The final is scored on Full only.** Every candidate is judged on Full. Small results are only a cheap filter
   (Small ≠ Full: `scen` is 0.73 on Small but worse than `mpc` on Full).
4. **Time guard:** the agent measures `time.process_time()` itself. When a week gets close to its budget, it falls back to a
   cheap plan. `try/except` goes around everything in `act`. Sizes always come from `config`, never hard-coded 108/395.
5. **Ideas must be big:** each idea needs a plausible path to **+0.05 RSS on Full** (≈ −0.17 trillion USD per Full
   episode, ~2% of total cost). No small parameter tuning until we are near 0.8.
6. Work on a branch, open a PR into `cloud` (not `main`).

## Final pick (organisers' announcement, 2026-10-07)

- The board automatically shows each team's best submission by Small RSS (ours: scen v3, 0.699). It can't be changed
  before **2026-10-10 00:00 Kyiv**.
- **2026-10-10 00:00–23:59 Kyiv**: pick the final entry (My Submissions → green icon). If nothing is done, the best-on-Small
  goes to the final. That is scen v3, which is WORSE on Full. **Switching on Oct 10 is mandatory.**
- The entry at 23:59 on Oct 10 is re-run on 400 hidden Full episodes. The candidate must be uploaded before then.

## Competition facts

- Score = RSS: 0 = naive, 1 = clairvoyant, negatives are kept. Harm-level weights 50/30/15/5, so level 1
  (calm episodes) dominates.
- Public board = Small (200 hidden episodes, 2 s CPU per week). The final = Full (400 episodes, 4 s per week).
- Scoring server: Python 3.13 stdlib + numpy 2.4.5 + SciPy 1.18.1 + PyTorch 2.14 CPU, **1 thread**, no GPU, no network,
  4 GB RAM, ≤500 MB unpacked, ≤1000 files, zip ≤100 MiB, 60 s untimed startup. `shockbench_flow` is NOT importable there.
  It is **at least ~5×** faster than the home server (AMD FX-6100); the exact factor is unknown.
- Fallbacks don't invalidate a submission, they only cost score (that week is played by the naive rule).

## Agents in this repo

| Folder | What | Result |
|---|---|---|
| `agents/heuristic` | organisers' heuristic | board 0.4283; Full dev 0.370 |
| `agents/mine` | Andrii's demand-aware dispatch | board 0.4487; Full dev 0.352 |
| `agents/mpc` | energy LP (H=12) + `fallback.py` (= `mine`) for every other slot | board 0.5397; **Full dev 0.5124** |
| **`agents/mpc_pulse`** | `mpc_chip` with the winners on by default: fuel pulse at TW/KR (`pulse_weeks` 1.5) + `fab_cap_mode: observed` | **Full dev 0.6751 (+0.131 vs mpc_chip, CI +0.097…+0.162). Codabench 967249: 0.6896, 0 fallbacks. Current final candidate.** |
| `agents/mpc_chip` | `mpc` + **chip LP** (`chips.py`) for every wafer/chip slot, + energy LP fix (the grid must burn) | **Full dev 0.5443 (+0.032 vs mpc, CI +0.009…+0.056)**. Current best on Full. Not uploaded yet |
| `agents/scen` | port of the organisers' `mpc_scen` | board **0.699** (Small) but **Full dev 0.42 < mpc** → not a final candidate |
| `agents/scen_final` (branch `scen-final`) | scen without debug weeks | Small +0.006 vs scen; same Full problem |
| `agents/calib` | speed probe | tool only |

`mpc_chip` options live in `PARAMS` at the top of `agent.py`, overridable with a `params.json` next to it (that is how
the test runner makes variants): `H`, `safety_weeks`, `chip_H` (24), `pulse_weeks` + `pulse_grids` (fuel pulse
experiment, off by default), `fab_boost` (no effect, ignore).

## How the game really works on the chip side (read from the simulator, 2026-10-07)

- The agent only controls **shipping**. Fabs start every wafer they hold up to capacity **if they get power**; raw chips
  come out after 6–8 weeks. OSATs package raw chips automatically (2 weeks). All sinks are **lost-sales**
  (leading-edge chip ~50k USD per missing unit, mature ~10k).
- Every node has a storage cap; stock above it is **disposed of** (lost).
- **Grids are `base_first`: homes are served first, fabs get only what is left.** Grids are short of fuel (LNG stock
  under the rationing line psi·Ibar most weeks; sanctions ban US LNG→EU and RU gas→EU; tankers queue at Malacca), so
  **fabs get ~1–2% of the power they need and run at ~2% of capacity**, while wafers pile up.
- Gap analysis on Full dev (`outputs/cost_breakdown.py`): mpc's gap to the clairvoyant plan is **95% chip shortage**,
  power shed only 0.2%.
- **The clairvoyant oracle LP relaxes the `base_first` rule** (`shockbench_flow/oracle/lp.py` docstring: the priority
  rule is replaced by its feasible set), so it powers fabs while shedding homes (its fabs run at ~40%, same shed as
  ours). **A large part of the chip gap is unreachable for any real agent.**
- What a real agent can still win:
  1. **Timing:** the rule is checked per week. Batching fuel so a grid is fully supplied in some weeks lets fabs run in
     those weeks ("fuel pulse"; crude test on Small: chip shortage −8%, total −1.4%).
  2. **Which fab gets the scarce leftover power:** it is split in proportion to each fab's wafer-limited draw
     (e·p̂/R, p̂ = min(capacity, wafers on hand)), so wafer allocation steers power to high-value fabs (memory/leading
     ≈ 25–40 M USD of chips per power unit vs mature ≈ 11 M).
  3. Chip routing and less waste (done in `mpc_chip`: disposal −94%, shortage −4%).
- The organisers' `mpc_det` / `mpc_det_safety` on Full dev: **0.372 / 0.375** (better chips than mpc, much worse power).

## Experiment pipeline (home server)

- Runner: `uv run python outputs/variants.py <small|full> <entropy|random> <N|dev|devpick:a,b,c,d|list> <variants.json> [n_jobs]`.
  The first entry of variants.json is the baseline; every other entry is compared with it **on the same episodes**
  (paired 90% interval). Writes `outputs/variants/<round>/results.json`.
- Funnel: **small20** (fresh random seed per round, filter only) → **full6** (`devpick:2,2,1,1` on root 0, all
  four harm levels) → **full20** (`dev`, decision).
- The server runs a queue (`~/sbf-jobs/xq.py`, 2 tests at a time). Page: http://192.168.1.46:8099/experiments.html
  (Tailscale: http://100.99.112.98:8099/experiments.html).
- Cost breakdown of any agent vs naive vs clairvoyant: `outputs/cost_breakdown.py full 0 dev agents/<name> 3`
  (also `policy:mpc_det` for package baselines).

## Results of 2026-10-07 afternoon (details in EXPERIMENTS.md)

- Fuel pulse works mostly through **Korea** on Full (KR fabs ~1% → ~20%); KR alone +0.119, TW/KR +0.133, TW/KR/JP/SEA +0.139 (Full 6, with fab_cap observed).
  Adding JP/SEA to TW/KR: +0.020 (cloud task 2). Bigger batches (2.5 weeks): worse. Automatic grid choice: no gain.
- `fab_cap_mode: observed` alone: Full dev 20 +0.051.
- Energy horizon 20 vs 12: no effect. Tanker priorities (task 4): dead end.
- Cost gap of mpc_pulse on Full dev: 1.15 T USD/episode (mpc: 1.66): chip shortage 88%, power shed 10% (the pulse adds ~0.12 T of shed).

## Next steps (2026-10-07 evening)

1. Round 1 on Small (running): fuel pulses (TW/KR, TW/KR/JP), energy horizon 20, chip-planner calibration.
2. Code the big ideas: planned pulses (the energy LP chooses burst weeks), steering scarce power to high-value fabs via
   wafer allocation, tanker priorities at straits (LNG for fab grids first).
3. Promote winners: full6 → full20. Upload the best Full candidate before Oct 10; switch the board entry on Oct 10.

## Practical notes

- `sbf evaluate` / `sbf check` / `outputs/variants.py` break on native Windows (`fcntl`); use Linux (home server, cloud).
- Reference caches are small (Full ≈ 1 MB) but slow to build (~10–20 min Full on 4 cores); a new seed needs new ones.
- `outputs/` is gitignored; the scripts there are force-added.
