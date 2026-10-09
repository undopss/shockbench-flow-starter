"""Task 29: shed (T USD) by grid and fab starts (M lots) by fab for agent variants on Full episodes.

    uv run python outputs/task-29/shedlots.py <episodes 0,2> <name> <agent dir> '<params json>' <out.json>
"""
import importlib.util
import json
import sys
from pathlib import Path

import gymnasium as gym
import numpy as np
import shockbench_flow_gym  # noqa: F401
from shockbench_flow_agent import agent_config

eps = [int(x) for x in sys.argv[1].split(",")]
name, agent_dir, params, out = sys.argv[2], sys.argv[3], json.loads(sys.argv[4]), sys.argv[5]
spec = importlib.util.spec_from_file_location("ag_" + name, Path(agent_dir) / "agent.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
mod.PARAMS.update(params)
env = gym.make("ShockBench/Full-v0")
res = {"shed": {}, "lots": {}, "J": []}
for ep in eps:
    obs, info = env.reset(options={"episode": ep})
    inst = info["static"]["instance"]
    nodes = inst["nodes"]
    cfg = agent_config(info["static"], info["policy_seed"], env.unwrapped.layout, obs)
    lay = cfg["layout"]
    grids = [nodes[g]["id"] for g in lay["grids"]]
    voll = [float(nodes[g]["grid"].get("voll", 4e6)) for g in lay["grids"]]
    fabs = [nodes[f]["id"] for f in lay["fabs"]]
    ag = mod.Agent(cfg)
    st = env.unwrapped.core._ep.state
    J, done = 0.0, False
    while not done:
        t = int(obs["week"][0])
        obs, r, term, trunc, info = env.step(ag.act(obs))
        done = term or trunc
        J -= r
        st = env.unwrapped.core._ep.state
        for gi, g in enumerate(grids):
            res["shed"][g] = res["shed"].get(g, 0.0) + float(obs["last_week.shed.qty"][gi]) * voll[gi] / len(eps)
        for fi, f in enumerate(fabs):
            res["lots"][f] = res["lots"].get(f, 0.0) + float(st.fab_wip.get(fi, {}).get(t, 0.0)) / len(eps)
    res["J"].append(J)
Path(out).write_text(json.dumps(res))
