Status: running 2nd batch of offline tests (true material supply, value-weighted / bigger wafer buffer)

First results (Full devpick:2,2,1,1, mpc_fab3sell copy, chip shortage T USD/episode):
- agent 2.089; oracle with the agent's own starts (routing ceiling) 1.995; oracle with the agent's fab power after homes 1.933; free oracle 1.753.
  => chip-side ceiling (everything the chip LP + wafer buffer control, with perfect foresight) = 0.156 T; power side 0.180 T.
- Chip LP fed perfect info (true demand + true capacities + true fab starts + horizon 52): only -0.023 T shortage, +0.006 RSS.
