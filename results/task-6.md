Status: reliable_bonus +0.015 on L1; trying to widen it, then Full 6

Plan: find where mpc_pulse/mpc_chip lose money in calm (L1) Full episodes and fix one reachable piece.

So far:
- Full dev cost breakdown: mpc_chip L1 RSS 0.458 (gap 1.76 T/ep, 99.9% chips); mpc_pulse L1 0.650 (gap 1.14 T/ep: shortage 1.01 T, shed 0.09 T).
- Calm ep 2 vs clairvoyant (mpc_pulse): chip loss 2.75 T vs 2.30 T. Biggest reachable piece: fab_cn_mature_1 (pulse 15.4M lots vs oracle 26.9M) -
  grid_cn crude is ~107/week short every week (term_cn gets 1693/wk, burn 1800), which comes straight out of the fab's 393/wk headroom (homes first);
  LNG is kept exactly at the rationing line, so every dip sheds homes and stops the fab for weeks.
- Energy LP prices any fuel shortfall at VOLL (~4M/unit), but at a fab grid the first `headroom` units cost fab power: ~11M USD/unit (mature), 25-38M (leading/memory).
- OSAT->sink edges (some at 0.25 of u0 permanently) cap leading-edge deliveries at ~300k/wk vs 640k demand; the LP is right about those.

Milestone (Full L1 dev episodes 2,5,7,10,14, baseline mpc_pulse):
- fab_boost 2 / 5: +0.0003 / +0.0015, intervals hold 0 -> dead end (energy LP sees no shortfall at fab grids; CN/SEA fuel is physically capped, the oracle gets the same fuel and wins only by breaking homes-first).
- NEW reliable_bonus (agents/mpc_calm, off by default): 300 -> +0.0146 [+0.0076, +0.0231], 1500 -> +0.0140. chip_growth 1.0: +0.0005 (no).
