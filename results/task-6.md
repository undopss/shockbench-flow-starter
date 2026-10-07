Status: analysing level-1 gap (cost breakdown of mpc_chip done, mpc_pulse running)

Plan: cost_breakdown on Full dev, study the level-1 (calm) gap vs the clairvoyant plan, implement one off-by-default fix aimed at calm episodes, test it with the runner.

So far: mpc_chip Full dev RSS 0.5443 (L1 0.458, the weakest level). L1 gap to clairvoyant 1.76 T USD/episode, 99.9% chip shortage.
Note: the shipped cache did not hit here (generator_id dir 7740c882... vs 93b801ef... in the tgz); references were rebuilt (~40 min) and match the home ones (naive exact, oracle within a few cents).
