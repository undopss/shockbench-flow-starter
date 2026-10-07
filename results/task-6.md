Status: done

# Task 6: calm (harm level 1) episodes on Full

## Verdict
`agents/mpc_calm` = `mpc_pulse` + **reliable_bonus 300** (new, on by default in this folder only). Full dev 20 vs mpc_pulse:
**+0.0120 [+0.0082, +0.0163]**, better on every harm level (L1 0.650 -> 0.665), 0 fallbacks. On Small it is neutral
(+0.0024, interval holds 0). Below the +0.05 bar on its own, but it is robust, cheap (same CPU) and closes the reachable piece of the
L1 gap that I found. On top of plain mpc_chip settings the same option is worth +0.079 (most of it overlaps with `fab_cap_mode: observed`).
`sbf check`: Small and Full pass. CPU per week on this machine: Full max 0.321 s, median 0.217 s (mpc_pulse 0.313 / 0.215);
Small max 0.095 s, median 0.067 s. Not uploaded.

## Where calm episodes lose money (Full dev, `outputs/cost_breakdown.py full 0 dev ... 4`, USD per episode)
- mpc_chip L1: RSS 0.458, gap to clairvoyant 1.76 T, 99.9% chip shortage.
- mpc_pulse L1: RSS 0.650, gap 1.14 T: shortage 1.01 T (89%), shed 0.09 T (8%, the pulse's hold weeks).
- Calm episode 2, mpc_pulse vs oracle LP solution (`outputs/task6/oracle_dump.py`): chip loss 2.75 T vs 2.30 T.
  - **Unreachable (most of it):** CN and SEA fabs. grid_cn crude gets ~1693/wk vs 1800 burn, grid_sea gets no crude at all from
    week 9; the oracle gets the *same* fuel into those grids (checked: same inflows) and only powers the fabs because it relaxes homes-first.
    Leading-edge delivery is capped by OSAT->sink edges (several permanently at 0.25 of u0, one sanctioned): ~300k/wk vs 640k demand;
    the oracle ships 302k/wk, we shipped 264k/wk.
  - **Reachable:** US fabs (grid_us has spare power, no extra shed), JP memory, US mature_2. mpc_pulse ran US leading fabs at ~6%
    (oracle ~25-28%) because the chip LP filled the scarce leading-edge delivery capacity with *planned* output from pulsed KR/TW fabs,
    which under-delivers, and starved the US fabs of wafers (equal chip value, so the LP was indifferent).
- With reliable_bonus 300, episode 2: US leading 0.12/0.06/0.10M -> 0.55/0.42/0.57M lots (oracle 0.51/0.39/0.53), JP memory 0.68 -> 1.42M
  (oracle 1.37), US mature_2 5.1 -> 8.1M (oracle 7.9), CN 15.4 -> 17.9M; cost 5.064 -> 5.017 T.

## What I built
`agents/mpc_calm/chips.py`: `reliable_bonus` = a USD credit per raw chip shipped out of a fab (fab -> OSAT slots) whose grid shed no
homes last week and is not a pulse grid. It is a tie-break: well below the raw chip's disposal cost (2000 USD le / 400 mature), so the LP
never makes chips only to throw them away. Also `chip_growth` (observed-mode multiplier, default 1.25 = unchanged). Agent options:
`reliable_bonus` (300 here), `chip_growth`.

## Runner tables (exactly as printed)
### 1. fab_boost (existing option) on Full L1 dev episodes 2,5,7,10,14 (entropy 0): dead end
```
full, entropy 0, 5 episodes; diff = variant - mpc_pulse, 90% paired interval
variant                      RSS     L1     L2     L3     L4     diff  interval               better%  fallb
mpc_pulse                 0.6502  0.650      -      -      -  +0.0000  [+0.0000, +0.0000]     nan%      0
fab_boost_2               0.6505  0.651      -      -      -  +0.0003  [-0.0006, +0.0015]    66.3%      0
fab_boost_5               0.6517  0.652      -      -      -  +0.0015  [-0.0006, +0.0048]    68.6%      0
```
### 2. new options, same 5 L1 episodes
```
full, entropy 0, 5 episodes; diff = variant - mpc_pulse, 90% paired interval
variant                      RSS     L1     L2     L3     L4     diff  interval               better%  fallb
mpc_pulse                 0.6502  0.650      -      -      -  +0.0000  [+0.0000, +0.0000]     nan%      0
rel_bonus_300             0.6648  0.665      -      -      -  +0.0146  [+0.0076, +0.0231]   100.0%      0  <-- better
rel_bonus_1500            0.6641  0.664      -      -      -  +0.0140  [+0.0073, +0.0218]   100.0%      0  <-- better
chip_growth_1             0.6507  0.651      -      -      -  +0.0005  [-0.0009, +0.0024]    68.2%      0
```
### 3. Full dev 20 (entropy 0), baseline mpc_pulse
```
full, entropy 0, 20 episodes; diff = variant - mpc_pulse, 90% paired interval
variant                      RSS     L1     L2     L3     L4     diff  interval               better%  fallb
mpc_pulse                 0.6752  0.650  0.752  0.635  0.632  +0.0000  [+0.0000, +0.0000]     nan%      0
rel_bonus_300             0.6873  0.665  0.759  0.649  0.642  +0.0120  [+0.0082, +0.0163]   100.0%      0  <-- better
rel_bonus_1000            0.6870  0.664  0.760  0.648  0.641  +0.0117  [+0.0081, +0.0158]   100.0%      0  <-- better
```
### 4. Full dev 20 (entropy 0), baseline mpc_chip (bonus on mpc_chip's settings: no pulse, fab_cap full)
```
full, entropy 0, 20 episodes; diff = variant - mpc_chip, 90% paired interval
variant                      RSS     L1     L2     L3     L4     diff  interval               better%  fallb
mpc_chip                  0.5443  0.458  0.724  0.516  0.492  +0.0000  [+0.0000, +0.0000]     nan%      0
chip_rel_bonus_300        0.6237  0.569  0.772  0.571  0.528  +0.0794  [+0.0645, +0.0960]   100.0%      0  <-- better
```
### 5. Small, random root 130424204, 20 episodes
```
small, entropy 130424204, 20 episodes; diff = variant - mpc_pulse, 90% paired interval
variant                      RSS     L1     L2     L3     L4     diff  interval               better%  fallb
mpc_pulse                 0.5915  0.597  0.576  0.566      -  +0.0000  [+0.0000, +0.0000]     nan%      0
mpc_calm                  0.5939  0.600  0.576  0.576      -  +0.0024  [-0.0005, +0.0057]    90.5%      0
```

## Choices made without asking
- Baseline mpc_pulse (the current candidate) instead of mpc_chip for the main tests; also ran vs mpc_chip (table 4).
- Skipped the full6 stage (went straight to Full dev 20, which is cheap here with the references built).
- New folder `agents/mpc_calm` (copy of mpc_pulse), with the bonus on by default there; mpc_chip/mpc_pulse untouched.

## Surprises
- The shipped cache `cache/sbf-cache.tgz` did **not hit** here: its Full dir is `full/93b801ef...`, this machine computes generator_id
  `7740c882...` (Python 3.13.16 here; the id hashes the instance, maybe it differs by environment). References were rebuilt (~40 min) and
  agree with the home ones (naive identical, oracle within 5 cents). Copying `93b801ef...` to the new name would likely work.
- `fab_boost` stays useless on Full calm: the energy LP sees no shortfall at the fab grids (its pool counts terminal stock and early
  pipeline arrivals), and where fuel really is short (CN crude, SEA crude) it is physically capped anyway.
- Probes for anyone digging further: `outputs/task6/` (probe_week.py per-week dumps, show.py, oracle_dump.py, probe_grids.py;
  lp_dump.py/elp_dump.py need the debug lines removed from mpc_calm re-added).
