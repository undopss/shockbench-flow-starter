import sys, time, pickle, importlib.util, numpy as np, gymnasium as gym, shockbench_flow_gym
from scipy.optimize import milp, LinearConstraint, Bounds
from shockbench_flow_agent import agent_config
s=importlib.util.spec_from_file_location("ag", "agents/mpc_pulse/agent.py"); m=importlib.util.module_from_spec(s); s.loader.exec_module(m)
env=gym.make("ShockBench/Full-v0"); obs,info=env.reset(options={"episode":0})
cfg=agent_config(info["static"],info["policy_seed"],env.unwrapped.layout,obs); ag=m.Agent(cfg)
for w in range(4): a=ag.act(obs); obs,*_=env.step(a)
ag.act(obs); pp=ag.pplan
gr=[g for g in pp.grids if g["gpos"]==0][0]
arr=pp.arrivals(obs, ag.planned_arrivals); pp._plan_grid(obs, gr, arr)
c,A,rl,rh,ig,lo,hi=pp.last_model
print("n",len(c),"rows",A.shape[0],"ints",ig.sum())
for opts in [{}, {"presolve":False}, {"mip_rel_gap":1e-2}, {"presolve":False,"mip_rel_gap":1e-2}]:
    t0=time.process_time(); r=milp(c,constraints=LinearConstraint(A,rl,rh),integrality=ig,bounds=Bounds(lo,hi),options=dict({"time_limit":5},**opts))
    print(opts, f"{time.process_time()-t0:.3f}", r.status, r.fun, r.mip_node_count)
pickle.dump(pp.last_model, open("outputs/task3/tw_model.pkl","wb"))
