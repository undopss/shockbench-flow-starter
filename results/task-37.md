Status: running Full dev 20 (nd_open vs mpc_cq)

Found so far: ~85% of chip disposal on mpc_cq is transport-bound (every route out of the slot full); the chip LP itself
plans almost all of it. One real LP-vs-simulator mismatch: the LP scales every lane's capacity by the chokepoint's open
fraction, but the simulator applies it only to the strait's throughput kappa (already shared by cq_kappa). Option
`nd_open` fixes it: Full devpick +0.0073 [+0.0002, +0.0153]. Energy-LP version (`nd_open_e`) -0.016; `sell_buffer` -0.004.
