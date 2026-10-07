Status: done — verdict **too small** (ceiling ≈ 0.01 T USD/episode, bar 0.17 T). Nothing built.

## Task 11: steer scarce fab power to the most valuable fabs (baseline agents/mpc_pulse)

### Method (outputs/task-11/power_steer.py)
- Plays mpc_pulse exactly as outputs/cost_breakdown.py does (same worlds/seeds/fallback). RSS check reproduces the
  board number: Full dev 20 RSS **0.6752** (known 0.6751), 0 fallback weeks.
- Only grids with ≥2 fabs can be steered: TW (leading + 2 mature), KR (leading + memory, both chip_le), US (3 leading +
  2 mature), EU (2 leading + mature). JP, CN, SEA have one fab; IN none. Only two chip products: chip_le (pi ≈ 50.5k)
  and chip_mat (pi ≈ 10.3k), so value per power unit = pi·R/e: memory ≈ 40 M, leading ≈ 25 M, mature ≈ 11 M USD/GWh.
- A grid-week is **power-limited** when some fab started fewer lots than p̂ = min(α·R·cap0, wafers on hand), with wafers
  on hand = end stock + lots started + disposal (base_first gives every fab the same factor, so one short fab = the grid
  is short). In those weeks the fabs' total energy ΣE is re-split greedily to the highest pi·R/e fabs, each up to its
  capacity draw e·α·cap0 (as if it held wafers). pi = 0 for a chip with no lost sales (never happened: both chips lose
  sales in every episode, 24-47 M chip_le and 70-87 M chip_mat units). Extra chips capped by lost units ("capped");
  "early" drops weeks too late for chips to reach a sink. Sum over weeks = ceiling.
- Looser bound (`ceiling_loose_all_weeks`): the same re-split in **every** grid-week with power to fabs, power-limited
  or not (in non-limited weeks this is really a wafer-supply lever, not power steering, so it overstates this lever).

### Results
Full devpick:2,2,1,1 (root 0, episodes 2,5,0,1,53,26):
```
written outputs/task-11/power_steer_full_0_devpick-2,2,1,1_mpc_pulse.json RSS check: {'rss': 0.7132132427710741, 'pooled': True, 'rss_all': 0.7104566263065007, 'rss_by_stratum': {1: 0.7250143869967227, 2: 0.7527935361456293, 3: 0.6252539833535259, 4: 0.7093238696319016}}
   ep lvl   lost USD   uncapped     capped capped,early  gain by grid (T USD)
    2   1      2.747     0.0316     0.0316       0.0316  {'grid_tw': 0.0308}
    5   1      2.619     0.0149     0.0149       0.0149  {'grid_tw': 0.0122, 'grid_kr': 0.0027}
    0   2      2.769     0.0031     0.0031       0.0031  {'grid_kr': 0.0031}
    1   2      2.073     0.0053     0.0053       0.0053  {'grid_kr': 0.005}
   53   3      3.172     0.0073     0.0073       0.0073  {'grid_kr': 0.0068}
   26   4      2.994     0.0072     0.0072       0.0072  {'grid_kr': 0.0065}
ceiling_uncapped       plain mean 0.0116 T, harm-weighted 0.0143 T, per level L1 0.0233, L2 0.0042, L3 0.0073, L4 0.0072
ceiling_capped         plain mean 0.0116 T, harm-weighted 0.0143 T, per level L1 0.0233, L2 0.0042, L3 0.0073, L4 0.0072
ceiling_capped_early   plain mean 0.0116 T, harm-weighted 0.0143 T, per level L1 0.0233, L2 0.0042, L3 0.0073, L4 0.0072
```
Full dev, all 20 (root 0):
```
written outputs/task-11/power_steer_full_0_dev_mpc_pulse.json RSS check: {'rss': 0.6752411297338179, 'pooled': True, 'rss_all': 0.6642854493764442, 'rss_by_stratum': {1: 0.6501867431542854, 2: 0.7521382026633144, 3: 0.6352797959609715, 4: 0.6324126718650402}}
   ep lvl   lost USD   uncapped     capped capped,early  gain by grid (T USD)
    0   2      2.769     0.0031     0.0031       0.0031  {'grid_kr': 0.0031}
    1   2      2.073     0.0053     0.0053       0.0053  {'grid_kr': 0.005}
    2   1      2.747     0.0316     0.0316       0.0316  {'grid_tw': 0.0308}
    3   2      3.614     0.0000     0.0000       0.0000  {}
    4   2      1.998     0.0384     0.0384       0.0384  {'grid_kr': 0.0103, 'grid_tw': 0.0281}
    5   1      2.619     0.0149     0.0149       0.0149  {'grid_tw': 0.0122, 'grid_kr': 0.0027}
    6   2      1.966     0.0007     0.0007       0.0007  {}
    7   1      2.436     0.0162     0.0162       0.0162  {'grid_kr': 0.0084, 'grid_tw': 0.0078}
   10   1      2.557     0.0012     0.0012       0.0012  {'grid_kr': 0.0012}
   14   1      2.650     0.0117     0.0117       0.0117  {'grid_kr': 0.0113}
   26   4      2.994     0.0072     0.0072       0.0072  {'grid_kr': 0.0065}
   41   4      3.437     0.0177     0.0177       0.0177  {'grid_tw': 0.0164, 'grid_kr': 0.0013}
   44   4      3.029     0.0073     0.0073       0.0073  {'grid_kr': 0.0073}
   53   3      3.172     0.0073     0.0073       0.0073  {'grid_kr': 0.0068}
   57   3      3.509     0.0097     0.0097       0.0097  {'grid_kr': 0.0097}
   61   3      3.026     0.0011     0.0011       0.0011  {}
   69   3      2.604     0.0067     0.0067       0.0067  {'grid_kr': 0.0052, 'grid_tw': 0.0014}
   76   3      3.214     0.0049     0.0049       0.0049  {'grid_kr': 0.0047}
   80   4      3.204     0.0132     0.0132       0.0132  {'grid_kr': 0.0129}
  102   4      3.168     0.0227     0.0227       0.0227  {'grid_kr': 0.0223}
ceiling_loose_all_weeks plain mean 0.1245 T, harm-weighted 0.1274 T, per level L1 0.1216, L2 0.1353, L3 0.1392, L4 0.1019
ceiling_uncapped       plain mean 0.0110 T, harm-weighted 0.0120 T, per level L1 0.0151, L2 0.0095, L3 0.0059, L4 0.0136
ceiling_capped         plain mean 0.0110 T, harm-weighted 0.0120 T, per level L1 0.0151, L2 0.0095, L3 0.0059, L4 0.0136
ceiling_capped_early   plain mean 0.0110 T, harm-weighted 0.0120 T, per level L1 0.0151, L2 0.0095, L3 0.0059, L4 0.0136
```

### Why it is small
- Power-limited weeks with power left for fabs are rare: TW 0-34 and KR 2-13 of 104 weeks per episode; US and EU never
  show up (their leftover is either 0 or enough for all wafers). In most weeks the fabs get either nothing (homes not
  fully served, base_first) or everything their wafers ask for.
- The chip value actually made in those contested weeks is only ~0.02-0.18 T/episode, so even a perfect split gains
  ~0.003-0.04 T. Most of the gain is TW (mature → leading) and KR (leading → memory).
- Even the loose all-weeks bound is 0.125 T/episode (harm-weighted 0.127 T) < 0.17 T.

### Verdict
Too small: ceiling 0.011 T/episode (≈ +0.003 RSS) on Full dev 20; loose upper bound 0.125 T (< 0.17 T). Not built.
The bottleneck is how often fabs get any power (pulses, tasks 12/14), not how the power is split.

### Choices made (nobody to ask)
- Used lost-weighted mean pi per packaged chip; chips are not traced to specific sinks or shipping lead times (both
  only lower the ceiling, so the verdict holds).
- Ran the cheap diagnostic on all 20 dev episodes too (25 s per 6 episodes) to make sure devpick wasn't unrepresentative.
