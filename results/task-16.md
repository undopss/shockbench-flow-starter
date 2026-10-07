Status: done — pp20 (planned pulses on all fab grids, on top of the buffer) is +0.046 on Full dev 20

## Verdict
`agents/mpc_bufplan` + `{"pulse_plan": true, "pp_value": 20}` beats `agents/mpc_buffer` at every stage:
Small random 20 +0.025, Full devpick 6 +0.032, **Full dev 20 0.7820 vs 0.7363 (+0.046, 90% [+0.034, +0.056], better on 100% of bootstrap)**.
pp50 is the same within noise (+0.044). Restricting the planner to CN/JP/SEA gives only +0.013 on Full 6, so most of the gain is at TW/KR
(where the planner replaces the fixed 1.5-week pulse). Recommendation: new final candidate = mpc_bufplan with pp20 (needs a `params.json`
or flipping the defaults in a final copy; left off by default here as the task asked).

Note on task 3 vs now: mpc_pplan was −0.012 vs mpc_pulse, but on top of the 3-week wafer buffer the planned pulses pay off —
consistent with task 12's finding that pulses were landing on fabs with no wafers.

## CPU (`uv run sbf check`, this cloud machine, pp20 copy in outputs/task-16/pp20_agent)
- Small (1 dev episode, budget 2 s): week 1 0.093 s, median 0.062 s, max 0.093 s. All checks passed.
- Full (2 dev episodes, budget 4 s): week 1 0.237 / 0.265 s, median 0.189 / 0.207 s, max 0.271 / 0.294 s. All checks passed.
- The planner also has its own deadline (`pp_deadline` 1.5 s CPU in the week) after which it stops planning grids.

## Choices made (nobody to ask)
- Small stage ran only the all-grid variants (CN/SEA don't exist on Small); CN/JP/SEA variants went straight to Full 6, as the task said.
- Full 6 ran all four variants in one file (variants16.json) so they share the baseline.
- Full dev 20 ran pp20 and pp50 only (all-grid clearly beat CN/JP/SEA-only on Full 6).
- Merged `origin/cloud` into the branch first (only docs changed there).
- Surprise: the cache tarball didn't cover Full devpick on this machine (references are stored under a different config hash,
  `7740c8824dd9c8ed` here vs `93b801effce44fbf` in the tarball), so Full 6 built references for ~28 min. Small seed 148337082 took ~19 min.
- Why CN/JP/SEA-only is weak: not investigated further (the all-grid version is the clear winner); the plain pulse at CN/EU was costly in
  task 14, the planner at least doesn't lose there (+0.013 on Full 6).
## Small random 20 (entropy 148337082)
```
small, entropy 148337082, 20 episodes; diff = variant - mpc_buffer, 90% paired interval
variant                      RSS     L1     L2     L3     L4     diff  interval               better%  fallb
mpc_buffer                0.7441  0.667  0.775  0.849  0.799  +0.0000  [+0.0000, +0.0000]     nan%      0
pp20                      0.7694  0.724  0.781  0.835  0.832  +0.0253  [+0.0110, +0.0401]   100.0%      0  <-- better
pp50                      0.7697  0.724  0.782  0.835  0.832  +0.0256  [+0.0111, +0.0404]   100.0%      0  <-- better

results: outputs/variants/v16_small_small_148337082_1007-2102/results.json
```
Both all-grid planners pass Small (+0.025, interval above 0).
