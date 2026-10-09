Status: measured baseline split, building/testing mpc_steer

# Task 32: steer power to the most valuable fab inside a grid (`agents/mpc_steer`)

## 1. Measurement (baseline mpc_imit_room, Full devpick:2,2,1,1, `outputs/task-32/probe32.py`)
RSS 0.8535 (L1-4 0.845/0.875/0.842/0.846), 0 fallback weeks. Per multi-fab grid, mean per episode (104 weeks).
A week is "partial" when the fabs got 2-98% of their nameplate draw. "best share" = top-value fab's share of the
fabs' power if the split were greedy by pi/e (value per GWh); gain = that re-split valued at pi (gross: assumes sellable).

| grid | full wk | partial wk | zero wk | fab GWh in partial wks | top share got | top share best | gross gain T/ep |
|---|---|---|---|---|---|---|---|
| TW (leading 25M/GWh vs 2× mature 11M) | 11.0 | 57.3 | 35.7 | 18.3k | 0.60 | 0.79 | 0.041 |
| KR (memory 40M vs leading 25M, same chip_le_raw) | 25.5 | 46.7 | 31.8 | 14.5k | 0.80 | 0.96 | 0.030 |
| US (3 leading vs 2 mature) | 16.2 | 69.8 | 18.0 | 14.0k | 0.13 | 0.20 | 0.036 (not sellable: US leading output already disposed 1.2M/ep) |
| EU (2 leading vs mature) | 20.2 | 24.5 | 59.3 | 5.3k | 0.19 | 0.25 | 0.005 |

Low-value fabs hold 1.2-1.7 weeks of nameplate wafers in partial weeks (the 3-week buffer), so the split follows
nameplate, as task 28 said. Fab output disposed at the fab (per ep): 0 at TW and KR; US leading 1.19M, US mature 3.9M,
EU 1.2M, JP 0.19M. Sellable gross ceiling ≈ TW+KR ≈ 0.07 T/ep ≈ 0.02 RSS: **below the +0.05 bar even if fully captured.**
