"""Task 25: where do mpc_fab3sell's planners' one-week predictions miss reality?

    uv run python outputs/task-25/miss25.py <small|full> <entropy> <episodes> <agent> [n_jobs] [tag]

Plays the agent (an instrumented copy of mpc_fab3sell: agents/mpc_fb logs its planners' predictions when SBF_FB_LOG is
set) on each episode and compares, week by week, with the simulator's StepRecords:
  clip   requested vs executed per slot class (and the most clipped slots)
  fuel   the fuel LP's end-of-week pool stock and fuel shortfall vs the real pool stock and grid segment output
  pp     the pulse planner's predicted homes served y and fab energy E per grid vs real served_load and fab energy
  chip   the chip LP's served per sink, lots started per fab, disposal vs real
Writes outputs/task-25/miss_<tag>.json (per-episode aggregates) and prints the tables.
"""

import json
import os
import sys
import tempfile
import time
from multiprocessing import Pool
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from variants import pick_episodes  # noqa: E402


def episode(args):
    n, task, entropy, agent_root, cache = args
    from shockbench_flow.dynamics.env import rollout
    from shockbench_flow_agent.local_eval import NO_ZIP_SHA256
    from shockbench_flow_agent.scoring import _metered_shim, _policy_seed, _world
    from shockbench_flow_agent.shim import load_agent_class, unload_agent

    t0 = time.perf_counter()
    inst, omega, marks, fallback = _world(task, entropy, n, 3, cache)
    pseed = _policy_seed(entropy, n, NO_ZIP_SHA256)
    log = Path(tempfile.mkdtemp()) / "log.jsonl"
    os.environ["SBF_FB_LOG"] = str(log)
    cls = load_agent_class(agent_root, f"submission_fb_{n}")
    mod = sys.modules[cls.__module__]
    mod.LOG = str(log)
    shim = _metered_shim(cls, None)
    from shockbench_flow_agent.scoring import _world as _w  # noqa: F401
    traj = rollout(inst, shim, omega, "standard" if task != "tiny" else "standard", pseed, marks=marks,
                   fallback=fallback)
    ag = shim.agent
    recs = traj.records
    logs = {}
    for line in log.read_text().splitlines():
        d = json.loads(line)
        logs[d["week"]] = d
    unload_agent()
    out = analyse(inst, ag, recs, logs)
    out["episode"] = n
    out["seconds"] = round(time.perf_counter() - t0, 1)
    out["J"] = traj.J_cents / 100.0
    return out


def analyse(inst, ag, recs, logs):
    cfg_nodes = inst.nodes if hasattr(inst, "nodes") else None
    node_ids = ag.node_ids
    static_slots = ag.fallback.__dict__.get("slots")
    edges = ag.edges
    # slot classes
    from_type = {}
    res = {}
    T = len(recs)
    nslots = len(logs[1]["flows"])
    # ---- clip, by class of (tail type -> head type)
    ntype = ag._ntype
    slot_edge = ag._slot_edge
    cls_req, cls_exe = {}, {}
    slot_req = np.zeros(nslots)
    slot_exe = np.zeros(nslots)
    for r in recs:
        for s, q in r.requested.items():
            slot_req[s] += q
        for s, q in r.executed.items():
            slot_exe[s] += q
    for s in range(nslots):
        e = slot_edge[s]
        key = f"{ntype[edges['tail'][e]]}->{ntype[edges['head'][e]]}:{ag._kname[ag._slot_k[s]]}"
        cls_req[key] = cls_req.get(key, 0.0) + slot_req[s]
        cls_exe[key] = cls_exe.get(key, 0.0) + slot_exe[s]
    res["clip_class"] = {k: [cls_req[k], cls_exe[k]] for k in cls_req}
    top = np.argsort(-(slot_req - slot_exe))[:12]
    res["clip_top"] = [[int(s), ag._slot_name[s], float(slot_req[s]), float(slot_exe[s])] for s in top]

    # ---- fuel LP: pool stock and output
    P = len(ag.pools)
    feeds = {}
    for (node, k), p_i in ag.feeds.items():
        idx = inst.slot_index.get((node, k))  # the record's stock is in the simulator's slot order
        if idx is not None:
            feeds.setdefault(p_i, []).append(idx)
    stock_miss = np.zeros((P, T)) * np.nan
    out_miss = np.zeros((P, T)) * np.nan
    for w in range(1, T + 1):
        lg = logs.get(w)
        if lg is None or lg["fuel"] is None:
            continue
        r = recs[w - 1]
        gord = {node: i for i, node in enumerate(ag._grids)}
        for p_i, p in enumerate(ag.pools):
            real = sum(float(r.stock[i]) for i in feeds.get(p_i, []))
            stock_miss[p_i, w - 1] = real - lg["fuel"]["I"][p_i]
            gi = gord.get(p["grid"])
            seg = r.segment.get((gi, p["k"]), 0.0)
            pred_out = lg["fuel"]["burn"][p_i] - lg["fuel"]["sf"][p_i]
            out_miss[p_i, w - 1] = seg - pred_out
    seg = np.zeros((P, T)) * np.nan
    sfp = np.zeros((P, T)) * np.nan
    brn = np.zeros((P, T)) * np.nan
    gord = {node: i for i, node in enumerate(ag._grids)}
    for w in range(1, T + 1):
        lg = logs.get(w)
        if lg is None or lg["fuel"] is None:
            continue
        r = recs[w - 1]
        for p_i, p in enumerate(ag.pools):
            seg[p_i, w - 1] = r.segment.get((gord.get(p["grid"]), p["k"]), 0.0)
            sfp[p_i, w - 1] = lg["fuel"]["sf"][p_i]
            brn[p_i, w - 1] = lg["fuel"]["burn"][p_i]
    # 4 weeks ahead: the LP's stock at the end of week w+4 vs the real one; shortfall over weeks w..w+4 vs real
    # burn short of the LP's burn over those weeks
    st4 = np.zeros((P, T)) * np.nan
    sh4 = np.zeros((P, T)) * np.nan
    for w in range(1, T - 3):
        lg = logs.get(w)
        if lg is None or lg["fuel"] is None or "I4" not in lg["fuel"]:
            continue
        for p_i, p in enumerate(ag.pools):
            real = sum(float(recs[w + 3].stock[i]) for i in feeds.get(p_i, []))
            st4[p_i, w - 1] = real - lg["fuel"]["I4"][p_i]
            gi = gord.get(p["grid"])
            short = sum(lg["fuel"]["burn"][p_i] - recs[w - 1 + t].segment.get((gi, p["k"]), 0.0) for t in range(5))
            sh4[p_i, w - 1] = short - lg["fuel"]["sf4"][p_i]
    res["fuel"] = []
    for p_i, p in enumerate(ag.pools):
        b = np.nanmean([lg["fuel"]["burn"][p_i] for lg in logs.values() if lg["fuel"]]) if logs else np.nan
        res["fuel"].append({"grid": node_ids[p["grid"]], "k": ag._kname[p["k"]], "burn": float(b),
                            "stock_bias": float(np.nanmean(stock_miss[p_i])),
                            "stock_mae": float(np.nanmean(np.abs(stock_miss[p_i]))),
                            "out_bias": float(np.nanmean(out_miss[p_i])),
                            "out_mae": float(np.nanmean(np.abs(out_miss[p_i]))),
                            "out_neg_weeks": int(np.nansum(out_miss[p_i] < -1e-6 * max(b, 1))),
                            "burn_ratio": float(np.nansum(seg[p_i]) / max(np.nansum(brn[p_i]), 1e-9)),
                            "sf_weeks": int(np.nansum(sfp[p_i] > 1e-6 * max(b, 1))),
                            "sf_over_burn": float(np.nansum(sfp[p_i]) / max(np.nansum(brn[p_i]), 1e-9)),
                            "real_short_weeks": int(np.nansum(seg[p_i] < 0.999 * brn[p_i])),
                            "stock4_bias": float(np.nanmean(st4[p_i])), "stock4_mae": float(np.nanmean(np.abs(st4[p_i]))),
                            "short4_bias": float(np.nanmean(sh4[p_i])),
                            "series_stock": [None if np.isnan(v) else float(v) for v in stock_miss[p_i]],
                            "series_out": [None if np.isnan(v) else float(v) for v in out_miss[p_i]]})

    # ---- pulse planner: homes served and fab energy per grid
    res["pp"] = {}
    fab_grid = ag._fab_grid  # fab ordinal -> grid ordinal
    for w in range(1, T + 1):
        lg = logs.get(w)
        if not lg or not lg["pp"]:
            continue
        r = recs[w - 1]
        for gpos, (g, y, E, ehat, mode) in lg["pp"].items():
            gi = int(gpos)
            Er = float(sum(r.energy[f] for f, gg in fab_grid.items() if gg == gi))
            Gr = float(sum(v for (gg, k), v in r.segment.items() if gg == gi))
            d = res["pp"].setdefault(ag.node_ids[ag._grids[gi]], {"n": 0, "G_pred": 0.0, "G_real": 0.0, "y_pred": 0.0,
                                                                 "y_real": 0.0, "E_pred": 0.0, "E_real": 0.0,
                                                                 "ehat": 0.0, "E_pred_pos_real0": 0,
                                                                 "voll": ag._voll[gi], "modes": [0, 0, 0, 0, 0, 0]})
            d["n"] += 1
            d["G_pred"] += g; d["G_real"] += Gr
            d["y_pred"] += y; d["y_real"] += float(r.served_load[gi])
            d["E_pred"] += E; d["E_real"] += Er; d["ehat"] += ehat
            d["E_pred_pos_real0"] += int(E > 1e-6 and Er < 0.1 * E)
            d["modes"][mode] += 1

    # ---- chip LP: served per sink, starts per fab, disposal
    ch = ag.chips
    res["chip_sink"] = []
    res["chip_fab"] = []
    if ch is not None:
        for j, sk in enumerate(ch.sinks):
            pred = real = 0.0
            for w in range(1, T + 1):
                lg = logs.get(w)
                if not lg or not lg["chip"]:
                    continue
                pred += lg["chip"]["sv"][j]
                real += float(recs[w - 1].served[sk["row"]])
            p4 = r4 = d4p = d4r = 0.0
            for w in range(1, T - 3):
                lg = logs.get(w)
                if not lg or not lg["chip"] or "sv4" not in lg["chip"]:
                    continue
                p4 += lg["chip"]["sv4"][j]
                d4p += lg["chip"]["dem4"][j]
                r4 += sum(float(recs[w - 1 + t].served[sk["row"]]) for t in range(5))
                d4r += sum(float(recs[w - 1 + t].demand[sk["row"]]) for t in range(5))
            p = ch.pos[sk["pos"]]
            res["chip_sink"].append({"sink": node_ids[p["node"]], "k": ag._kname[p["k"]], "pi": sk["pi"],
                                     "pred": pred, "real": real, "pred5": p4, "real5": r4, "dem5_pred": d4p,
                                     "dem5_real": d4r})
        for fi, f in enumerate(ch.fabs):
            pred = real = 0.0
            for w in range(1, T + 1):
                lg = logs.get(w)
                if not lg or not lg["chip"]:
                    continue
                pred += lg["chip"]["st"][fi]
                real += float(recs[w - 1].lots_started[f["pos"]])
            res["chip_fab"].append({"fab": node_ids[f["node"]], "pred": pred, "real": real})
        dp = dr = 0.0
        for w in range(1, T + 1):
            lg = logs.get(w)
            if not lg or not lg["chip"]:
                continue
            for i, p in enumerate(ch.pos):
                dp += lg["chip"]["d"][i]
                dr += float(recs[w - 1].disposal[inst.slot_index[(p["node"], p["k"])]])
        res["chip_disp"] = [dp, dr]
    res["cpu"] = [lg["cpu"] for lg in logs.values()]
    res["shed_usd"] = float(sum(float(np.dot(r.shed, [ag._voll[i] for i in range(len(r.shed))])) for r in recs))
    return res


def main(task, entropy, episodes, agent, n_jobs=4, tag=None):
    entropy = int(entropy)
    eps = pick_episodes(task, entropy, str(episodes), int(n_jobs))
    if eps == "dev":
        from shockbench_flow_agent.scoring import EpisodeSet
        eps = [int(r["episode"]) for r in EpisodeSet.build(task, "dev", entropy=0, n_jobs=int(n_jobs)).references]
    if isinstance(eps, int):
        eps = list(range(eps))
    from shockbench_flow.evaluation.cache import default_cache_dir
    cache = str(default_cache_dir())
    with Pool(int(n_jobs)) as pool:
        rows = pool.map(episode, [(n, task, entropy, agent, cache) for n in eps], chunksize=1)
    tag = tag or f"{task}_{entropy}_{episodes}"
    Path(f"outputs/task-25/miss_{tag}.json").write_text(json.dumps(rows))
    print(f"wrote outputs/task-25/miss_{tag}.json ({len(rows)} episodes)")


if __name__ == "__main__":
    main(*sys.argv[1:])
