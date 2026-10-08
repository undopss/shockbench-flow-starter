"""Task 27: is closure_end ever shown in the gym env (the competition regime)? Count observed entries."""
import sys
import numpy as np
import gymnasium as gym
import shockbench_flow_gym  # noqa: F401
task = sys.argv[1]; n = int(sys.argv[2])
env = gym.make({"small": "ShockBench/Small-v0", "full": "ShockBench/Full-v0"}[task])
tot = shown = endshown = closedweeks = 0
for ep in range(n):
    obs, info = env.reset(options={"episode": ep})
    if ep == 0:
        print([k for k in obs if k.startswith("closure_end")], info.get("theta", None) if isinstance(info, dict) else None)
    done = False
    while not done:
        o = np.asarray(obs["closure_end.chokepoint.observed"]); shown += int(o.sum())
        e = np.asarray(obs["closure_end.end_week.observed"]); endshown += int(e.sum())
        closedweeks += int((np.asarray(obs["graph_now.open"]) < 0.5).sum()); tot += 1
        obs, _, te, tr, _ = env.step(env.action_space.sample()); done = te or tr
print(task, n, "weeks", tot, "closure_end entries shown", shown, "end_week shown", endshown, "closed chk-weeks", closedweeks)
