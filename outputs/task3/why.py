import sys, importlib.util, numpy as np, gymnasium as gym, shockbench_flow_gym
from shockbench_flow_agent import agent_config
s=importlib.util.spec_from_file_location("ag", "agents/mpc_pulse/agent.py"); m=importlib.util.module_from_spec(s); s.loader.exec_module(m)
env=gym.make("ShockBench/Full-v0"); obs,info=env.reset(options={"episode":int(sys.argv[1])})
cfg=agent_config(info["static"],info["policy_seed"],env.unwrapped.layout,obs); ag=m.Agent(cfg)
ids=[n["id"] for n in cfg["static"]["instance"]["nodes"]]; pp=ag.pplan
for w in range(int(sys.argv[2])):
    a=ag.act(obs)
    if w in (5,15):
        arr=pp.arrivals(obs, ag.planned_arrivals)
        for gr in pp.grids:
            st=obs["stock.qty"]
            print(w, ids[gr["node"]], [(ids[f["node"]], round(float(st[f["win"]])), round(float(obs["graph_now.fab.cap_eff"][f["pos"]])), round(float(obs["graph_now.fab.R"][f["pos"]]),2)) for f in gr["fabs"]], "plan", pp._plan_grid(obs, gr, arr))
    obs,*_=env.step(a)
