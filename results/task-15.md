Status: done — verdict: too small (no build)

# Task 15: are the early warnings worth something? (Full, baseline agents/mpc_buffer)

**Verdict: no.** Even *perfect* foresight of every event that starts during a Full episode is worth at most
**0.127 T USD/episode (≈ +0.043 RSS; SE 0.044 T, median 0.058 T)** for mpc_buffer — below the 0.17 T bar — and the real
signals are far from perfect (warning AUC 0.51-0.67). So nothing was built.

Biggest surprise: with **all** in-episode events removed, mpc_buffer is still 0.70 T/episode behind the clairvoyant plan
(gap with events 0.83 T). **~85% of our remaining Full gap has nothing to do with disruptions**: it is planning in calm
conditions (chips/power), which is where round-3 effort should go.

## Step 1: signal quality (120 Full episodes, gym `ShockBench/Full-v0` episodes 0-119, ground truth from each omega)

Script `outputs/task-15/signals.py full 120 4` (log `signals_full_120.log`). Warning units on Full: 14 regions, 1 dyad
(CN-TW), 7 chokepoints. Labels: region unit = onset of any tariff/sanction/outage/closure/conflict/piracy/energy event
touching the region, or a conflict-state onset (z_c none→minor/war) / regional conflict; dyad = z_dyad escalation or a
conflict between/inside CN, TW; chokepoint = closure of that node. Messages: a thread is "real" if a real omega event of
the channel's type, region and target was announced when the thread appeared. Pending prohibitions: real if the edge
really is prohibited for k at the stated week (`marks.prohibited`).

```
full: 120 episodes, 22 warning units (14 regions, 1 dyads, 7 chokepoints)

events starting inside the episode, per episode: {'energy_shock': 4.23, 'material_outage': 0.93, 'militarised_closure': 0.95, 'piracy': 0.69, 'port_strike': 2.62, 'regional_conflict': 0.47, 'sanction': 9.5, 'tariff': 8.38, 'weather_closure': 2.73}

warning.score -> event onset within K weeks (pooled unit-weeks; AUC 0.5 = useless)
  unit kind  target                   K base rate    AUC prec@top5% prec@top1%
  chokepoint closure                  4     1.95%  0.525      1.83%      2.02%
  chokepoint closure                  8     3.84%  0.519      3.47%      3.47%
  chokepoint closure                 12     5.69%  0.513      4.94%      5.30%
  chokepoint militarised_closure      4     0.45%  0.605      0.95%      1.07%
  chokepoint militarised_closure      8     0.86%  0.589      1.61%      1.49%
  chokepoint militarised_closure     12     1.26%  0.579      2.25%      1.55%
  dyad       conflict_between         4     0.07%  0.297      0.00%      0.00%
  dyad       conflict_between         8     0.12%  0.321      0.00%      0.00%
  dyad       conflict_between        12     0.16%  0.349      0.00%      0.00%
  dyad       conflict_in_either       4     0.10%  0.523      0.67%      0.00%
  dyad       conflict_in_either       8     0.18%  0.539      1.22%      0.00%
  dyad       conflict_in_either      12     0.23%  0.524      1.27%      0.00%
  dyad       dyad_war_onset           4     0.25%  0.661      1.33%      4.17%
  dyad       dyad_war_onset           8     0.49%  0.658      2.78%      7.76%
  dyad       dyad_war_onset          12     0.73%  0.673      4.35%     11.71%
  region     any_PM_event             4     6.92%  0.509      7.45%      6.49%
  region     any_PM_event             8    12.61%  0.508     13.13%     11.10%
  region     any_PM_event            12    17.90%  0.507     18.34%     14.88%
  region     conflict_onset           4     0.26%  0.651      0.64%      0.48%
  region     conflict_onset           8     0.51%  0.650      1.30%      0.99%
  region     conflict_onset          12     0.77%  0.646      1.98%      1.55%
  region     regional_conflict        4     0.24%  0.586      0.33%      0.00%
  region     regional_conflict        8     0.45%  0.590      0.69%      0.00%
  region     regional_conflict       12     0.68%  0.593      1.09%      0.00%

warning lead: share of onsets preceded (1..12 weeks before) by a score above the unit kind's 95% quantile, and the median weeks between the first such week and the onset
  chokepoint closure                onsets   438  warned  13.9%  median lead  7.0 w
  chokepoint militarised_closure    onsets   111  warned  23.4%  median lead  7.0 w
  dyad       conflict_between       onsets     2  warned   0.0%  median lead  nan w
  dyad       conflict_in_either     onsets     3  warned  33.3%  median lead  7.0 w
  dyad       dyad_war_onset         onsets     8  warned  25.0%  median lead 12.0 w
  region     any_PM_event           onsets  4045  warned   6.5%  median lead 12.0 w
  region     conflict_onset         onsets   113  warned  14.2%  median lead 12.0 w
  region     regional_conflict      onsets   112  warned   7.1%  median lead 12.0 w

real events starting in the episode: share announced on each channel, median lead (weeks)
  tariff               n= 1006  tariff_formal 56% (lead 9.5); tariff_informal 44% (lead 3.2); tariff_final 100% (lead 0.9)
  sanction             n= 1140  sanction_legal 100% (lead 0.0); ties_threat 100% (lead 0.0)
  material_outage      n=  111  never announced
  militarised_closure  n=  114  mid_threat 100% (lead 1.0)
  regional_conflict    n=   57  never announced
  piracy               n=   83  never announced
  energy_shock         n=  508  never announced
  weather_closure      n=  328  never announced
  port_strike          n=  314  never announced

message threads seen by an agent (real = matches a real omega event; lead = onset week - first seen)
  mid_threat                           threads    145 (  1.2/ep)  real  78.6%  median lead (real)   0.0 w
  sanction_legal                       threads    152 (  1.3/ep)  real  43.4%  median lead (real)   4.0 w
  sanction_legal+ties_threat           threads     99 (  0.8/ep)  real  48.5%  median lead (real)  16.5 w
  tariff_formal                        threads    228 (  1.9/ep)  real  79.8%  median lead (real)   6.0 w
  tariff_formal+tariff_final           threads    509 (  4.2/ep)  real  77.8%  median lead (real)   7.0 w
  tariff_informal                      threads    171 (  1.4/ep)  real  68.4%  median lead (real)   3.0 w
  tariff_informal+tariff_final         threads    432 (  3.6/ep)  real  70.6%  median lead (real)   2.0 w
  ties_threat                          threads    976 (  8.1/ep)  real  52.4%  median lead (real)  12.0 w

pending_prohibitions entries: 264 (2.2/ep), really prohibited at their week 52.3%, median lead (real) 5.0 w
```

Reading:
- **warning.score is close to useless**: AUC 0.51-0.52 vs closures and vs "any event in the region"; best is the CN-TW
  dyad vs war onset (AUC 0.66, top-1% precision 4-12%), but that happened 8 times in 120 episodes (and conflicts
  between CN and TW 2 times). Region units vs conflict onset: AUC 0.65, top-5% precision ≤2%.
- **messages**: every tariff, sanction and militarised closure is announced, but: tariffs' final notice ~1 week ahead
  (formal proposals ~6-9 weeks, 68-80% real); sanctions 43-52% real (TIES threats ~12 weeks ahead); MID threats 79% real
  but the agent sees them ~0 weeks before the closure. Regional conflicts, energy shocks, weather, strikes, piracy and
  material outages are never announced.
- **pending_prohibitions** (already used by mpc_buffer/chips.py as if certain): only **52%** come true (decoys).
  Not tested whether discounting them helps; given sanctions' total ceiling below (0.023 T) it can't reach the bar.

## Step 2: value of information (Full root 0, episodes 0-19, mpc_buffer)

Script `outputs/task-15/voi.py full 0 0,...,19 agents/mpc_buffer 4` (JSON
`voi_full_0_0_..._19.json`, log `voi_20.log`). For each class, the events of that class whose onset is inside the
episode are removed from omega (carried-in events stay; marks recomputed; demand shocks, decoys and warnings untouched),
then mpc_buffer is played exactly as `sbf evaluate` plays it and the clairvoyant LP is solved.
**Ceiling = (J_agent(ω) − J_agent(ω − class)) − (J_oracle(ω) − J_oracle(ω − class))**: how much more the agent loses to
that class than the clairvoyant plan (which already has perfect foresight). A foresighted agent can at best lose no more
than the clairvoyant plan to the class. Classes: announced = tariff + sanction + militarised closure (messages);
conflict = regional conflict (region/dyad units); closures = militarised + weather (chokepoint units).

```
episodes [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19], classes ['base', 'all', 'announced', 'conflict', 'closures', 'tariff', 'sanction', 'energy_shock'], 160 runs
left out (failed runs): [(7, 'tariff', 'oracle not solved')]

base check: agent RSS per episode {0: 0.728, 1: 0.871, 2: 0.836, 3: 0.801, 4: 0.872, 5: 0.734, 6: 0.635, 7: 0.544, 8: 0.675, 9: 0.595, 10: 0.716, 11: 0.942, 12: 0.629, 13: 0.797, 14: 0.755, 15: 0.523, 16: 0.696, 17: 0.651, 18: 0.751, 19: 0.732} oracle reproduces cache: True

class          dropped/ep  dAgent T dOracle T ceiling T ceiling RSS   per episode (ceiling T)
all                  26.7     1.162     1.036     0.127       0.043   +0.262 -0.010 -0.009 +0.068 +0.023 -0.019 +0.352 +0.049 +0.226 +0.201 +0.101 -0.084 -0.096 +0.047 +0.190 +0.792 +0.219 +0.180 +0.036 +0.006
announced            15.9     0.633     0.550     0.082       0.027   +0.189 -0.008 +0.014 +0.034 +0.026 -0.020 +0.216 +0.002 +0.162 +0.117 -0.011 -0.099 -0.060 +0.047 +0.117 +0.769 +0.109 +0.032 +0.011 +0.002
conflict              0.2     0.000     0.000    -0.000      -0.000   +0.000 +0.000 +0.000 +0.000 +0.000 +0.000 +0.000 -0.000 +0.000 +0.000 -0.000 +0.000 +0.000 +0.000 +0.000 +0.000 +0.000 +0.000 +0.000 +0.000
closures              3.2     0.071     0.004     0.067       0.021   +0.001 -0.007 +0.005 +0.012 +0.077 -0.015 +0.002 +0.000 +0.004 +0.025 +0.060 +0.009 +0.021 +0.000 +0.134 +0.855 +0.078 +0.070 +0.005 -0.001
tariff                6.8     0.006     0.004     0.002       0.001   +0.010 -0.003 +0.004 +0.001 +0.007 -0.000 +0.013 +0.002 +0.000 -0.001 +0.004 -0.000 +0.001 -0.001 -0.001 -0.000 +0.002 +0.004 +0.000
sanction              8.4     0.564     0.541     0.023       0.009   +0.195 -0.005 +0.010 -0.003 -0.056 -0.019 +0.202 +0.001 +0.152 +0.116 -0.062 -0.109 -0.069 +0.046 +0.072 -0.121 +0.072 +0.030 +0.007 +0.002
energy_shock          3.9     0.479     0.462     0.017       0.006   +0.055 +0.001 +0.011 +0.004 +0.001 -0.003 +0.048 +0.045 +0.000 +0.038 +0.065 +0.000 -0.000 +0.000 +0.014 -0.000 +0.000 +0.060 +0.000 +0.000
```

- all events: ceiling mean 0.127 T (SE 0.044), median 0.058 T, without episode 15 0.092 T. Below 0.17 T.
- The ceiling of the classes that *have* a signal: announced 0.082 T (mostly sanctions' interaction; sanctions alone
  0.023 T, tariffs 0.002 T), closures 0.067 T (driven by one episode, #15, +0.86 T; chokepoint warnings have AUC 0.52
  and MID threats come ~0 weeks ahead, so not catchable), regional conflicts 0 (0.2/episode start inside an episode and
  they cost nothing here). Realistic value with the actual noisy signals is a fraction of these.
- Base mpc_buffer on these 20 episodes: mean RSS 0.724 (per-episode RSS in the log; computed with naive/clairvoyant
  from this script, not the shared cache — see below).

## Environment note (important for every cloud task)

In this cloud container the Full generator id is `7740c882…` while `cache/sbf-cache.tgz` (and the image's own
joblib cache from Oct 3) is for `93b801ef…`: same package sha (39ec701c95ac), same instance digest, same uv.lock, and
not the Python patch version (3.13.5 and 3.13.16 both give 7740c882). Small/Tiny differ too (d9adeaf8 vs d8f72cce).
So "Full dev episode 3" here is a **different omega** (hash dd5333… vs b6ae6e… in the cache): the cached references do
not apply, `devpick`/`dev` re-draw the dev split from scratch (very slow; I stopped it after 25 min) and cloud RSS
numbers on "root 0" are not the same episodes as the home server's. I did not find the cause (some non-.py package data?
something in the environment?). That's why step 2 uses root-0 episodes 0-19 (harm level not computed) instead of
devpick:2,2,1,1. Worth checking which generator id the scoring server uses.

## Files
- `outputs/task-15/signals.py`, `signals_full_120.log`, `signals_full_120_summary.json`
- `outputs/task-15/voi.py`, `voi_full_0_0_..._19.json`, `voi_20.log`; first 6-episode pass `voi_full_0_0_1_2_3_4_5.json`, `voi_1.log`
