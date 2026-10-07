Status: done. Verdict: too small (ceiling ≈ 0.036 T USD/episode, below the 0.17 T bar). Nothing built.

# Task 13: chips to the most expensive missing demand

## What I measured
`outputs/task-13/play.py` plays `agents/mpc_pulse` exactly as `outputs/cost_breakdown.py` does (same `_world`, policy
seed, metered shim, fallback) on **Full dev `devpick:2,2,1,1`** (episodes 2, 5, 0, 1, 53, 26) and dumps the chip-side
records per week (demand, served, lost, stock, disposal, packaged, chip shipments `x`). `outputs/task-13/analyze.py`
computes the numbers below. Full printout: `outputs/task-13/analyze6.txt`.
RSS of this run (check that the play is the scorer's): 0.7132 on these 6 episodes (by level 1: 0.725, 2: 0.753, 3: 0.625, 4: 0.709).

## Key facts (verified)
- **pi is the same at every sink for a product** on Full: chip_le 50,400-50,520 USD, chip_mat 10,280-10,400 USD
  (read from `inst.demands`). So moving chips from one sink to another of the same product cannot gain more than ~0.2%
  of pi per unit: there is no "most expensive missing demand" within a product.
- Sinks are lost-sales; a sink that loses sales in a week has 0 stock that week (served = min(demand, stock)).
- OSAT packaging is pro rata over raw types only when throughput binds. **It never bound while leading-edge raw chips
  waited and leading-edge sales were lost** (OSAT-mix lever = 0 on all 6 episodes).
- Lost sales are huge (mean 2.73 T USD/episode, 60% of chip demand value) but they come from chips **never made**, not
  chips stuck in the system.

## Ceiling (USD per episode, mean of 6)
| item | USD/episode |
|---|---|
| gap of mpc_pulse to clairvoyant | 1.04e12 |
| chip demand (pi × d) | 4.55e12 |
| lost sales (pi × U) | 2.73e12 |
| chips disposed (fab raw ~1.1e10, OSAT packaged ~1.4e10), at pi | 2.52e10 |
| chips left at the end (fab raw, OSAT, sinks, OSAT→sink shipments under way), at pi | 7.3e9 |
| sink misallocation: stock above next week's demand at one sink while another sink of the product lost sales, min(excess, lost) × pi | 3.6e9 (2.1e10 in ep 26, ~0 elsewhere) |
| OSAT le/mat mix | 0 |
| **time-aware ceiling** (chips never sold = end stock + disposal, assigned greedily to the earliest lost sales of their product in weeks the product had that much stock anywhere; lead times ignored → over-counts) | **3.25e10** |
| **upper bound used for the verdict** (ceiling + misallocation + mix, overlapping) | **3.62e10 ≈ 0.036 T** |

Per episode the upper bound ranges 1.4e10 … 5.8e10, never near 0.17 T. Note the misallocation number is not a real
gain anyway (same pi at all sinks; it only counts if those chips stayed unsold, which the ceiling row already covers).

## Verdict
**Too small**: chips already in the system can cover at most ~0.036 T USD/episode (≈ +0.01 RSS on Full, and that is an
optimistic bound), vs the 0.17 T bar. I did not run all 20 dev episodes: the bound is 5× under the bar on every one of the 6
episodes across all four harm levels. No agent built, no runner tables (no variant to compare).
The only non-trivial piece is chip disposal (~0.025 T, mostly OSAT leading-edge packaged chips above storage and
fab raw chips above storage); reducing it is worth ≤ ~+0.007 RSS. The chip gap is production (power to fabs), as tasks 11/12/14 assume.

## Choices made without asking
- devpick 6 only (no 20-dev run) because the ceiling is far below the bar.
- pi per product taken as the mean over sinks (they differ by <0.3%).
