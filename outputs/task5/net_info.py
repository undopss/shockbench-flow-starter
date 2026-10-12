import gymnasium as gym, shockbench_flow_gym, numpy as np
from shockbench_flow_agent import agent_config
env = gym.make("ShockBench/Full-v0")
obs, info = env.reset(options={"episode": 0})
st = info["static"]; inst = st["instance"]; nodes = inst["nodes"]; com = st["commodities"]["id"]
lay = agent_config(info["static"], info["policy_seed"], env.unwrapped.layout, obs)["layout"]
ids = [n["id"] for n in nodes]
for f in lay["fabs"]:
    fb = nodes[f]["fab"]; print(ids[f], {k: fb[k] for k in fb if k not in ()})
for o in lay["osats"]:
    print(ids[o], nodes[o]["osat"])
E = st["edges"]
def edges_from(n): return [(e, ids[E["head"][e]], [com[k] for k in (E["K"][e] or [])]) for e in range(len(E["head"])) if E["tail"][e]==n]
us = [i for i,x in enumerate(ids) if "fab_us" in x]
for f in us: print(ids[f], "->", edges_from(f))
sk = st["sinks"]
print("sinks", [(ids[n], com[k], p) for n,k,p in zip(sk["node"], sk["k"], sk["pi"])][:80])
