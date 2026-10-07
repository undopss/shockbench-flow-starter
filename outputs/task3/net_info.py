import sys, numpy as np, gymnasium as gym, shockbench_flow_gym
from shockbench_flow_agent import agent_config
task=sys.argv[1]
env=gym.make(f"ShockBench/{task}-v0")
obs,info=env.reset(options={"episode":0})
cfg=agent_config(info["static"],info["policy_seed"],env.unwrapped.layout,obs)
st=cfg["static"]; inst=st["instance"]; nodes=inst["nodes"]; ids=[n["id"] for n in nodes]
E=st["edges"]; com=st["commodities"]["id"]
print("params", inst["params"])
lay=cfg["layout"]
print("grids", lay["grids"])
for gi,g in enumerate(lay["grids"]):
    n=nodes[g]; print(ids[g], {k:v for k,v in n["grid"].items()}, "stock", n.get("stock"))
    print("   G_bar", obs["graph_now.grid.G_bar"][gi], "y_bar", obs["graph_now.grid.y_bar"][gi])
for f in lay["fabs"]:
    print(ids[f], nodes[f]["fab"])
for e in range(len(E["head"])):
    t,h=E["tail"][e],E["head"][e]
    if nodes[t].get("type")=="terminal" and nodes[h].get("type")=="grid":
        print("edge",e,ids[t],"->",ids[h],"K",[com[k] for k in E["K"][e]],"tau",E["tau0"][e] if "tau0" in E else None,"u0",E["u0"][e], "terminal stock", nodes[t].get("stock"))
print(list(E.keys()))
