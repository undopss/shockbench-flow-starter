"""Trace per grid per week: terminal/grid lng+crude stock, shed share, fab energy share. Usage: trace.py Full ep agent_dir"""
import sys, json, importlib.util, numpy as np, gymnasium as gym, shockbench_flow_gym
from shockbench_flow_agent import agent_config
task, ep, adir = sys.argv[1], int(sys.argv[2]), sys.argv[3]
s=importlib.util.spec_from_file_location("ag", f"{adir}/agent.py"); m=importlib.util.module_from_spec(s); s.loader.exec_module(m)
env=gym.make(f"ShockBench/{task}-v0"); obs,info=env.reset(options={"episode":ep})
cfg=agent_config(info["static"],info["policy_seed"],env.unwrapped.layout,obs)
ag=m.Agent(cfg); inst=cfg["static"]["instance"]; nodes=inst["nodes"]; ids=[n["id"] for n in nodes]
com=cfg["static"]["commodities"]["id"]; lay=cfg["layout"]; si={tuple(r):i for i,r in enumerate(lay["stock_slots"])}
fabs=lay["fabs"]; grids=lay["grids"]
term={ids[g].replace("grid","term") for g in grids}
rows=[]; J=0; done=False
while not done:
    a=ag.act(obs); obs,r,te,tr,info=env.step(a); done=te or tr; J-=r
    rec=env.unwrapped.core.trajectory.records[-1]
    for gi,g in enumerate(grids):
        gid=ids[g]; tid=ids.index(gid.replace("grid","term"))
        ehat=sum(nodes[fabs[fi]]["fab"]["e"]*nodes[fabs[fi]]["fab"]["cap0"] for fi in range(len(fabs)) if nodes[fabs[fi]]["fab"]["grid"]==gid)
        en=sum(rec.energy[fi] for fi in range(len(fabs)) if nodes[fabs[fi]]["fab"]["grid"]==gid)
        def st(n,k): i=si.get((n,com.index(k))); return float(obs['stock.qty'][i]) if i is not None else float("nan")
        rows.append(dict(w=rec.week,g=gid,Tl=st(tid,"lng"),Il=st(g,"lng"),Tc=st(tid,"crude"),Ic=st(g,"crude"),
            shed=float(rec.shed[gi]),ybar=float(obs["graph_now.grid.y_bar"][gi]),fabE=en,ehat=ehat,
            seg_l=rec.segment.get((gi,com.index("lng")),0.0)))
print("J",J)
json.dump(rows,open(f"outputs/task3/trace_{task}_{ep}_{adir.strip('/').split('/')[-1]}.json","w"))
import collections
by=collections.defaultdict(list)
for r in rows: by[r["g"]].append(r)
for g,rs in by.items():
    if rs[0]["ehat"]==0: continue
    sh=np.array([r["shed"] for r in rs]); fe=np.array([r["fabE"] for r in rs])
    print(f"{g:9s} shed weeks {np.sum(sh>1e-6):3d} shed tot {sh.sum():9.0f}  fabE/ehat mean {fe.mean()/rs[0]['ehat']:.3f}  full-fab weeks {np.sum(fe>0.99*rs[0]['ehat'])}  mean Tl {np.mean([r['Tl'] for r in rs]):8.0f} Il {np.mean([r['Il'] for r in rs]):8.0f} Tc {np.mean([r['Tc'] for r in rs]):7.0f} Ic {np.mean([r['Ic'] for r in rs]):7.0f}")
