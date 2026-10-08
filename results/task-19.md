Status: done

# Task 19: stop making chips nobody can sell

**Verdict: the lever is too small.** The clairvoyant ceiling is **0.10 T USD/episode** (0.14 T if each grid's fab power
can also move between its fabs), below the 0.17 T bar. Most of the disposal is **transport-limited**: the OSAT→sink
edges already run at their capacity, which is cut for the whole episode. One cheap option is worth keeping:
**`sell_end`** (no wafer buffer for lots that can't reach a sink before the episode ends). On Full dev 20 it scores
**+0.0044 [+0.0029, +0.0059]**, better in 100% of bootstraps, at no CPU cost. That gain comes from **less power shed**,
not from selling more chips. I recommend switching it on in the final candidate. It is off by default in
`agents/mpc_sell`, as the task asked.

## What I built

`agents/mpc_sell/` = copy of `agents/mpc_bufplan` with `pulse_plan: true, pp_value: 20` as defaults (so its defaults are
the round-4 baseline). New options, all off by default:

| option | where | what |
|---|---|---|
| `sell_end` | `chips.py` | the wafer-buffer rows are dropped for window weeks with `week + t + fab tau + tail_lead > T` (tail_lead = OSAT tau + 2 shipping weeks = 4) |
| `sell_buffer` (+ `sell_frac` 0.9) | `chips.py` | solves the chip LP once without the buffer; at a fab whose planned starts stay under 90% of its LP capacity (so it is sales-limited, not power-limited), the buffer shrinks to 3 weeks of those planned starts; then the real solve |
| `pp_end_cut` | `pplan.py` | the pulse planner gives fab energy zero value in those end weeks. This touches pulse logic but applies to every grid; it is not the CN/JP/SEA work of task 18 |

There is also a `STATS` counter in `agent.py` (weeks the chip LP ran, was skipped for time, or failed), read by the
diagnostic. On this machine the LP ran 104/104 weeks in every episode, so on Full the chip LP is never skipped here.

## Measurement first (Full devpick:2,2,1,1 = episodes 2, 5, 0, 1, 53, 26; baseline = mpc_sell defaults)

Scripts: `outputs/task-19/diag19.py` (plays the agent the way cost_breakdown does and records chip stock, disposal,
shipments and requested vs executed amounts per week), `an19.py` (tables), `ts19.py` (time series per slot),
`marks19.py` (true edge capacities from the marks), `bound19.py` (ceiling LPs), `topo19.py` (Full's chip network,
`topo_full.txt`).

Chips disposed per episode: chip_mat_raw 5.1M (fab_us_mature_1 3.1M, fab_eu_mature_1 1.1M, fab_us_mature_2 0.8M),
chip_mat 3.1M (osat_tw 1.6M, osat_cn 1.0M), chip_le 3.2M (osat_kr 1.2M, osat_my 0.9M, osat_tw 0.7M), chip_le_raw 1.6M
(US leading fabs). Valued at pi, that is 0.32 T disposed plus 0.12 T left in stock at the end. **But that value isn't
reachable:**

- **Why it overflows (episode 2, osat_kr chip_le):** osat_kr ships 101,821 chip_le every week, exactly the edge
  capacities `marks.u` of this episode (osat_kr→sink_us 16.8k of a nominal 74.8k, →sink_sea 8.1k of 35.9k, …). The chip
  LP requests exactly that, and the simulator executes all of it (requested = executed on every chip slot). osat_my's
  sink edges are cut too (→sink_us 25k of 101k, →sink_row 2k of 32k). So the surplus has nowhere to go, even though
  sink_us loses 13.8M chip_le.
- **Ceiling LP** (`bound19.py`): the package's clairvoyant LP with every fab's weekly starts capped at what the agent
  actually started. Its chip shortage is the best any routing or "start fewer" policy could do with the agent's own
  production, with perfect foresight of capacities and demand. Variant "gridE": the LP may instead move each grid's
  weekly fab energy (capped at the agent's) between that grid's fabs.

```
  ep  agent short  capped LP   gridE LP    free LP  agent-capped  agent-gridE | lots agent / capped LP / gridE LP (M)
   2        2.415      2.350      2.341      2.300         0.065        0.074 | 104.7 / 64.3 / 65.2
   5        2.020      1.886      1.842      1.457         0.134        0.177 | 101.3 / 85.9 / 85.3
   0        2.375      2.143      2.074      1.923         0.232        0.301 | 97.5 / 72.0 / 71.3
   1        1.678      1.615      1.607      1.235         0.063        0.070 | 86.8 / 67.3 / 68.1
  53        2.300      2.238      2.211      1.563         0.062        0.089 | 70.7 / 56.2 / 57.0
  26        2.634      2.568      2.508      2.038         0.066        0.125 | 55.9 / 43.2 / 43.2
mean agent - gridE-LP shortage: 0.140 T USD/episode (+ moving each grid's fab power between its fabs)
mean agent - capped-LP shortage: 0.104 T USD/episode (routing + start-capping ceiling)
```

  The capped LP uses only 61-85% of the agent's lots, which confirms that a lot of the output is unsellable. But it
  sells only 0.10 T more, spread thinly over every sink (largest: sink_cn chip_mat 0.029, sink_sea chip_le 0.026,
  sink_us chip_le 0.017 T). Capping starts by itself saves only the disposal cost (0.015 T). The rest of the gap to the
  free oracle (≈0.5 T here) is new production at CN/JP/SEA, which is task 18. These ceilings assume foresight, so the
  reachable part is smaller.

## Funnel (baseline `{"agent": "agents/mpc_bufplan", "params": {"pulse_plan": true, "pp_value": 20}}`)

```
small, entropy 1005861973, 20 episodes; diff = variant - bufplan_pp20, 90% paired interval
variant                      RSS     L1     L2     L3     L4     diff  interval               better%  fallb
bufplan_pp20              0.7462  0.722  0.782  0.737      -  +0.0000  [+0.0000, +0.0000]     nan%      0
sell_end                  0.7488  0.719  0.792  0.737      -  +0.0026  [-0.0010, +0.0062]    88.4%      0
sell_buffer               0.7460  0.721  0.782  0.737      -  -0.0002  [-0.0024, +0.0017]    45.5%      0
sell_both                 0.7479  0.719  0.791  0.735      -  +0.0017  [-0.0023, +0.0058]    77.5%      0

full, entropy 0, 6 episodes; diff = variant - bufplan_pp20, 90% paired interval
variant                      RSS     L1     L2     L3     L4     diff  interval               better%  fallb
bufplan_pp20              0.8219  0.828  0.836  0.795  0.786  +0.0000  [+0.0000, +0.0000]     nan%      0
sell_end                  0.8287  0.837  0.841  0.798  0.797  +0.0068  [+0.0059, +0.0079]   100.0%      0  <-- better
sell_buffer               0.8215  0.830  0.838  0.786  0.778  -0.0004  [-0.0022, +0.0013]    31.8%      0
sell_both                 0.8269  0.840  0.841  0.786  0.786  +0.0050  [+0.0039, +0.0061]   100.0%      0  <-- better

full, entropy 0, 6 episodes (second round)
pp_end_cut                0.8241  0.830  0.842  0.794  0.784  +0.0022  [+0.0011, +0.0032]   100.0%      0  <-- better
end_both                  0.8247  0.830  0.842  0.795  0.786  +0.0028  [+0.0016, +0.0039]   100.0%      0  <-- better
(sell_end + pp_end_cut; same baseline 0.8219, sell_end 0.8287 in that round)

full, entropy 0, 20 episodes (dev)
variant                      RSS     L1     L2     L3     L4     diff  interval               better%  fallb
bufplan_pp20              0.7820  0.767  0.834  0.764  0.704  +0.0000  [+0.0000, +0.0000]     nan%      0
sell_end                  0.7864  0.773  0.837  0.767  0.709  +0.0044  [+0.0029, +0.0059]   100.0%      0  <-- better
sell_both                 0.7850  0.774  0.835  0.760  0.707  +0.0030  [+0.0003, +0.0056]    96.7%      0  <-- better
```

The baseline reproduces the team's 0.7820 exactly. Results: `outputs/variants/variants19*/results.json`; raw output:
`outputs/task-19/run_*.txt`.

**Why sell_end helps:** on Full 6, sell_end − base = shed −23.7 B, disposal −0.14 B, holding −0.04 B, shortage +0.04 B USD
per episode. In the last ~10 weeks the fabs no longer hold a 3-week wafer buffer, so the pulse planner (which values the
wafers on hand at pi) stops holding fuel back for fab power whose chips could never be sold. Lots started in the last
10 weeks drop from 7.4M to 1.2M. The direct version, `pp_end_cut`, does less (+0.002). I didn't dig into why
(probably wafers already at the fabs still draw power and still get valued through the energy LP / plain pulse).

## Before / after (Full 6, M chips per episode; oracle lots = task 17's LP on the same episodes)

```
                  disposed base -> sell_end    end stock base -> sell_end
chip_mat_raw            5.08 -> 4.92                 1.12 -> 0.57
chip_mat                3.07 -> 3.07                 4.46 -> 4.41
chip_le                 3.17 -> 3.17                 0.75 -> 0.75
chip_le_raw             1.55 -> 1.51                 0.37 -> 0.14

lots (M)            base (last 10 wk)   sell_end (last 10 wk)   oracle
fab_tw_leading_1     7.97 (0.65)          7.34 (0.06)          7.17
fab_tw_mature_1      5.84 (0.52)          5.38 (0.07)          4.26
fab_us_leading_1     1.35 (0.10)          1.22 (0.00)          0.94
fab_kr_leading_1     2.38 (0.17)          2.22 (0.01)          1.36
fab_kr_memory_1     18.32 (1.30)         16.98 (0.08)         15.16
fab_us_leading_2     0.90 (0.06)          0.82 (0.00)          0.58
fab_jp_memory_1      3.01 (0.22)          2.87 (0.09)          5.92
fab_us_leading_3     1.26 (0.09)          1.15 (0.00)          0.40
fab_eu_leading_1     0.82 (0.08)          0.73 (0.00)          0.73
fab_row_leading_1    0.47 (0.05)          0.42 (0.00)          0.61
fab_cn_mature_1     16.59 (1.89)         15.41 (0.74)         23.49
fab_us_mature_1      7.03 (0.59)          6.45 (0.01)          3.22
fab_eu_mature_1      6.36 (0.65)          5.77 (0.04)          4.17
fab_sea_mature_1     1.14 (0.00)          1.14 (0.00)          4.60
fab_tw_mature_2      5.39 (0.47)          4.96 (0.05)          4.20
fab_us_mature_2      7.34 (0.56)          6.79 (0.02)          5.80
```

Disposal during the episode barely changes, as expected: it is transport-limited, not caused by the end of the episode.

## sbf check (`outputs/task-19/ag_sellend` = agents/mpc_sell + `{"sell_end": true}`)

Both pass: 5 files, nothing imported outside the allowed set.
- Small: week 1 0.082 s, median act 0.060 s, **max 0.094 s** (budget 2 s)
- Full: week 1 0.276 s, median act 0.184 s, **max 0.276 s** (budget 4 s)

This cloud machine is fast: 6 Full episodes in ~45 s on 4 workers.

## Surprises / notes for other cloud sessions

- **The naive F_Q disk cache is keyed on the Python patch version.** The home cache (`cache/sbf-cache.tgz`) holds Full's
  F_Q entry for Python 3.13.5; this container runs 3.13.16, so the first Full world rebuilt it, single-threaded (~30 min,
  and my first attempt hit the 30-min tool limit). Fix: `EpisodeSet.build("full", "dev", entropy=0, n_jobs=4)` once
  (`outputs/task-19/fq19.py full small`: Full 21 min, Small 16 min). After that, the reference cache from the tgz is hit
  normally. Consider adding the 3.13.16 entries to the tgz.
- Episode-level edge capacity cuts (`marks.u`, constant all episode) are what make chips unsellable. They are visible in
  `graph_now.u`, and the chip LP already uses them.
- `outputs/task-19/diag19_*.json` hold the raw per-week data (6 Full episodes, baseline / sell_end / sell_buffer / both).
