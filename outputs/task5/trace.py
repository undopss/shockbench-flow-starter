"""Trace US fabs on Full episode 0: wafer stock, cap, LP planned starts, actual starts, wafers shipped in."""
import importlib.util, sys, json, numpy as np, gymnasium as gym, shockbench_flow_gym
from shockbench_flow_agent import agent_config
agent_dir = sys.argv[1] if len(sys.argv) > 1 else "agents/mpc_chip"
params = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {"fab_cap_mode": "observed"}
weeks = int(sys.argv[3]) if len(sys.argv) > 3 else 104
s = importlib.util.spec_from_file_location("m", f"{agent_dir}/agent.py"); m = importlib.util.module_from_spec(s); s.loader.exec_module(m)
m.PARAMS |= params
env = gym.make("ShockBench/Full-v0")
obs, info = env.reset(options={"episode": 0})
cfg = agent_config(info["static"], info["policy_seed"], env.unwrapped.layout, obs)
ag = m.Agent(cfg)
ch = ag.chips
ids = [n["id"] for n in info["static"]["instance"]["nodes"]]
lay = cfg["layout"]
cap_store = {}
orig = m._chips.linprog
def lp(*a, **k):
    r = orig(*a, **k); cap_store["res"] = r; cap_store["c"] = a[0]; cap_store["bounds"] = k["bounds"]; return r
m._chips.linprog = lp
us = [fi for fi, f in enumerate(ch.fabs) if ids[f["node"]].startswith("fab_us")]
stock_index = {tuple(r): i for i, r in enumerate(lay["stock_slots"])}
tot_cost = 0; done = False; wk = 0
starts_hist = {fi: [] for fi in us}
while not done and wk < weeks:
    a = ag.act(obs)
    week = int(obs["week"][0])
    H = max(1, min(ch.H, ch.T - week + 1))
    res = cap_store.get("res"); x = res.x if res is not None and res.status == 0 else None
    S, P = len(ch.lp_slots), len(ch.pos); nF = len(ch.fabs)
    off_f = S * H + 2 * P * H
    line = [f"w{week:3d}"]
    for fi in us:
        f = ch.fabs[fi]; node = f["node"]
        I_w = obs["stock.qty"][stock_index[(node, ch.pos[f["in"]]["k"])]]
        cap = obs["graph_now.fab.cap_eff"][f["pos"]]
        plan = x[off_f + fi * H: off_f + fi * H + 4] if x is not None else []
        hi = cap_store["bounds"][off_f + fi * H, 1]
        inflow = sum(a["flows"][ls["slot"]] for ls in ch.lp_slots if ls["dst"] == f["in"])
        outflow = sum(a["flows"][ls["slot"]] for ls in ch.lp_slots if ls["src"] == f["out"])
        line.append(f"{ids[node][4:]}: I {I_w:7.0f} cap {cap:6.0f} hi {hi:6.0f} plan {' '.join(f'{v:6.0f}' for v in plan)} in {inflow:6.0f} out {outflow:6.0f}")
    print(" | ".join(line), flush=True)
    obs, r, term, trunc, info = env.step(a); done = term or trunc; tot_cost -= r; wk += 1
print("cost", tot_cost)
