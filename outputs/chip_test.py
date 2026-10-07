"""Quick check: mpc vs mpc_chip on a few gym episodes (J, cost components, chip LP success, CPU per week)."""
import importlib.util, sys, time, numpy as np, gymnasium as gym, shockbench_flow_gym
from shockbench_flow_agent import agent_config
def load(p, name):
    s=importlib.util.spec_from_file_location(name,p); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
task = sys.argv[1] if len(sys.argv)>1 else "Small"; eps=[int(x) for x in (sys.argv[2] if len(sys.argv)>2 else "0,1").split(",")]
names=["freight","war","tariff","hold","qhold","short","disp","shed"]
env = gym.make(f"ShockBench/{task}-v0")
for name in (sys.argv[3] if len(sys.argv)>3 else "mpc,mpc_chip").split(","):
    mod=load(f"agents/{name}/agent.py","m_"+name)
    tot=np.zeros(8); J=0; tmax=0; tsum=0; weeks=0; ok=0; fails=0
    for ep in eps:
        obs,info=env.reset(options={"episode":ep})
        ag=mod.Agent(agent_config(info["static"],info["policy_seed"],env.unwrapped.layout,obs))
        ch=getattr(ag,"chips",None)
        if ch is not None:
            orig=ch.plan
            def wrapped(o, orig=orig):
                global ok, fails
                try: r=orig(o)
                except Exception as e:
                    fails+=1; import traceback; traceback.print_exc(); raise
                if r is None: fails+=1
                else: ok+=1
                return r
            ch.plan=wrapped
        done=False
        while not done:
            t0=time.process_time(); a=ag.act(obs); dt=time.process_time()-t0; tmax=max(tmax,dt); tsum+=dt; weeks+=1
            obs,r,term,trunc,info=env.step(a); done=term or trunc
            tot+=obs["last_week.cost_components"]; J-=r
    print(f"{name}: J {J/len(eps):.4e} per ep | chip LP ok {ok} fail {fails} | cpu max {tmax:.2f}s mean {tsum/weeks:.3f}s", flush=True)
    print("   "+"  ".join(f"{n} {v/len(eps):.2e}" for n,v in zip(names,tot)), flush=True)
