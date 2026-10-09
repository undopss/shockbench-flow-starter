Status: done

agents/mpc_combo = mpc_jpow (agent.py, pplan.py) + mpc_final (chips.py, fb_kappa_ct option). Changes are disjoint (jpow: energy LP / pulse planner; final: chip LP + params), so the merge is mechanical. Running the reproduction check on Full dev (devpick:1,0,0,0).

Cache note (verified): on this cloud machine the reference cache key (`generator_id`) for Full is `7740c8824dd9c8ed`
(Small `d9adeaf8805a6767`), not the tgz's `93b801effce44fbf` / `d8f72ccef883e24c`, and the omega hashes differ too, so
the tgz cache is NOT used here and Full dev references were rebuilt (~28 min). But the episodes are the same: J_naive and
harm are identical on episodes 0, 5, 102 and J_oracle differs by 2 cents; dev RSS below matches tasks 30/33 exactly.
Next sessions can reuse the home cache by copying `full/93b801effce44fbf` to `full/7740c8824dd9c8ed` (and Small
`d8f72ccef883e24c` to `d9adeaf8805a6767`) under `~/.cache/shockbench-flow/references/v0.1.2-39ec701c95ac/` (not tested).

## 1. Reproduction check (Full dev episode 0 here = devpick:1,0,0,0, cloud generator)
mpc_combo with only jpow's params.json: J = 478022210632130 = mpc_jpow's J exactly (RSS 0.8706).
mpc_combo with only final's params.json: J = 473664773267382 = mpc_final's J exactly (RSS 0.8840). 0 fallbacks.

## 2. Full dev 20 (root 0), baseline agents/mpc_imit_room
```
full, entropy 0, 20 episodes; diff = variant - base, 90% paired interval
variant                      RSS     L1     L2     L3     L4     diff  interval               better%  fallb
base                      0.8228  0.821  0.858  0.791  0.755  +0.0000  [+0.0000, +0.0000]     nan%      0
combo                     0.8322  0.837  0.857  0.799  0.761  +0.0094  [+0.0030, +0.0165]    99.9%      0  <-- better
combo_safe                0.8331  0.841  0.858  0.792  0.759  +0.0103  [+0.0054, +0.0154]   100.0%      0  <-- better
jpow                      0.8319  0.840  0.853  0.797  0.759  +0.0091  [+0.0033, +0.0149]    99.9%      0  <-- better
final                     0.8270  0.826  0.861  0.797  0.757  +0.0043  [+0.0003, +0.0082]    96.4%      0  <-- better
```
combo = jpow + final params (union); combo_safe = jpow params + fb_kappa_ct only. Wins don't add: combo +0.0094 ≈ jpow
+0.0091; final's safety_weeks/pp_end/warn_gain add nothing on top of jpow. Fresh seed root: 540469033.

## 3. Fresh Full seed, root 540469033, 20 episodes (no harm-level-4 episode drawn)
```
full, entropy 540469033, 20 episodes; diff = variant - base, 90% paired interval
variant                      RSS     L1     L2     L3     L4     diff  interval               better%  fallb
base                      0.8345  0.832  0.818  0.889      -  +0.0000  [+0.0000, +0.0000]     nan%      0
combo                     0.8482  0.853  0.823  0.875      -  +0.0137  [+0.0041, +0.0247]    99.0%      0  <-- better
combo_safe                0.8458  0.851  0.819  0.875      -  +0.0113  [+0.0027, +0.0217]    98.6%      0  <-- better
jpow                      0.8387  0.842  0.816  0.874      -  +0.0043  [-0.0022, +0.0109]    86.5%      0
final                     0.8494  0.851  0.827  0.894      -  +0.0150  [+0.0088, +0.0222]   100.0%      0  <-- better
```
Mean of the two sets (40 episodes): combo +0.0116, combo_safe +0.0108, final +0.0097, jpow +0.0067. jpow and final
each win one set; combo is above 0 on both and the best on average -> **recommended: agents/mpc_combo with its
params.json (the full union)**.

## 4. sbf check + guard (agents/mpc_combo, this cloud machine)
- `sbf check mpc_combo --task=small`: all checks passed; week 1 0.119 s, median act 0.108 s, max 0.160 s (budget 2 s).
- `sbf check mpc_combo --task=full`: all checks passed; week 1 0.329 s, median act 0.292 s, max 0.449 s (budget 4 s).
- Guard (`outputs/task-34/guard_test.py 0 agents/mpc_combo`, = task 33's with the agent as argument), Full dev ep 0:
  A 484595110784995 = B (bogus grid names) ; C (grid_cn renamed) 483247395594149 = D (pp_direct without grid_cn); 0 fallbacks. Passed.

## 5. New gap map: agents/mpc_combo on Full dev 20 (root 0), vs mpc_imit_room and task 20's mpc_fab3sell (same episodes)
Runs: `outputs/task-17/gap17.py full 0 dev agents/mpc_{combo,imit_room} 4` (references reproduced 20/20, 0 fallbacks,
RSS check combo 0.8322 / imit_room 0.8228 = the runner's), `outputs/task-20/{map20,flow20,disp20}.py`, and a new
`outputs/task-34/map34.py` (side-by-side table, the a/b/c split of chip lost sales, per-episode list). map20 on task 20's
fab3sell JSON reproduces `outputs/task-20/map_full.txt` exactly. Raw: `outputs/task-34/{map34_full,map_*,flow_*,disp_combo}.txt`.

Gap to the clairvoyant plan, T USD/episode (0.01 RSS = 0.034 T):
```
component               fab3sell     imit_room         combo     d imit_room         d combo
freight                   0.0058        0.0057        0.0059         -0.0001          0.0001
tariff                    0.0103        0.0103        0.0103         -0.0000         -0.0000
holding                   0.0153        0.0154        0.0156          0.0001          0.0003
queue_holding             0.0009        0.0009        0.0008         -0.0000         -0.0001
shortage                  0.4714        0.4703        0.4449         -0.0011         -0.0265
disposal                  0.0125        0.0119        0.0139         -0.0005          0.0015
shed                      0.1971        0.1619        0.1596         -0.0352         -0.0376
salvage_credit           -0.0055       -0.0055       -0.0055         -0.0000         -0.0000
TOTAL                     0.7078        0.6710        0.6454         -0.0368         -0.0624
shed by grid:
  grid_tw                 0.0543        0.0532        0.0495         -0.0011         -0.0048
  grid_kr                 0.0299        0.0262        0.0271         -0.0037         -0.0028
  grid_jp                 0.0271        0.0270        0.0216         -0.0002         -0.0055
  grid_cn                 0.0304        0.0300        0.0360         -0.0005          0.0056
  grid_us                 0.0048        0.0048        0.0048          0.0000          0.0000
  grid_eu                 0.0219        0.0216        0.0221         -0.0003          0.0002
  grid_sea               -0.0037       -0.0037       -0.0051          0.0000         -0.0014
  grid_in                 0.0325        0.0030        0.0036         -0.0295         -0.0289
```
Chip lost sales split (unit balance; (a) = net lots oracle - agent x mean pi, (b) = extra disposal x pi, (c) = the rest:
made, not disposed, not sold in time / left at the end; sink-mix part ~0, so "cheaper sink" is not a leak):
```
fab3sell:
  chip_le   gap  0.3610 = (a) not made  0.0993 [ +1.97 M lots] + (b) disposed  0.1710 [ +3.39 M] + (c) rest  0.0908   | end stock 0.0379, sink-mix part -0.0001
  chip_mat  gap  0.1104 = (a) not made -0.0323 [ -3.13 M lots] + (b) disposed  0.0834 [ +8.07 M] + (c) rest  0.0593   | end stock 0.0391, sink-mix part -0.0006
imit_room:
  chip_le   gap  0.3589 = (a) not made  0.0971 [ +1.92 M lots] + (b) disposed  0.1704 [ +3.38 M] + (c) rest  0.0914   | end stock 0.0393, sink-mix part -0.0001
  chip_mat  gap  0.1114 = (a) not made -0.0315 [ -3.05 M lots] + (b) disposed  0.0838 [ +8.11 M] + (c) rest  0.0591   | end stock 0.0399, sink-mix part -0.0006
combo:
  chip_le   gap  0.3414 = (a) not made  0.0708 [ +1.40 M lots] + (b) disposed  0.1765 [ +3.50 M] + (c) rest  0.0942   | end stock 0.0415, sink-mix part -0.0001
  chip_mat  gap  0.1034 = (a) not made -0.0358 [ -3.46 M lots] + (b) disposed  0.0891 [ +8.62 M] + (c) rest  0.0501   | end stock 0.0309, sink-mix part -0.0006
  by sink (combo): sea/le 0.140, us/le 0.065, cn/mat 0.063, eu/le 0.036, in/le 0.031, jp/le 0.031, sea/mat 0.029, row/le 0.020
```
(a) is net: the agent over-makes at US/TW/EU fabs and under-makes at JP/KR/CN/SEA. Gross per-fab deficit (map20, lots x
pi, upper bound) is 0.817 T, of which 0.683 T in weeks the grid shed >= 1% of homes (base_first: no power left for fabs).
Disposal (disp20, combo): 8.57 M chip units/ep disposed in weeks the slot's out-edges were >= 95% full, 3.82 M with spare
out-capacity (mostly chip_mat at fab_eu_mature_1 / osat_tw / osat_cn), 0.01 M blocked; value at pi 0.274 T. Top:
osat_kr/chip_le 0.94 M, fab_us_mature_1 raw mat 3.41 M, fab_us_leading_3 raw le 0.61 M, osat_tw/chip_le 0.56 M, osat_my/chip_le 0.49 M.

**What jpow (+final) changed vs imit_room** (combo - imit_room, T/ep): total -0.026 (= +0.0075 RSS here). Shortage -0.025,
all chip_le "not made" (-0.026: fab_jp_memory_1 3.28 -> 3.89 M lots, fab_cn_mature_1 19.29 -> 19.66); shed JP -0.0055,
TW -0.004, SEA -0.0014 but CN +0.006; disposal +0.0015 and chip_le disposed +0.12 M (more chips, same out-edges).
Line by line vs task 20's fab3sell (total -0.062): -0.029 is grid_in shed (imit_room's fix), -0.027 shortage (jpow), the
rest small. Nothing changed on the disposal leak or the KR memory fab (12.99 -> 12.89 M lots vs oracle 14.11).

Per-episode RSS (combo, sorted):
ep41(L4) 0.544  ep57(L3) 0.721  ep6(L2) 0.724  ep80(L4) 0.753  ep102(L4) 0.753  ep61(L3) 0.764  ep69(L3) 0.785  ep7(L1) 0.788
ep0(L2) 0.790  ep10(L1) 0.797  ep76(L3) 0.814  ep26(L4) 0.845  ep14(L1) 0.857  ep3(L2) 0.865  ep5(L1) 0.866  ep53(L3) 0.874
ep2(L1) 0.877  ep44(L4) 0.879  ep4(L2) 0.906  ep1(L2) 0.929

5 worst (gap T/ep; a/b/c as above):
- ep 41 L4 0.544: gap 1.44 = chip_le 0.64 (not made 0.26, disposed 0.27) + chip_mat 0.28 + shed 0.50 (TW 0.23, CN 0.17). Shed + CN mature fab dark (-19 M lots): an energy storm (53 shocks).
- ep 57 L3 0.721: gap 0.88 = chip_le 0.50 (not made 0.29: JP memory -6.1 M lots) + shed 0.24 (TW, KR). JP memory fab dark.
- ep 6 L2 0.724: gap 0.64 = chip_le 0.46, almost all not made (0.40: JP memory -6.3 M, KR memory -2.3 M) with mat_kr_wafer outage wk 39: wafers, not power.
- ep 80 L4 0.753: gap 1.08 = chip_le 0.85, not made 0.74 (KR memory -10.8 M, JP memory -5.8 M lots, CN mature -20 M); shed small (0.04): fabs dark with homes served -> fab power/wafers, RU gas->CN and uranium->KR sanctions.
- ep 102 L4 0.753: gap 0.82 = shed 0.34 (TW 0.18, JP 0.07) + chip_le 0.32. A TW shed episode (101 shocks).

## Verdict
- **Final candidate: `agents/mpc_combo` with its params.json** =
  `{"kappa_lp": true, "pp_direct": ["grid_cn", "grid_eu"], "pp_split": true, "sell_end": true, "imit_grid": "room", "jp_qedge": true, "jp_arrfb": 0.2, "fb_kappa_ct": true, "safety_weeks": 4.0, "pp_end": 0.7, "warn_gain": 0.5}`.
  Full dev 20 +0.0094 [+0.0030, +0.0165] (0.8322), fresh root 540469033 ×20 +0.0137 [+0.0041, +0.0247] (0.8482), both
  intervals > 0; jpow alone fails the fresh seed (interval holds 0) and final alone is weaker on dev. sbf check Small +
  Full pass (max 0.16 / 0.45 s per week), guard test passes, 0 fallbacks everywhere. Not run: `small 0 dev` no-harm
  check (not asked for in task 34; Small is not a target). Not uploaded.
- The wins don't stack beyond ~+0.01: combo ≈ the better of the two on each set. Team goal Full ≥ 0.85 is not reached
  on dev (0.832); the fresh seed is at 0.848.

## 3 biggest remaining leaks (combo, Full dev 20, T USD/episode; 0.01 RSS = 0.034 T)
1. **Chips made and thrown away: ≈ 0.27 T** (chip_le 0.177 + chip_mat 0.089 at pi; disposal cost line only 0.014).
   Unchanged since task 20 and slightly worse with more lots. 69% of disposed units in weeks the slot's out-edges were
   ≥ 95% full (osat_kr, osat_tw, osat_my chip_le; US fabs' raw chips), so upstream: don't make / send chips that the
   OSAT's or fab's out-edges can't carry; for chip_mat 31% had spare out-capacity (fab_eu_mature_1, osat_tw, osat_cn) —
   the LP just didn't ship them. Reachable without foresight (out-capacities are observed).
2. **Fabs dark at JP / KR / CN / SEA when homes are shed: gross ≈ 0.68 T** (lots x pi upper bound; net chip_le "not made"
   only 0.07 T because US/TW/EU fabs over-make). JP memory 3.9 vs oracle 6.8 M lots, KR memory 12.9 vs 14.1, CN mature
   19.7 vs 22.8, SEA mature 1.6 vs 4.6. Dominates ep 6, 57, 80. The value at stake is the mix: memory/leading at JP/KR
   are worth 5x mature, so steering scarce fab power/wafers to them (not to US mature, which makes 3.6 M surplus and
   then disposes 3.4 M raw at fab_us_mature_1) is the lever.
3. **Home shed: 0.160 T** (TW 0.050, CN 0.036, KR 0.027, JP 0.022, EU 0.022); in the worst episodes (41, 102) TW shed
   alone is 0.18-0.23 T. Plus a smaller (c) "made, not disposed, not sold in time" ≈ 0.14 T (0.07 T of it is end stock).
