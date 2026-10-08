Status: done

# Task 28 (rerun): "rule lawyer", every simulator mechanic vs what we exploit (Full)

**Verdict: no hidden rule is worth +0.05 RSS by itself.** Every cost term except shortage and shed adds up to
**< 0.05 T/episode** of gap, and the clairvoyant reference is an LP relaxation of the simulator (`oracle/lp.py:1-10`,
"J^oracle stays a bound"), so no rule trick can score above the oracle. The whole reachable gap on Full devpick 6 is
**0.506 T/ep** (dev 20: 0.708). It sits where tasks 20-21 already put it: **fab power under the homes-first rule**
(~0.18 T of fab power plus the pulses' 0.16 T of extra shed) and **chip routing/overflow** (≤ 0.094 T with perfect
foresight). The one rule we use only partly and that needs no foresight is **power steering inside a grid**: leftover
power goes to each fab in proportion to the wafers it holds. Its ceiling is ~0.03-0.06 T (TW, KR), below the bar on
its own.

## How it was measured
- I read all of `shockbench_flow/dynamics/*` (sim, production, chokepoint, clip, cost, env, state), `instance/schema.py`,
  `marks.py` (events → marks, alpha-bar, scrap, tariffs, sanctions, war risk), `information/forecast.py`,
  `oracle/lp.py` (header), `scoring/rss.py`, and the agent's `agent.py`/`chips.py` headers.
- `outputs/task-28/inst_dump.py` → `full_instance.txt` (every commodity, sink, fab, OSAT, grid, stock slot, chokepoint).
  `outputs/task-28/static28.py` → `static_full.txt` (grid headroom, fuel stocks in weeks of burn, salvage maximum).
- `outputs/task-28/probe28.py full 0 devpick:2,2,1,1 agents/mpc_fab3sell 3` replays mpc_fab3sell (its own
  params.json) on Full episodes 2, 5, 0, 1, 53, 26 and measures each mechanic from the weekly records → 
  `probe_full_0_devpick-2-2-1-1_mpc_fab3sell.json`, `probe_summary.txt`. **RSS 0.8500** (L1-4 0.843/0.869/0.838/0.845),
  0 fallback weeks, and J equal **to the cent** to task 20's run of the same episodes.
  Choice I made: the probe builds the world **without the naive fallback**, because this container's Python doesn't match
  the cached F_Q and rebuilding it took 57 min on one core (`outputs/task-28/fq_full.py`; now cached in `~/.cache` here).
  This only matters if a week fails, and none did.
- Agent-vs-oracle cost components and per-grid shed come from task 20's dev-20 JSON (`outputs/task-20/gap17v2_...`),
  restricted to the same 6 episodes (`outputs/task-28/shed_cmp.py`). Chip-side LP bounds are task 21's (same 6 episodes).

## Ranked table (T USD per Full episode, devpick 6 unless said; 0.01 RSS ≈ 0.034 T on Full)

| # | mechanic | rule (file:line) | we do now | idea | ceiling T | needs foresight? |
|---|---|---|---|---|---|---|
| 1 | **Fab power under homes-first**: rationing reads last week's gas stock; each fuel segment capped at share·G-bar (crude/nuclear can't be replaced by gas); homes first, fabs get the rest | `dynamics/sim.py:332-363`, `production.py:25-27` | pulses (pplan) at TW/KR, pp_split (recharge gas, hold crude), pp_direct CN/EU | known: better pulse timing; JP's crude segment is empty 66 wk/ep (39.5k GWh while shedding) | **≤ 0.34** (fab power 0.180 [task 21] + pulse shed price 0.159) | partly (the oracle's plan uses foresight; task 3's MILP says reachable with it) |
| 2 | **Disposal above I^max** at fabs/OSATs/sinks (end of week, after serving) | `sim.py:408-412`, cost `cost.py:125` | chip LP models caps and disposal | plan raw-chip flows with the OSATs' out-edge capacities (task 20 item 1) | 0.32 gross at pi (4.7M LE + 8.5M MAT units disposed/ep); **LP bound 0.094** (task 21 routing) | partly |
| 3 | **Which fab starts when**, incl. **power steering inside a grid**: leftover power split ∝ e·p̂/R, p̂ = min(α·R·cap0, wafers on hand) | `sim.py:322-325, 349-354` | wafer_buffer = 3 weeks of nameplate at **every** fab → split ∝ nameplate | in partial-power weeks hold wafers back from the lower-value fab: TW mature (11 M USD/GWh) → TW leading (25 M); KR leading (25 M) → KR memory (40 M) | greedy gross 0.111 (TW 0.040, KR 0.030, US 0.036 *not sellable: US leading chips already overflow*, EU 0.005); **LP bound 0.062** (task 21 "starts") | **no** (needs next week's leftover power, which pplan already plans) |
| 4 | End of horizon: stock and WIP at T credited only at salvage ν (1-18 USD/unit chips) | `cost.py:145-173` | `sell_end` (no wafer buffer for lots that can't sell) | ship/start less in the last ~10 weeks | chips left at T: 0.70M LE + 4.8M MAT ≈ 0.085 gross; part of 2-3 | no |
| 5 | Salvage S_T itself | `cost.py:145-173` | nothing | end with full storage | max possible 0.0177 (every slot at I^max), we get 0.0059 → **+0.012 gross** | no — dead |
| 6 | Holding, tariff, freight, queue holding, war risk, disposal *cost* | `cost.py:118-126`, `marks.py:798-884` | in the LPs | — | gaps 0.016 / 0.009 / 0.006 / 0.002 / 0.0001 / 0.015 → **< 0.05 all together** | — dead |
| 7 | Tanker overrides, hold, turn-backs | `chokepoint.py:73-205`, `env.py:150-227` (release_mode) | never set (default FIFO release) | turn back stuck LNG/crude, time releases | turn-backs exist only at Suez (→term_eu/term_in): Suez tanker queue 10k GWh-wk/ep, 0 while closed; fuel queued at closed Malacca/Taiwan 0.21M GWh-wk/ep. Task 4: ~0. Hold adds nothing that source-side timing can't do (sources hold for free, refill to cap) | ≈ 0 |
| 8 | Container queues at straits (FIFO by arrival cohort, κ_ct pro rata, no override for containers) | `chokepoint.py:120-146` | chip LP; kappa_lp only for tankers | — | chip_mat at Malacca 170M unit-weeks/ep (~1.6M units waiting); holding 0.0006; the delay is inside #2's bound | partly |
| 9 | OSAT packaging pro rata across raw types when throughput binds (chip LP assumes a free split) | `sim.py:379-392`, `production.py:41` | LP free split (model mismatch) | send LE raw first | binds 1.3 wk/ep, 2.6k LE units displaced → **~0.0001** | — dead |
| 10 | Scrap of WIP at fab-hit onsets | `sim.py:369-375`, `marks.py:1025-1027` | nothing | idle a fab before a hit | 0.5 hits/ep, **0 units scrapped** (the hit fabs were idle) | yes — dead |
| 11 | α-bar overproduction ceiling (up to 1.25 after an outage) | `marks.py:1032-1041`, `sim.py:322-325` | fab_cap observed | — | headroom 41k lots/ep, 0 used (fabs are power-limited) → **≤ 0.002** | — dead |
| 12 | Supply refills to the cap, the rest is lost | `sim.py:316-319` | — | — | lost at the cap per ep: LNG 1.8M, crude 0.36M, nuclear 2.1M GWh, while grids shed; the oracle sheds the same at JP/SEA/US/IN, so it is transport/sanction-limited | structural |
| 13 | Nuclear stock starts at exactly 52 weeks; Full is 104 | `static_full.txt` | energy LP ships nucfuel | — | US nuclear empty 7 wk/ep (all in shed weeks); the oracle sheds in the **same weeks** (identical US shed weeks in 5/6 episodes) | structural |
| 14 | Demand noise and forecast | `information/forecast.py:1-15`, `omega/demand.py` | game forecast (8 wk) | — | forecast_shares = (1,0,…,0): the forecast shows nothing of the future noise beyond the AR(1) mean; σ = 0.1 and fill is 45-75% everywhere | ≈ 0 |
| 15 | Lost sales vs backlog | `sim.py:395-405` | — | — | all 16 Full sinks are lost-sales (sink_cn chip_le has demand 0) | — |
| 16 | Energy priority rule | `production.py:11-38` | — | — | every grid is base_first; the oracle relaxes it, but CONTEXT's homes-first MILP: ≤ 0.003 | — |
| 17 | Fallback, validation, clipping, rounding | `env.py:35-47, 150-227`, `clip.py:54, 193, 289` | try/except + time guard | — | a failed week plays naive, dropped entries do nothing, clips are pro rata: these rules can only lose | — |
| 18 | Scoring | `scoring/rss.py:4`, `oracle/lp.py:1-10` | — | — | RSS = Σ p_s ḡ_s / Σ p_s D̄_s, p = 0.50/0.30/0.15/0.05; the oracle is a bound, so RSS ≤ 1 and there is no score trick | — |

## Facts worth knowing (all read or measured, not guessed)
- **Grid headroom is exactly the fabs' nameplate draw** (`static_full.txt`): G-bar − y-bar = Σ e·cap0 at every fab grid
  (TW 488, KR 456, JP 181, CN 393, US 266, EU 242, SEA 125 GWh/wk; IN 0). So any missing segment (gas below the
  rationing line, crude empty, a G-bar cut) takes power from the fabs first, and only a fully supplied week runs them.
- **Crude starts at 0 at every grid**, at 1-5% of G-bar. At JP the crude segment (900 GWh/wk) is 5× the fab headroom
  (181), so JP memory can only run in weeks with crude on hand. Agent crude stock-outs per ep (GWh while shedding):
  JP 39.5k, CN 54.5k, EU 52.9k, SEA 61.4k, KR 2.2k, TW 1.8k. The oracle sheds about the same at JP/SEA (154k/352k vs our
  157k/353k GWh), so most of this is structural.
- Shed per grid, agent vs oracle (GWh/ep): TW 45k/43k, KR 61k/51k, JP 157k/154k, CN 107k/94k, US 167k/165k,
  EU 112k/103k, SEA 353k/352k, IN 8.6k/8.6k. Our remaining shed gap is at **KR, CN, EU** (and a little TW/JP).
- LNG disposed of at grid_us: 0.29M GWh/ep (dev 20): the US pipeline overfills the grid. That costs only 0.001 T
  (and US doesn't shed from LNG), but it is fuel thrown away.
- Rationing sees the grid's stock only, never the terminal's (`sim.py:337-339`), and this week's arrivals count for the
  burn but not for the rationing factor. That is the whole pulse mechanism, and pplan already models it.

## Surprising
- Nothing in the rules is hidden from us. The other teams' lead must come from planning quality (task 20: on Small,
  chip overflow plus structural EU/JP shed), not from a rule we missed.
- Power steering (#3) is the only under-used rule that needs no foresight. Worth a small build only if combined with
  pplan (it knows which weeks will be partial); gross 0.07 T at TW + KR, realistically ≤ 0.03-0.06 T.
