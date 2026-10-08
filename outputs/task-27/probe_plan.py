"""Task 27: run mpc_clim's energy LP directly (no try/except) with the climate options on/off for a few weeks."""
import importlib.util, sys, time
import numpy as np
import gymnasium as gym
import shockbench_flow_gym  # noqa: F401
spec = importlib.util.spec_from_file_location("clim_agent", "agents/mpc_clim/agent.py")
mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
task, ep, weeks = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
env = gym.make({"small": "ShockBench/Small-v0", "full": "ShockBench/Full-v0"}[task])
obs, info = env.reset(options={"episode": ep})
from shockbench_flow_agent.convert import agent_config
cfg = None
try:
    cfg = agent_config(info["static"], info["policy_seed"], env.unwrapped.layout, obs)
except Exception as e:
    print("config", e)
on = dict(clim_reopen=True, clim_derate=True, clim_safety=1.0)
a = mod.Agent(cfg)
assert a.ok
print("clim tables:", [c is not None for c in a.clim])
for w in range(weeks):
    base = a.fallback.act(obs); flows = np.array(base["flows"], float)
    mod.PARAMS.update({k: False if isinstance(v, bool) else 0.0 for k, v in on.items()})
    f0 = a._plan(obs, flows.copy(), time.process_time())
    a.closed_week = -1; a.closed_for = np.maximum(a.closed_for - (obs["graph_now.open"] < 0.5), 0)
    mod.PARAMS.update(on)
    t = time.process_time(); f1 = a._plan(obs, flows.copy(), t); dt = time.process_time() - t
    closed = np.flatnonzero(obs["graph_now.open"] < 0.5)
    d = np.abs(f1 - f0).sum() if f0 is not None and f1 is not None else None
    print(f"week {w + 1}: closed chk {closed.tolist()} for {a.closed_for[closed].tolist()}  plan ok {f0 is not None} "
          f"{f1 is not None}  |diff| {d:.1f}  lp {dt:.2f}s")
    obs, *_ = env.step(a.act(obs))
