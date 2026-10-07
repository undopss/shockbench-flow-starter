Status: testing fix 1 (fab_boost on Full L1 episodes)

Plan: find where mpc_pulse/mpc_chip lose money in calm (L1) Full episodes and fix one reachable piece.

So far:
- Full dev cost breakdown: mpc_chip L1 RSS 0.458 (gap 1.76 T/ep, 99.9% chips); mpc_pulse L1 0.650 (gap 1.14 T/ep: shortage 1.01 T, shed 0.09 T).
- Calm ep 2 vs clairvoyant (mpc_pulse): chip loss 2.75 T vs 2.30 T. Biggest reachable piece: fab_cn_mature_1 (pulse 15.4M lots vs oracle 26.9M) -
  grid_cn crude is ~107/week short every week (term_cn gets 1693/wk, burn 1800), which comes straight out of the fab's 393/wk headroom (homes first);
  LNG is kept exactly at the rationing line, so every dip sheds homes and stops the fab for weeks.
- Energy LP prices any fuel shortfall at VOLL (~4M/unit), but at a fab grid the first `headroom` units cost fab power: ~11M USD/unit (mature), 25-38M (leading/memory).
- OSAT->sink edges (some at 0.25 of u0 permanently) cap leading-edge deliveries at ~300k/wk vs 640k demand; the LP is right about those.
