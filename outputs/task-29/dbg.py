import importlib.util, sys, numpy as np, gymnasium as gym, shockbench_flow_gym
from shockbench_flow_agent import agent_config
from scipy.optimize import linprog as _lp
s = importlib.util.spec_from_file_location("pv", "agents/mpc_pval/agent.py"); m = importlib.util.module_from_spec(s); s.loader.exec_module(m)
cap = {}
def lp(*a, **k):
    r = _lp(*a, **k); cap["r"] = r; cap["b"] = k["bounds"]; return r
m._chips.linprog = lp
env = gym.make("ShockBench/Full-v0"); obs, info = env.reset(options={"episode": 0})
ag = m.Agent(agent_config(info["static"], info["policy_seed"], env.unwrapped.layout, obs))
for w in range(int(sys.argv[1])):
    a = ag.act(obs); obs, *_ = env.step(a)
r = cap["r"]; ch = ag.chips; H = ch.H
print(r.status, r.fun)
n = len(r.x); um = r.upper.marginals; lm = r.lower.marginals
print("upper marg nonzero", np.sum(np.abs(um) > 1e-6), "min", um.min(), "max", um.max(), "lower nonzero", np.sum(np.abs(lm) > 1e-6))
import re
src = open("agents/mpc_pval/chips.py").read()
P = len(ch.pos); S = len(ch.lp_slots)
# recompute offsets the same way as chips.py
print("P", P, "S", S, "nfabs", len(ch.fabs), "n", n, "H", H)
b = cap["b"]
for off in range(0, n - H, 1):
    pass
off_f = S * H + 2 * P * H
nF = len(ch.fabs)
for fi, f in enumerate(ch.fabs):
    sl = slice(off_f + fi * H, off_f + fi * H + 4)
    print(fi, "x", np.round(r.x[sl], 1), "hi", np.round(b[sl, 1], 1), "um", np.round(um[sl]), "lm", np.round(lm[sl]))
