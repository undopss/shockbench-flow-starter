import sys, time, importlib.util, numpy as np, gymnasium as gym, shockbench_flow_gym
from shockbench_flow_agent import agent_config
task, eps, adir = sys.argv[1], [int(x) for x in sys.argv[2].split(",")], sys.argv[3]
s=importlib.util.spec_from_file_location("ag", f"{adir}/agent.py"); m=importlib.util.module_from_spec(s); s.loader.exec_module(m)
env=gym.make(f"ShockBench/{task}-v0")
names=["freight","war","tariff","hold","qhold","short","disp","shed"]
for ep in eps:
    obs,info=env.reset(options={"episode":ep}); cfg=agent_config(info["static"],info["policy_seed"],env.unwrapped.layout,obs)
    t0=time.process_time(); ag=m.Agent(cfg); init=time.process_time()-t0
    ts=[]; J=0; tot=np.zeros(8); done=False
    while not done:
        t0=time.process_time(); a=ag.act(obs); ts.append(time.process_time()-t0)
        obs,r,te,tr,info=env.step(a); done=te or tr; J-=r; tot+=obs["last_week.cost_components"]
    print(f"ep {ep}: J {J:.4e} init {init:.2f}s cpu/week max {max(ts):.2f} median {np.median(ts):.3f} | "+" ".join(f"{n} {v:.2e}" for n,v in zip(names,tot)), flush=True)
