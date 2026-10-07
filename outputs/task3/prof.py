import sys, time, importlib.util, numpy as np, gymnasium as gym, shockbench_flow_gym, collections
from shockbench_flow_agent import agent_config
task, ep, adir, W = sys.argv[1], int(sys.argv[2]), sys.argv[3], int(sys.argv[4])
s=importlib.util.spec_from_file_location("ag", f"{adir}/agent.py"); m=importlib.util.module_from_spec(s); s.loader.exec_module(m)
env=gym.make(f"ShockBench/{task}-v0"); obs,info=env.reset(options={"episode":ep})
cfg=agent_config(info["static"],info["policy_seed"],env.unwrapped.layout,obs); ag=m.Agent(cfg)
pp=ag.pplan; orig=pp._plan_grid; stats=collections.defaultdict(list)
ids=[n["id"] for n in cfg["static"]["instance"]["nodes"]]
def wrap(obs, gr, arr):
    t0=time.process_time(); r=orig(obs, gr, arr); stats[ids[gr["node"]]].append((time.process_time()-t0, r is None)); return r
pp._plan_grid=wrap
for w in range(W):
    a=ag.act(obs); obs,*_=env.step(a)
for g,v in stats.items():
    t=np.array([x[0] for x in v]); print(g, f"mean {t.mean():.3f} max {t.max():.3f} none {sum(x[1] for x in v)}/{len(v)}")
