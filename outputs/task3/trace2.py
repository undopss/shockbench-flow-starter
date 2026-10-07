import sys, importlib.util, numpy as np, gymnasium as gym, shockbench_flow_gym
from shockbench_flow_agent import agent_config
task, ep, adir, gname = sys.argv[1], int(sys.argv[2]), sys.argv[3], sys.argv[4]
W=[int(x) for x in sys.argv[5].split(",")]
s=importlib.util.spec_from_file_location("ag", f"{adir}/agent.py"); m=importlib.util.module_from_spec(s); s.loader.exec_module(m)
env=gym.make(f"ShockBench/{task}-v0"); obs,info=env.reset(options={"episode":ep})
cfg=agent_config(info["static"],info["policy_seed"],env.unwrapped.layout,obs)
ag=m.Agent(cfg); inst=cfg["static"]["instance"]; nodes=inst["nodes"]; ids=[n["id"] for n in nodes]
com=cfg["static"]["commodities"]["id"]; lay=cfg["layout"]; si={tuple(r):i for i,r in enumerate(lay["stock_slots"])}
gi=[ids[g] for g in lay["grids"]].index(gname); g=lay["grids"][gi]; spec=nodes[g]["grid"]; tid=ids.index(gname.replace("grid","term"))
slots=cfg["static"]["action_slots"]; E=cfg["static"]["edges"]
tg=[s_ for s_,(e,k) in enumerate(zip(slots["edge"],slots["k"])) if E["head"][e]==g]
print("slots into grid:",[(s_,ids[E["tail"][slots["edge"][s_]]],com[slots["k"][s_]]) for s_ in tg])
done=False
while not done:
    a=ag.act(obs); w=int(obs["week"][0]); Gb=obs["graph_now.grid.G_bar"][gi]
    obs,r,te,tr,info=env.step(a); done=te or tr
    rec=env.unwrapped.core.trajectory.records[-1]
    if w not in W: continue
    segs={("none" if k is None else com[k]):round(v/(spec["shares"].get("unmodelled" if k is None else com[k],0)*Gb),3) for (gg,k),v in rec.segment.items() if gg==gi}
    stk={k:round(float(obs['stock.qty'][si[(n,com.index(k))]])) for k in spec["shares"] if k!="unmodelled" for n in [g] }
    tstk={k:round(float(obs['stock.qty'][si[(tid,com.index(k))]])) for k in ("lng","crude") if (tid,com.index(k)) in si}
    print(w,"seg/share*G",segs,"grid stock",stk,"term",tstk,"req",[round(a["flows"][s_]) for s_ in tg],"exe",[round(rec.executed.get(s_,0)) for s_ in tg],"shed",round(float(rec.shed[gi])),"u",[round(float(obs["graph_now.u"][slots["edge"][s_]])) for s_ in tg])
