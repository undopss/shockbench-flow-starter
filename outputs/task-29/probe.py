"""Task 29 probe: a few weeks of a Full episode with agents/mpc_pval, prints pplan's V vs the dual V per grid."""
import importlib.util, json, os, sys, time, numpy as np, gymnasium as gym, shockbench_flow_gym
from shockbench_flow_agent import agent_config
ep, weeks = int(sys.argv[1]), int(sys.argv[2])
os.environ["PV_LOG"] = sys.argv[3]
s = importlib.util.spec_from_file_location("pv", "agents/mpc_pval/agent.py"); m = importlib.util.module_from_spec(s)
s.loader.exec_module(m)
m.PARAMS["pv_dual"] = "measure"
env = gym.make("ShockBench/Full-v0")
obs, info = env.reset(options={"episode": ep})
ag = m.Agent(agent_config(info["static"], info["policy_seed"], env.unwrapped.layout, obs))

for w in range(weeks):
    t0 = time.process_time(); a = ag.act(obs); dt = time.process_time() - t0
    fv = ag.chips.fab_val
    pass
    obs, r, term, trunc, info = env.step(a)
