"""Per week for chosen fabs on Full ep 0 (gym): cap_eff, wafer stock, lots actually started, grid shed last week."""
import importlib.util, sys, json, numpy as np, gymnasium as gym, shockbench_flow_gym
from shockbench_flow_agent import agent_config
names = sys.argv[1].split(","); params = json.loads(sys.argv[2])
s = importlib.util.spec_from_file_location("m", "agents/mpc_chip/agent.py"); m = importlib.util.module_from_spec(s); s.loader.exec_module(m)
m.PARAMS |= params
env = gym.make("ShockBench/Full-v0"); obs, info = env.reset(options={"episode": 0})
cfg = agent_config(info["static"], info["policy_seed"], env.unwrapped.layout, obs); ag = m.Agent(cfg)
nodes = info["static"]["instance"]["nodes"]; ids = [n["id"] for n in nodes]; lay = cfg["layout"]
fabs = {n: list(lay["fabs"]).index(ids.index(n)) for n in names}
grids = {n: list(lay["grids"]).index(ids.index(nodes[ids.index(n)]["fab"]["grid"])) for n in names}
si = {tuple(r): i for i, r in enumerate(lay["stock_slots"])}; com = cfg["static"]["commodities"]["id"]
tot = {n: [0, 0] for n in names}; done = False
while not done:
    a = ag.act(obs); w = int(obs["week"][0])
    obs, r, te, tr, info = env.step(a); done = te or tr
    for n in names:
        node = ids.index(n); tau = nodes[node]["fab"]["tau"]
        started = sum(q for nd, q, out, seen in zip(obs["wip.node"], obs["wip.qty"], obs["wip.out_week"], obs["wip.qty.observed"]) if seen and nd == node and out - tau == w)
        cap = obs["graph_now.fab.cap_eff"][fabs[n]]; shed = obs["last_week.shed.qty"][grids[n]]
        I = obs["stock.qty"][si[(node, com.index("wafer"))]]
        tot[n][0] += started; tot[n][1] += cap
        if w % 8 == 0: print(f"w{w:3d} {n:18s} cap {cap:8.0f} started {started:8.0f} wafers left {I:9.0f} shed {shed:8.3f}")
for n in names: print(n, "started/cap over episode", f"{tot[n][0]:.3e} / {tot[n][1]:.3e} = {tot[n][0]/tot[n][1]:.0%}")
