Status: measuring (Full devpick + Small dev running)

Plan: measure where mpc_fab3sell's planners mispredict reality week by week, then build agents/mpc_fb with online
corrections (off by default) and run the funnel vs mpc_fab3sell.

First look (Small dev ep 0): requested vs executed clipping is negligible (≥0.999 on every slot class); the pulse
planner's week-0 prediction of homes served and fab energy equals the simulator's exactly; the chip LP's served per
sink is close. The fuel LP is biased: its "shortfall" variable is unbounded, so it books phantom fuel (1.4-3x the
week's burn at short grids) to stay above the rationing line, and it assumes burn = share x G_bar while the grid only
burns what it serves.
