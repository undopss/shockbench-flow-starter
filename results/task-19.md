Status: building the naive F_Q cache for this machine (Python 3.13.16; the home cache is keyed on 3.13.5, so every Full world rebuilt it single-threaded, ~30 min)

Plan: measure where mpc_bufplan(pp20) makes chips it cannot sell (disposal, end stock, late lots), then build
agents/mpc_sell (copy of mpc_bufplan with pp20 on by default; new options off by default) and funnel vs the baseline.
