# Task 4: tanker priorities at straits — verdict: dead end (no +0.05 on Full)

## What was built
`agents/mpc_chip/tankers.py` + options in `agents/mpc_chip/agent.py`, **all off by default** (baseline unchanged):

- `tanker_mode: "lp"` — every week a small LP sets `release_mode=1` and `override_qty` for each (strait, lng/crude)
  pair with queued cargo. Each lot goes out on its own lane first (what the default rule does). Cargo that its own
  next edge cannot take that week can be redirected to another override slot (another lane, so another destination),
  but only to a pool (grid, fuel) that is short (stock + 2 weeks of arrivals < floor). Weight × (1 + `fab_bonus`) for
  grids that feed fabs. Hard limits: queue content (this week's arrivals included), out-edge u, kappa_tb. Soft:
  later edges/straits on the lane, minus what already waits there.
- `queue_eta: true` — energy LP counts queued cargo only after its next edge can drain the queue (was: all of it
  arrives after the lane's tau).

## What the diagnostics showed (mpc_chip, Small dev 0-3, Full dev 0-3)
- The queues are almost never caused by kappa. They are caused by a **narrow next edge** after the strait (e.g.
  Malacca→term_tw u≈30/week with ~3.6k LNG parked all 52 weeks; Suez→term_eu u≈42 with ~1.7k LNG). This is a
  one-off parked stock (~1-2 weeks of one grid's burn), not a lost flow: the energy LP already caps new shipments by the
  min u of the route.
- Full dev ep 0: Taiwan strait partly closed all 104 weeks (kappa 673), ~19k crude + ~14k LNG queued there. The
  override slots at chk_taiwan only lead to term_kr / term_jp, so there is nothing to redirect there.

## Results (runner tables as printed)

Round 1 (buggy first version: held every arrival for a week + scattered cargo across destinations), root 521238367:
```
small, entropy 521238367, 20 episodes; diff = variant - mpc_chip, 90% paired interval
variant                      RSS     L1     L2     L3     L4     diff  interval               better%  fallb
mpc_chip                  0.6187  0.601  0.674  0.669      -  +0.0000  [+0.0000, +0.0000]     nan%      0
tk_lp                     0.5702  0.566  0.608  0.492      -  -0.0485  [-0.0858, -0.0196]     0.0%      0  <-- worse
tk_lp_eta                 0.5721  0.567  0.612  0.492      -  -0.0466  [-0.0838, -0.0171]     0.1%      0  <-- worse
eta                       0.6197  0.602  0.675  0.669      -  +0.0010  [-0.0000, +0.0023]    94.3%      0
tk_lp_eta_fab             0.5724  0.567  0.614  0.492      -  -0.0464  [-0.0837, -0.0168]     0.1%      0  <-- worse
```

Round 2 (fixed: arrivals counted, own lane first, redirect only to short pools), same root:
```
small, entropy 521238367, 20 episodes; diff = variant - mpc_chip, 90% paired interval
variant                      RSS     L1     L2     L3     L4     diff  interval               better%  fallb
mpc_chip                  0.6187  0.601  0.674  0.669      -  +0.0000  [+0.0000, +0.0000]     nan%      0
tk_lp                     0.6220  0.604  0.674  0.687      -  +0.0033  [-0.0031, +0.0092]    79.8%      0
tk_lp_eta                 0.6201  0.603  0.667  0.687      -  +0.0014  [-0.0047, +0.0070]    62.7%      0
tk_lp_fab1                0.6289  0.612  0.677  0.696      -  +0.0102  [+0.0036, +0.0168]    99.8%      0  <-- better
eta                       0.6197  0.602  0.675  0.669      -  +0.0010  [-0.0000, +0.0023]    94.3%      0
```

Stage 2, Full `0 devpick:2,2,1,1`:
```
full, entropy 0, 6 episodes; diff = variant - mpc_chip, 90% paired interval
variant                      RSS     L1     L2     L3     L4     diff  interval               better%  fallb
mpc_chip                  0.5802  0.517  0.692  0.568  0.522  +0.0000  [+0.0000, +0.0000]     nan%      0
tk_lp                     0.5763  0.506  0.678  0.596  0.525  -0.0039  [-0.0076, -0.0005]     0.0%      0  <-- worse
tk_lp_fab1                0.5791  0.510  0.680  0.596  0.526  -0.0010  [-0.0065, +0.0039]    31.8%      0
tk_lp_fab3                0.5597  0.482  0.676  0.577  0.491  -0.0205  [-0.0356, -0.0044]     0.0%      0  <-- worse
tk_lp_fab1_eta            0.5788  0.510  0.680  0.597  0.524  -0.0014  [-0.0070, +0.0037]    31.8%      0
```

## Verdict
Not worth pursuing. Best variant `tk_lp_fab1`: +0.010 on Small (20 eps, CI excludes 0), −0.001 on Full (6 dev eps,
CI holds 0). Far below the +0.05 bar. Full L3 improves (+0.03) but L1 (calm, 50% of the score) loses ~0.007-0.035.
Do not switch it on.

## Surprises
- The override takes cargo FIFO whatever lane it came on, so a pair's queue is one fungible pool, but redirecting it
  away from the lanes the energy LP chose hurts: the LP's plan is the better destination choice. Only "excess" cargo
  can be steered usefully, and there is little of it.
- Override mode turns the default release off, and the observation's queue excludes this week's arrivals: a naive
  override holds every arrival one week at every strait (−0.05 RSS on Small).
- `queue_eta` alone: +0.001 on Small, no effect worth having.
- `sbf check` was not run (nothing here is meant for the final).
