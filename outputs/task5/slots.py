import importlib.util, sys, numpy as np, gymnasium as gym, shockbench_flow_gym
from shockbench_flow_agent import agent_config
s = importlib.util.spec_from_file_location("m", "agents/mpc_chip/agent.py"); m = importlib.util.module_from_spec(s); s.loader.exec_module(m)
env = gym.make("ShockBench/Full-v0"); obs, info = env.reset(options={"episode": 0})
cfg = agent_config(info["static"], info["policy_seed"], env.unwrapped.layout, obs)
ch = m._chips.ChipPlanner(cfg)
ids = [n["id"] for n in info["static"]["instance"]["nodes"]]
sl = cfg["static"]["action_slots"]
tau, u, c, mask = obs["graph_now.tau"], obs["graph_now.u"], obs["graph_now.c"], obs["action_mask"]
def desc(p): return f"{ids[ch.pos[p]['node']]}/{cfg['static']['commodities']['id'][ch.pos[p]['k']]}"
for name in sys.argv[1:]:
    for ls in ch.lp_slots:
        if name in desc(ls["src"]) or name in desc(ls["dst"]):
            r = ls["route"]
            print(ls["slot"], desc(ls["src"]), "->", desc(ls["dst"]), "mask", mask[ls["slot"]], "u", [round(float(u[e])) for e in r], "tau", [int(tau[e]) for e in r], "c", round(sum(float(c[e]) for e in r),1), "chk", ls["chk"])
sk = cfg["static"]["sinks"]
print("supply", {desc(i): float(obs["graph_now.supply.avail"][ch.supply_index[(ch.pos[i]['node'], ch.pos[i]['k'])]]) for i in ch.materials if (ch.pos[i]['node'], ch.pos[i]['k']) in ch.supply_index})
print("stock mats", {desc(i): float(obs["stock.qty"][ch.stock_index[(ch.pos[i]['node'], ch.pos[i]['k'])]]) for i in ch.materials})
print("cap", {desc(i): ch.pos[i]["cap"] for i in ch.materials})
print("demand le", [(ids[ch.pos[s['pos']]['node']], round(s['dbar'])) for s in ch.sinks])
E = cfg["static"]["edges"]; print("edge keys", list(E.keys()))
for name in sys.argv[1:]:
    for ls in ch.lp_slots:
        if name in desc(ls["src"]):
            e = ls["route"][0]
            print(name, ls["slot"], {k: (E[k][e] if not isinstance(E[k], dict) else None) for k in E if k not in ("K",)})
