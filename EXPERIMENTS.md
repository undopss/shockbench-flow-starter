# Experiment log

Generated 2026-10-07 18:34 from the home server's queue (and cloud task branches).
Each row: one idea vs its baseline on the same episodes; diff = RSS(variant) - RSS(baseline); better/worse = the whole
90% paired interval is above/below 0. Stages: small20 (filter) -> full6 (devpick 2,2,1,1) -> full20 (official dev); fresh-* = never-used seeds.

| # | finished | verdict | idea | stage | seed | variant RSS | baseline RSS | diff | 90% interval | L1 (calm) | source |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 10-07 16:53 | **better** | Fuel pulses at Taiwan + Korea | small20 | 787505523 | 0.6889 | 0.6516 | +0.0373 | [+0.0183, +0.0568] | 0.659 | claude@home |
| 2 | 10-07 16:53 | **unclear** | Energy plan 20 weeks ahead (was 12) | small20 | 787505523 | 0.6510 | 0.6516 | -0.0006 | [-0.0026, +0.0014] | 0.616 | claude@home |
| 3 | 10-07 16:55 | **worse** | Chip planner (calibration on Small) | small20 | 787505523 | 0.5648 | 0.6516 | -0.0868 | [-0.1138, -0.0660] | 0.553 | claude@home |
| 4 | 10-07 16:56 | **unclear** | Fuel pulses at Taiwan + Korea + Japan, 2 weeks | small20 | 787505523 | 0.6610 | 0.6516 | +0.0094 | [-0.0154, +0.0318] | 0.637 | claude@home |
| 5 | 10-07 17:06 | **better** | Fuel pulses at Taiwan + Korea (Full check) | full6 | 0 | 0.6594 | 0.5802 | +0.0792 | [+0.0324, +0.1321] | 0.636 | claude@home |
| 6 | 10-07 17:08 | **better** | Fuel pulses at Taiwan only | small20 | 223948299 | 0.6749 | 0.6628 | +0.0121 | [+0.0022, +0.0220] | 0.677 | claude@home |
| 7 | 10-07 17:11 | **unclear** | Fuel pulses at every grid | small20 | 223948299 | 0.6700 | 0.6628 | +0.0072 | [-0.0132, +0.0279] | 0.677 | claude@home |
| 8 | 10-07 17:11 | **unclear** | Fuel pulses TW+KR, bigger batches (2.5 weeks) | small20 | 223948299 | 0.6858 | 0.6628 | +0.0230 | [-0.0021, +0.0473] | 0.687 | claude@home |
| 9 | 10-07 17:18 | **better** | Plan power-starved fabs at their real output | full6 | 0 | 0.6424 | 0.5802 | +0.0622 | [+0.0457, +0.0768] | 0.616 | claude@home |
| 10 | 10-07 17:20 | **better** | Plan fabs on grids with power cuts at their real output | full6 | 0 | 0.6424 | 0.5802 | +0.0623 | [+0.0438, +0.0785] | 0.619 | claude@home |
| 11 | 10-07 17:24 | **better** | Fuel pulses TW+KR (decision run) | full20 | 0 | 0.6373 | 0.5443 | +0.0930 | [+0.0601, +0.1242] | 0.595 | claude@home |
| 12 | 10-07 17:29 | **better** | Pulse TW/KR + real fab capacity (combo) | full6 | 0 | 0.7132 | 0.5802 | +0.1330 | [+0.0868, +0.1852] | 0.725 | claude@home |
| 13 | 10-07 17:31 | **unclear** | Automatic pulse (fab grids with power cuts) + real fab capacity | full6 | 0 | 0.6427 | 0.5802 | +0.0625 | [-0.0167, +0.1521] | 0.687 | claude@home |
| 14 | 10-07 17:35 | **better** | Plan power-starved fabs at their real output (decision run) | full20 | 0 | 0.5949 | 0.5443 | +0.0506 | [+0.0391, +0.0633] | 0.531 | claude@home |
| 15 | 10-07 17:38 | **unclear** | Automatic pulse (fab grids with power cuts) | small20 | 967288973 | 0.6511 | 0.6474 | +0.0038 | [-0.0165, +0.0246] | 0.710 | claude@home |
| 16 | 10-07 17:41 | **better** | Pulse at the starved grids KR+JP+SEA + real fab capacity | full6 | 0 | 0.7065 | 0.5802 | +0.1263 | [+0.0779, +0.1811] | 0.714 | claude@home |
| 17 | 10-07 17:42 | **better** | Pulse TW/KR + real fab capacity (decision run) | full20 | 0 | 0.6751 | 0.5443 | +0.1308 | [+0.0966, +0.1624] | 0.650 | claude@home |
| 18 | 10-07 17:43 | **better** | Pulse TW+KR+JP+SEA + real fab capacity | full6 | 0 | 0.7186 | 0.5802 | +0.1385 | [+0.0848, +0.1992] | 0.733 | claude@home |
| 19 | 10-07 17:45 | **better** | Pulse at Korea only + real fab capacity | full6 | 0 | 0.6996 | 0.5802 | +0.1194 | [+0.0780, +0.1663] | 0.702 | claude@home |
| 20 | 10-07 17:57 | **better** | pulse_twkrjpsea_15 (cloud task 2) | full6 | 0 | 0.6798 | 0.5802 | +0.0996 | [+0.0573, +0.1475] | 0.675 | cloud task 2 |
| 21 | 10-07 17:57 | **better** | pulse_jpsea_15 (cloud task 2) | full6 | 0 | 0.5972 | 0.5802 | +0.0170 | [+0.0148, +0.0194] | 0.553 | cloud task 2 |
| 22 | 10-07 17:57 | **unclear** | pulse_jpsea_25 (cloud task 2) | full6 | 0 | 0.5794 | 0.5802 | -0.0007 | [-0.0041, +0.0029] | 0.535 | cloud task 2 |
| 23 | 10-07 17:57 | **better** | pulse_twkrjpsea_15 (cloud task 2) | full6 | 0 | 0.6798 | 0.6596 | +0.0202 | [+0.0120, +0.0293] | 0.675 | cloud task 2 |
| 24 | 10-07 17:57 | **worse** | pulse_twkrjpsea_25 (cloud task 2) | full6 | 0 | 0.6468 | 0.6596 | -0.0128 | [-0.0203, -0.0043] | 0.635 | cloud task 2 |

## Before the queue (2026-10-06/07, `sbf compare` and our own scripts)

| result | where |
|---|---|
| heuristic: Full dev 0.370, Small dev 0.400, Codabench 0.4283 | home server |
| mine (Andrii): Full dev 0.352, Codabench 0.4487 | home server |
| mpc v2 vs mine: Small 64 eps +0.085, Full dev 0.5124 vs 0.3517 | home server |
| organisers' planners on Small 64: mpc_scen 0.731, mpc_det_safety 0.719, mpc_det 0.717, ours 0.565 | home server |
| organisers' planners on Full dev: mpc_det 0.372, mpc_det_safety 0.375 (worse than mpc: power) | home server |
| scen vs mpc, Full dev: 0.4196 vs 0.5124 (scen worse on Full); scen on Codabench 0.699 | cloud + Codabench |
| mpc_chip vs mpc, Full dev: 0.5443 vs 0.5124, +0.032 [+0.009, +0.056] | home server |
| **mpc_pulse on Codabench (submission 967249): 0.6896, 0 fallbacks** | Codabench |
| Chronos zero-shot demand forecast: worse than the game's own forecast (9.6% vs 9.0% error) | home server |
| chokepoint warning score predicts closures: AUC 0.507 (useless) | home server |
| tanker priorities at straits (cloud task 4): dead end, about 0 on Full 6; queues are caused by narrow edges after the straits, not throughput | cloud task 4, `results/task-4.md` on its branch |

## Ideas (plain words)

- **Fuel pulses at Taiwan + Korea:** Hold LNG/crude at TW/KR terminals until 1.5 weeks of burn, then release in a batch, so some weeks the grid is fully supplied and the chip fabs (homes-first rule) get power. Ceiling: chip shortage is ~95% of the gap; -8% shortage on Small = ~+0.08 RSS minus extra power cuts.
- **Energy plan 20 weeks ahead (was 12):** Longer energy planning window. For the organisers' planner the horizon was the biggest lever on Small (H12 0.57 -> H20 0.69 -> default 0.72). Ceiling: large if our 12-week window starves grids of slow fuel.
- **Chip planner (calibration on Small):** Old mpc as the variant against mpc_chip: measures how much the chip planner adds on Small (+0.06 seen on 6 Full episodes). Calibration of the Small filter.
- **Fuel pulses at Taiwan + Korea + Japan, 2 weeks:** Same pulse idea, also at Japan (memory fab), bigger batches (2 weeks of burn).
- **Fuel pulses at Taiwan + Korea (Full check):** Winner of Small round 1 (+0.037). Now on 6 Full dev episodes, all four harm levels.
- **Fuel pulses at Taiwan only:** Pulse shape: only TW (leading + mature fabs). Tells if KR adds or costs.
- **Fuel pulses at every grid:** Pulse shape: all grids incl. EU (2 Small eps earlier said worse; check on 20).
- **Fuel pulses TW+KR, bigger batches (2.5 weeks):** Pulse shape: fewer, bigger full weeks.
- **Plan power-starved fabs at their real output:** Full: KR/JP/SEA fabs run at ~1% (no power) but the chip planner assumed 100%, so it under-fed fabs that do have power (US fabs 2-35%). Plan a fab holding wafers at what it actually started recently. Ceiling: US fabs ~14% of demand -> up to ~+0.1 if they run full.
- **Plan fabs on grids with power cuts at their real output:** Same idea, simpler trigger: if the fab's grid shed homes last week, plan the fab at its recent output.
- **Fuel pulses TW+KR (decision run):** Passed small20 (+0.037) and full6 (+0.079). Final check on the 20 official Full dev episodes.
- **Pulse TW/KR + real fab capacity (combo):** Both Full-stage winners together: do they stack?
- **Automatic pulse (fab grids with power cuts) + real fab capacity:** No grid names: pulse any grid that feeds fabs and shed homes last week. Answers the overfitting worry; on Full it should reach JP/SEA.
- **Plan power-starved fabs at their real output (decision run):** Passed full6 (+0.062). 20 official Full dev episodes.
- **Automatic pulse (fab grids with power cuts):** Auto grid choice alone, Small filter on a fresh seed.
- **Pulse at the starved grids KR+JP+SEA + real fab capacity:** Full diagnosis: the TW/KR pulse works through Korea (KR fabs 1% -> 17-22%); Japan and SE Asia are starved the same way (power cuts 101 and 96 of 104 weeks, fabs ~1%). Ceiling: JP memory 144k + SEA mature 139k per week of capacity, ~17% of demand.
- **Pulse TW/KR + real fab capacity (decision run):** Combo passed full6 with +0.133 (pulse +0.079, fabcap +0.062 alone). 20 official Full dev episodes.
- **Pulse TW+KR+JP+SEA + real fab capacity:** Same, keeping Taiwan in the list (TW pulse was neutral on Full).
- **Pulse at Korea only + real fab capacity:** KR/JP/SEA (+0.126) and TW/KR (+0.133) give about the same on Full 6 and the Full diagnosis shows the gain comes from Korea's fabs (1% -> ~20%). If KR alone matches, the rule is simpler and less likely to be overfit.
- **pulse_twkrjpsea_15 (cloud task 2):** from branch task-2-pulse-jpsea, baseline mpc_chip
- **pulse_jpsea_15 (cloud task 2):** from branch task-2-pulse-jpsea, baseline mpc_chip
- **pulse_jpsea_25 (cloud task 2):** from branch task-2-pulse-jpsea, baseline mpc_chip
- **pulse_twkrjpsea_25 (cloud task 2):** from branch task-2-pulse-jpsea, baseline pulse_twkr_15
