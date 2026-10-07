import sys, time, importlib.util, numpy as np, gymnasium as gym, shockbench_flow_gym
from shockbench_flow_agent import agent_config
task, ep, adir, W, G = sys.argv[1], int(sys.argv[2]), sys.argv[3], int(sys.argv[4]), sys.argv[5]
s=importlib.util.spec_from_file_location("ag", f"{adir}/agent.py"); m=importlib.util.module_from_spec(s); s.loader.exec_module(m)
env=gym.make(f"ShockBench/{task}-v0"); obs,info=env.reset(options={"episode":ep})
cfg=agent_config(info["static"],info["policy_seed"],env.unwrapped.layout,obs); ag=m.Agent(cfg)
pp=ag.pplan; orig=pp._plan_grid; ids=[n["id"] for n in cfg["static"]["instance"]["nodes"]]
def wrap(obs, gr, arr):
    pp.last_res=None; t0=time.process_time(); r=orig(obs, gr, arr); dt=time.process_time()-t0
    if ids[gr["node"]]==G:
        res=pp.last_res
        print(int(obs["week"][0]), f"{dt:.3f}s", None if res is None else (res.status, round(res.mip_gap,5) if res.mip_gap is not None else None, res.mip_node_count), r)
    return r
pp._plan_grid=wrap
for w in range(W):
    a=ag.act(obs); obs,*_=env.step(a)
