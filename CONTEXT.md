# Team context for Claude (cloud sessions)

Written 2026-10-07 from Botan's local Claude memory, so cloud sessions know what the local one knows.
Read `AGENTS.md` and `docs/GUIDE.md` too. Team: Botan (Codabench `botan_krutan`) and Andrii (GitHub `undopss`, owns this fork).
Their own notes are in Ukrainian; write anything meant for the team in Ukrainian, short and clear.

## Hard rules

1. **Never guess.** Don't invent scores, timings, or how code behaves ("should work on Full"). Run it or read it, or
   say "not verified" and ask. Keep verified facts and assumptions clearly apart.
2. **Never upload to Codabench.** Uploads are done by Botan only (3–5 a day, each one counts). Cloud sessions
   have no token anyway. Never commit `.env` or tokens. `sbf upload --help` does NOT print help, it really uploads.
3. **The board must always hold an agent verified on Full** (`sbf check --task=full` + a Full dev eval). The final
   re-runs the chosen agent on Full.
4. **Time guard:** the agent measures `time.process_time()` itself. When a week gets close to its budget, it falls back to a
   cheap plan. `try/except` goes around everything in `act`. Sizes always come from `config`, never hard-coded 108/395.
5. **A change is real only if** `sbf compare` on 64 episodes of our own root (`--entropy=12345`) gives a paired
   90% CI that excludes 0. The 20 dev episodes are only for the final confirmation.
6. Work on a branch and finish with a PR. Don't push to `main`.

## Competition facts

- Score = RSS: 0 = naive, 1 = clairvoyant, negatives are kept. Harm-level weights 50/30/15/5, so level 1
  (calm episodes) dominates. Overreacting in calm episodes is what hurts most.
- Public board = Small (200 hidden episodes, 2 s CPU per week). The final re-runs the same pick on Full (400 episodes, 4 s per week).
- Dev phase ends **2026-10-10 23:59 Kyiv**. Final runs 2026-10-11 00:00–13:00 Kyiv. Codabench competition 18290.
- Scoring server: Python 3.13 stdlib + numpy 2.4.5 + SciPy 1.18.1 + PyTorch 2.14 CPU, **1 thread**, no GPU, no network,
  4 GB RAM, ≤500 MB unpacked, ≤1000 files, zip ≤100 MiB, 60 s untimed startup. `shockbench_flow` is NOT importable there.
- It is **at least ~5× faster** than our home benchmark machine (AMD FX-6100), measured with `agents/calib` (submission 965577).
  The exact factor is unknown.
- Cost structure (Small, measured): power shed at grids ≈59%, chip shortage ≈39%, everything else <2%. Route-cost
  optimisation barely matters. The score depends on keeping grids fuelled (LNG/crude/nucfuel → terminals → grids)
  and chips flowing (wafers/power → fabs → OSATs). Small action slots: 0–34 energy, 35–59 wafers, 60–81 raw chips
  to OSATs, 82–107 OSAT→sinks.

## Agents in this repo

| Folder | What | Status |
|---|---|---|
| `agents/heuristic` | organisers' heuristic | board 958941: **0.4283** (currently the one on the leaderboard) |
| `agents/mine` | Andrii's demand-aware dispatch | board 964473: **0.4487** |
| `agents/mpc` | our energy MPC (scipy linprog, H=12, on energy slots; everything else → `fallback.py` = copy of `mine`) | board 964550: **0.5397**. Passes `sbf check` on Small and Full |
| `agents/scen` | port of the organisers' `mpc_scen` (vendored package as `sbfv/`, MIT; HiGHS through SciPy's bundled copy; `data/*.pkl` precomputed draws; `safe/` = copy of `agents/mpc` as safety net) | v3 = this version. Not yet seen on the board as of this writing; ask Botan for the latest result |
| `agents/calib` | speed probe: deliberately raises k weeks, X = Fallbacks / (episodes·10) | measuring tool only |

`agents/scen` history: v1 (965597) RSS 0.0000, every week naive, cause unknown. v2 (965604) RSS 0.4145, Fallbacks 3000
= 15 per episode = `Agent(config)` ValueError from our own generator-id check (Codabench's instance hash differs from local).
v3 removes that check, and its docstring explains how to decode the Fallbacks count. Locally v3 plays **identically** to
the original `mpc_scen` (6/8 episodes equal to the cent, RSS 0.7911 = 0.7911). On Full the FX-6100 takes up to 12.8 s per
week. Set `SCEN_SLOW_SHARE=100` for local tests on slow machines, otherwise the slow-week guard kicks in.
Before the final, the diagnostic weeks must be removed while keeping the safety net.

## Measured results (local)

64 Small episodes, root 12345, organisers' planners vs ours (`outputs/compare_baselines.py`, results in
`outputs/baselines_small_12345_64.json`):

| policy | RSS | note |
|---|---|---|
| mpc_scen | **0.731** | cpu max 4.8 s/week on the FX-6100 |
| mpc_det_safety | 0.719 | cpu max 0.56 s |
| mpc_det | 0.717 | |
| mpc_det_h20 | 0.686 | |
| mpc_det_h12 | 0.566 | horizon matters |
| ours `agents/mpc` | 0.565 | |
| greedy_lp | 0.393 | |

Other results:
- `mpc` v2 vs `mine`: Small 64 eps **+0.085** (CI +0.067…+0.106), Full 20 dev eps **0.5124 vs 0.3517** (+0.161).
- Heuristic: Small dev 0.4004, Full dev 0.3698. Full is harder, so check every candidate on Full.
- Policy search (`examples/06_policy_search.py`) gave only about +0.02. ⚠️ Its candidate has 108 per-slot numbers and crashes on
  Full (395 slots), so it must never be the final pick.
- Dead ends: chokepoint `warning.score` doesn't predict closures (AUC 0.507 over 300 eps). Chronos zero-shot loses to the
  simulator's own demand forecast (rel. error 0.096 vs 0.090), because that forecast is the generator's formula.
- Mentor advice (2026-10-06): prefer optimisation + parameter calibration over hand rules, separate tune and held-out
  seed sets, small NN components only. Andrii and Botan are open to time-series models for disruptions, not for demand.

## !!! Final pick (organisers' announcement, 2026-10-07)

- The board automatically shows each team's best submission by Small RSS (ours: scen v3, 0.699). It can't be changed
  before **2026-10-10 00:00 Kyiv**.
- **2026-10-10 00:00–23:59 Kyiv**: pick the final entry (My Submissions → green icon). If nothing is done, the best-on-Small
  goes to the final. That would be scen v3, which is WORSE on Full. **Switching on Oct 10 is mandatory.**
- The entry at 23:59 on Oct 10 is re-run on 400 hidden Full episodes. The candidate must be uploaded before then.

## Results 2026-10-07 (cloud sessions + upload)

- **scen v3 on Codabench (Small): RSS 0.699**. Strata: L1 0.651, L2 0.737, L3 0.761, L4 0.789. Fallbacks 448, of which
  446 are "invalid" (our own deliberate raises) and 2 "over_budget" (real weeks over 2 s on the server). No crashes.
- **Full, 20 dev eps: scen 0.4196 vs mpc 0.5124, diff −0.093 (90% CI −0.143…−0.037). scen is WORSE on Full.** Why is
  not known yet. A hypothesis to test, not a fact: the same horizon/stock problem mpc v1 had (nuclear fuel runs down).
  Full uses only S=2 scenarios.
- scen planner timing on Full (cloud Xeon 2.1 GHz, guard off): median 1.5–2.1 s/week, max 5–9.4 s, 7–9 of 104 weeks
  over 4 s. The scoring server's speed vs this machine is not measured.
- `agents/scen_final` (no debug weeks, safety net kept, week-1 guard fixed) vs scen, Small, 16 eps: 0.7850 vs 0.7792,
  +0.006 (CI +0.0008…+0.0104). It exists only as a patch (push to this repo was blocked).
- `SCEN_SLOW_SHARE` does not reach the agent inside `sbf check` (the isolated run passes only PATH/HOME).
- Reference caches are tiny (Full ≈ 772 KB in total); building them costs ~11 min on Full on the cloud machine.
- **The final re-scores the board submission on Full**, so the board entry at the deadline must be the best agent ON FULL.

## Next steps (as of 2026-10-07)

1. Get `scen` v3 on the board (Botan uploads) and decode its Fallbacks.
2. Compare `scen` vs `mpc` on 20 Full dev episodes (`SCEN_SLOW_SHARE=100 sbf compare scen mpc --task=full`).
3. Make the final `scen` clean: no diagnostic weeks, safety net kept, time guard within the Full budget.
4. Possible upgrades: port `mpc_det_safety` as a cheaper fallback, and tune H / scenario count / safety.

## Practical notes for a cloud machine

- Linux, so `sbf evaluate` / `sbf check` work. They break on native Windows because of `fcntl`.
- **No reference cache here.** On the FX-6100 the first Small eval built it in ~1 h (naive demand model 15 min, cut points
  ~40 min), and the Full cache took ~2 h. Use small episode counts and `-n` matching the cores you have. Don't burn hours
  re-running whole evals.
- `outputs/` is gitignored. Only the analysis scripts and the baselines JSON are force-added.
