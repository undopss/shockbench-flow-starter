Status: done — nothing kept. Weighted map built (reconciles exactly to 1 − RSS); the calm-episode leaks are real but the policy-reducible ones did not beat mpc_best. Best variant on Full dev 20: nuc_c07 −0.0004 [−0.0019, +0.0007]. mpc_best stays the final.

# Task 41: score-weighted gap map and the worst calm episodes (`agents/mpc_calm2`)

Everything was run on the cached Full dev episodes only (root 0). There was no fresh-seed check, so treat the numbers as at risk of overfitting.

## 1. Weighted gap map of mpc_best (Full dev 20)

`uv run python outputs/task-17/gap17.py full 0 dev agents/mpc_best 4`: references reproduced on 20/20, 0 fallback weeks,
RSS 0.8454 (L1 0.850, L2 0.874, L3 0.810, L4 0.767). Then `uv run python outputs/task-41/map41.py outputs/task-41/gap17v2_full_0_dev_mpc_best.json`.
RSS points of item c in episode e = p_s / n_s × gap_c,e / DEN, where DEN = Σ_s p_s D̄_s (scoring/rss.py (56)).
The points add up to 1 − RSS exactly (0.15458 = 0.15458, residual 0). The columns are in points ×100 (so 6.6 means 0.066 RSS), next to USD T/ep.
The chip split is a unit balance per product (as in map34). In episodes where the agent overproduces, "a not made" is negative and "b disposed" is positive, and the two cancel. The net per product is the real lost-sales gap (le 8.15, mat 2.20).

```
20 episodes; levels [(1, 5), (2, 5), (3, 5), (4, 5)]; DEN = sum p_s Dbar_s = 3.2855 T
official pooled RSS 0.84542; 1 - RSS = 0.15458; sum of RSS points = 0.15458
one USD in an L1 episode is worth 10.0x one USD in an L4 episode

RSS points (x100 = 'points of RSS') and USD gap per episode (T), per level; sorted by pooled points
component                pooled pts   L1 pts   L2 pts   L3 pts   L4 pts    L1 T/ep  L2 T/ep  L3 T/ep  L4 T/ep  all T/ep
short/le/b_disposed           6.627    4.416    1.278    0.734    0.200     0.2902   0.1399   0.1607   0.1313    0.1805
short/mat/b_disposed          2.532    1.463    0.487    0.484    0.097     0.0962   0.0533   0.1061   0.0637    0.0798
short/le/c_rest               1.760    1.125    0.377    0.194    0.064     0.0739   0.0413   0.0425   0.0422    0.0500
short/le/c_endstock           1.492    0.844    0.446    0.154    0.047     0.0555   0.0488   0.0338   0.0312    0.0423
shed/kr                       1.204    1.031    0.051    0.125   -0.003     0.0677   0.0055   0.0273  -0.0017    0.0247
shed/cn                       0.866    0.215    0.344    0.260    0.047     0.0142   0.0377   0.0569   0.0308    0.0349
short/mat/c_rest              0.727    0.429    0.183    0.100    0.015     0.0282   0.0201   0.0219   0.0095    0.0199
short/mat/c_endstock          0.618    0.419    0.116    0.072    0.012     0.0275   0.0127   0.0157   0.0077    0.0159
shed/jp                       0.579    0.215    0.305    0.006    0.053     0.0141   0.0334   0.0014   0.0346    0.0209
shed/eu                       0.559    0.279    0.158    0.075    0.047     0.0183   0.0173   0.0164   0.0311    0.0208
holding                       0.524    0.302    0.136    0.066    0.020     0.0199   0.0149   0.0145   0.0128    0.0155
shed/tw                       0.503   -0.215    0.106    0.433    0.178    -0.0141   0.0116   0.0949   0.1168    0.0523
disposal                      0.472    0.294    0.098    0.064    0.017     0.0193   0.0107   0.0140   0.0109    0.0137
tariff                        0.360    0.239    0.077    0.027    0.017     0.0157   0.0085   0.0058   0.0111    0.0103
freight                       0.199    0.115    0.051    0.025    0.008     0.0076   0.0056   0.0055   0.0050    0.0059
shed/us                       0.096   -0.012    0.096   -0.003    0.015    -0.0008   0.0105  -0.0007   0.0100    0.0048
shed/in                       0.052    0.028    0.005    0.000    0.018     0.0018   0.0006   0.0000   0.0118    0.0036
queue_holding                 0.020    0.011    0.010   -0.001   -0.000     0.0007   0.0011  -0.0002  -0.0002    0.0004
war_risk                      0.002    0.001    0.000    0.000   -0.000     0.0001   0.0000   0.0000  -0.0000    0.0000
short/(other)                -0.000    0.000   -0.000   -0.000   -0.000     0.0000  -0.0000  -0.0000  -0.0000   -0.0000
shed/(rest)                  -0.000    0.000   -0.000   -0.000   -0.000     0.0000  -0.0000  -0.0000  -0.0000   -0.0000
(residual)                   -0.000   -0.000    0.000   -0.000   -0.000    -0.0000   0.0000  -0.0000  -0.0000   -0.0000
shed/sea                     -0.146   -0.043   -0.101    0.012   -0.014    -0.0028  -0.0110   0.0027  -0.0092   -0.0051
salvage_credit               -0.184   -0.106   -0.047   -0.024   -0.007    -0.0069  -0.0052  -0.0052  -0.0048   -0.0055
short/mat/a_notmade          -1.674   -1.190   -0.198   -0.319    0.033    -0.0782  -0.0216  -0.0699   0.0218   -0.0370
short/le/a_notmade           -1.727   -2.452   -0.435    0.730    0.430    -0.1611  -0.0477   0.1599   0.2824    0.0584
TOTAL                        15.458    7.408    3.544    3.215    1.292     0.4868   0.3881   0.7041   0.8488    0.6069

Groups (RSS points x100):
  short/le                  8.151   L1   3.933 L2   1.665 L3   1.812 L4   0.741
  shed                      3.711   L1   1.498 L2   0.964 L3   0.908 L4   0.341
  short/mat                 2.202   L1   1.121 L2   0.589 L3   0.337 L4   0.156
  holding                   0.524   L1   0.302 L2   0.136 L3   0.066 L4   0.020
  disposal                  0.472   L1   0.294 L2   0.098 L3   0.064 L4   0.017
  tariff                    0.360   L1   0.239 L2   0.077 L3   0.027 L4   0.017
  freight                   0.199   L1   0.115 L2   0.051 L3   0.025 L4   0.008
  queue_holding             0.020   L1   0.011 L2   0.010 L3  -0.001 L4  -0.000
  war_risk                  0.002   L1   0.001 L2   0.000 L3   0.000 L4  -0.000
  short/(other)            -0.000   L1   0.000 L2  -0.000 L3  -0.000 L4  -0.000
  (residual)               -0.000   L1  -0.000 L2   0.000 L3  -0.000 L4  -0.000
  salvage_credit           -0.184   L1  -0.106 L2  -0.047 L3  -0.024 L4  -0.007
```
**Reading it.** L1 holds 7.4 of the 15.5 lost points (L2 3.5, L3 3.2, L4 1.3).
- **chip_le net 8.15 pts** (L1 3.93). The largest item.
- **Shed 3.71 pts.** At L1 it is KR 1.03, which is almost all ep 5 (pulses). TW is negative at L1.
- **chip_mat 2.20 pts.**
- **Small leaks, together 1.55 pts (L1 0.95):** holding 0.52, disposal 0.47, tariff 0.36, freight 0.20.
- By USD-weighting, TW shed looked like the biggest shed (0.052 T/ep). In RSS terms it is behind KR, CN, JP and EU, because it sits at L3/L4.

## 2. Worst calm episodes (re-ranked on mpc_best: ep 7, 14, 10, 2, all L1; then ep 6 and ep 0 at L2)

Tools: `outputs/task-41/disp41.py` (disposal by slot, lots by fab, sales by sink) and `replay41.py` (weekly replay plus the oracle's weekly O/U/I/p).
```
Per-episode: RSS points lost (x100), episode RSS, J gap T, top 4 items (T)
  ep  7 L1 pts  2.434 RSS_e 0.788 gap 0.800  short/le/a_notmade +0.514, short/mat/a_notmade +0.238, shed/cn -0.113, short/le/c_rest +0.084
  ep 14 L1 pts  1.482 RSS_e 0.863 gap 0.487  short/mat/a_notmade -0.322, short/le/b_disposed +0.237, short/mat/b_disposed +0.205, short/le/a_notmade -0.107
  ep 10 L1 pts  1.335 RSS_e 0.826 gap 0.439  short/mat/a_notmade -0.215, short/mat/b_disposed +0.150, short/le/b_disposed +0.092, short/le/a_notmade +0.081
  ep  2 L1 pts  1.133 RSS_e 0.886 gap 0.372  short/le/a_notmade -1.257, short/le/b_disposed +1.037, short/le/c_endstock +0.132, shed/cn +0.129
  ep  6 L2 pts  1.113 RSS_e 0.739 gap 0.609  short/le/a_notmade +0.426, short/mat/a_notmade +0.041, shed/cn +0.040, short/le/c_rest +0.034
  ep  5 L1 pts  1.023 RSS_e 0.894 gap 0.336  shed/kr +0.173, shed/tw -0.121, short/le/b_disposed +0.086, short/le/c_rest +0.084
  ep  0 L2 pts  0.868 RSS_e 0.836 gap 0.475  short/mat/a_notmade -0.200, short/le/b_disposed +0.194, short/mat/b_disposed +0.109, shed/cn +0.101
  ep 57 L3 pts  0.746 RSS_e 0.741 gap 0.818  short/le/a_notmade +0.270, short/le/b_disposed +0.149, shed/tw +0.091, short/mat/b_disposed +0.086
  ep 76 L3 pts  0.693 RSS_e 0.825 gap 0.759  short/le/a_notmade +0.373, short/le/b_disposed +0.112, short/le/c_rest +0.041, short/mat/b_disposed +0.040
  ep 61 L3 pts  0.669 RSS_e 0.767 gap 0.733  short/mat/a_notmade -0.353, short/le/b_disposed +0.322, short/mat/b_disposed +0.233, shed/cn +0.120
  ep  4 L2 pts  0.603 RSS_e 0.909 gap 0.330  short/le/a_notmade -0.662, short/le/b_disposed +0.457, short/mat/a_notmade +0.163, short/le/c_endstock +0.136
  ep 69 L3 pts  0.572 RSS_e 0.810 gap 0.626  shed/tw +0.187, short/le/b_disposed +0.099, short/le/a_notmade +0.095, short/mat/b_disposed +0.095
  ep 53 L3 pts  0.534 RSS_e 0.873 gap 0.585  short/le/b_disposed +0.123, shed/cn +0.078, short/mat/b_disposed +0.077, short/mat/a_notmade +0.057
  ep  1 L2 pts  0.497 RSS_e 0.936 gap 0.272  short/le/a_notmade -0.087, short/le/c_endstock +0.081, short/mat/b_disposed +0.064, short/le/c_rest +0.053
  ep  3 L2 pts  0.463 RSS_e 0.887 gap 0.254  shed/jp +0.120, short/mat/b_disposed +0.082, short/mat/a_notmade -0.070, short/le/a_notmade +0.034
  ep 41 L4 pts  0.431 RSS_e 0.552 gap 1.417  short/le/b_disposed +0.251, short/le/a_notmade +0.248, shed/tw +0.236, short/mat/a_notmade +0.226
  ep 80 L4 pts  0.335 RSS_e 0.748 gap 1.101  short/le/a_notmade +0.731, shed/tw +0.095, short/le/b_disposed +0.088, short/mat/a_notmade +0.081
  ep102 L4 pts  0.245 RSS_e 0.756 gap 0.807  shed/tw +0.182, short/le/a_notmade +0.138, short/mat/b_disposed +0.099, short/le/b_disposed +0.098
  ep 26 L4 pts  0.150 RSS_e 0.857 gap 0.494  short/le/a_notmade +0.213, short/mat/a_notmade -0.102, short/mat/b_disposed +0.082, short/le/b_disposed +0.079
  ep 44 L4 pts  0.130 RSS_e 0.892 gap 0.426  short/le/b_disposed +0.141, short/le/a_notmade +0.082, shed/tw +0.062, short/mat/a_notmade -0.058
```
- **ep 7 (L1, 2.43 pts, RSS_e 0.788).** Too few chips made: CN mature −19.6 M lots, KR memory −7.5, JP memory −6.3, TW mature −3.6.
  This loses sea/le +0.31 T and cn/mat +0.17 T. The agent sheds CN homes 0.11 T *less* than the oracle; the oracle sacrifices CN homes to run the fabs.
  Cause: fab power at CN/JP/KR. This is foresight plus pulse planning, the territory of tasks 24/30/32, and was not attempted here.
- **ep 14 (1.48) and ep 10 (1.34).** Wrong mix. The agent makes *more* overall (US mature +7.7 / +5.8 M, CN +5.1 / +6.5, TW +2.8..4.0) but less JP memory (−2.7 / −3.4 M) and KR memory.
  It disposes of osat_tw chip_le 2.3 M (ep 14) and osat_tw chip_mat 5 M (ep 10), and loses le sales at sea/eu/jp/us.
- **ep 2 (1.13).** Sells exactly what the oracle sells, but overproduces le at every Asian fab and disposes of 17 M packaged le at osat_my/kr/tw/ph.
  The cost is CN shed +0.13 T plus fees. Its chip lines cancel out (not made −1.26, disposed +1.04).
- **Common to all of them:**
  1. OSAT finished-chip stocks sit at storage cap most of the episode (agent ~2 M le / ~4 M mat vs the oracle's 0.5–1.5 M). That gives disposal and the end-stock lines.
  2. In every one of these episodes, US fabs (us_mature_1/2, us_leading_1/2/3) dispose of raw chips at their storage cap for ~30 consecutive weeks. The wafer buffer keeps feeding them while their output cannot leave.
- **Holding** is mostly grid **nucfuel**: +11..19 B USD/ep vs the oracle (e.g. ep 14: CN +4.4 B, US +5.5 B, EU +5.8 B).
  Nucfuel days_cover is 364 days, so cover_frac 0.8 keeps ~42 weeks of burn. The oracle runs it down to ~8 weeks.

## 3. Fixes tried (`agents/mpc_calm2` = mpc_best + options, all off by default; `same` reproduces mpc_best exactly)
- `fuel_cover` / `fuel_safety`: per-fuel cover_frac / safety_weeks at every grid (energy LP floor).
- `gate_frac`: no wafer buffer at a fab whose raw-chip stock is ≥ gate_frac of its storage.

devpick 6 (`outputs/task-41/v41a.json`, `v41b.json`):
```
full, entropy 0, 6 episodes; diff = variant - best, 90% paired interval
variant                      RSS     L1     L2     L3     L4     diff  interval               better%  fallb
best                      0.8864  0.890  0.895  0.873  0.857  +0.0000  [+0.0000, +0.0000]     nan%      0
same                      0.8864  0.890  0.895  0.873  0.857  +0.0000  [+0.0000, +0.0000]     0.0%      0
nuc_c0                    0.6981  0.815  0.581  0.661  0.483  -0.1883  [-0.2531, -0.1310]     0.0%      0  <-- worse
nuc_c0_s2                 0.6781  0.802  0.553  0.642  0.447  -0.2083  [-0.2835, -0.1419]     0.0%      0  <-- worse
gate90                    0.8843  0.889  0.897  0.862  0.852  -0.0020  [-0.0025, -0.0016]     0.0%      0  <-- worse

results: outputs/variants/v41a_full_0_1010-1001/results.json
```
```
full, entropy 0, 6 episodes; diff = variant - best, 90% paired interval
variant                      RSS     L1     L2     L3     L4     diff  interval               better%  fallb
best                      0.8864  0.890  0.895  0.873  0.857  +0.0000  [+0.0000, +0.0000]     nan%      0
nuc_c07                   0.8866  0.889  0.896  0.873  0.857  +0.0002  [-0.0006, +0.0010]    76.5%      0
nuc_c06                   0.8870  0.892  0.894  0.874  0.849  +0.0007  [-0.0001, +0.0015]    94.8%      0
nuc_c09                   0.8855  0.889  0.894  0.872  0.856  -0.0009  [-0.0010, -0.0008]     0.0%      0  <-- worse

results: outputs/variants/v41b_full_0_1010-1006/results.json
```
Full dev 20 (`outputs/task-41/v41c.json`):
```
full, entropy 0, 20 episodes; diff = variant - best, 90% paired interval
variant                      RSS     L1     L2     L3     L4     diff  interval               better%  fallb
best                      0.8454  0.850  0.874  0.810  0.767  +0.0000  [+0.0000, +0.0000]     nan%      0
nuc_c07                   0.8450  0.849  0.874  0.810  0.765  -0.0004  [-0.0019, +0.0007]    31.6%      0
nuc_c06                   0.8439  0.849  0.871  0.811  0.760  -0.0015  [-0.0047, +0.0010]    23.4%      0
nuc_c05                   0.8358  0.847  0.852  0.802  0.752  -0.0097  [-0.0178, -0.0020]     1.6%      0  <-- worse

results: outputs/variants/v41c_full_0_1010-1009/results.json
```
**The nucfuel cover is insurance, not waste.** Cover 0 costs +0.5..1.3 T in 5 of 6 episodes and saves 0.009 T in the other one.
Below ~0.7 it starts to lose on dev 20, and that loss is at L2 and L4 too. The devpick +0.0007 of 0.6 did not hold up.
Gating the wafer buffer at full US raw stock is −0.002 (the same result as task 19/37's sell_buffer).

## Verdict
No change is kept: `agents/mpc_best` stays the final, and nothing new was checked or packed.
In RSS terms the "small leaks" are worth 1.55 pts in total, and the biggest of them (holding) is mostly foresight-limited nucfuel insurance.
What is left at L1/L2 is the chip *mix*:
1. Too little JP/KR memory and CN/SEA output in power-short weeks (ep 7, 6, 0, 10, 14). This is power/foresight.
2. Over-production of chips that cannot reach a sink: the US fabs, OSATs at cap, ep 2. Two generic gates (sell_buffer, gate90) have now failed on it.
A fix would have to value a fab's wafers by what its chips can actually sell *and* still keep the buffer that catches power windows.

## Choices made without asking
- Took the 4 worst by RSS points (all L1: 7, 14, 10, 2) and also showed L2 eps 6 and 0, since ep 6 (1.11) is close to ep 2.
- Stopped after dev 20 showed no positive variant; no Small or fresh runs (the speed rule).
- Did not touch pulse/pplan code (task 40 runs in parallel).
