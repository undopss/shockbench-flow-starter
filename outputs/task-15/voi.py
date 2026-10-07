"""Task 15, step 2: what is foresight of an event class worth? Remove the class from omega and replay.

    uv run python outputs/task-15/voi.py full 0 devpick:2,2,1,1 agents/mpc_buffer 4 [classes]

For each episode and each class (events whose onset is inside the episode; carried-in events stay, the agent sees
them from week 1), builds omega without those event rows (marks recomputed), plays the agent (as sbf evaluate does,
same policy seed and fallback) and solves the clairvoyant LP. The ceiling of foresight on a class is
    (J_agent(omega) - J_agent(omega minus class)) - (J_oracle(omega) - J_oracle(omega minus class)),
i.e. how much more the agent loses to the class than the clairvoyant plan does (which already has perfect foresight).
Writes outputs/task-15/voi_<task>_<entropy>_<eps>.json.
"""

import json
import sys
import time
from pathlib import Path

import numpy as np
from joblib import Parallel, delayed

TYPES = ("tariff", "sanction", "material_outage", "militarised_closure", "regional_conflict", "piracy",
         "energy_shock", "weather_closure", "port_strike")
CLASSES = {
    "base": (),
    "all": tuple(range(9)),
    "announced": (0, 1, 3),  # tariff, sanction, militarised closure: the message channels
    "conflict": (4,),  # region / dyad warnings
    "closures": (3, 7),  # chokepoint warnings
    "tariff": (0,),
    "sanction": (1,),
    "energy_shock": (6,),
}


def drop_events(inst, omega, types):
    """omega without the events of ``types`` whose onset is inside the episode (0 <= onset < T)."""
    from shockbench_flow import marks
    from shockbench_flow.omega.container import ARRAY_DTYPES

    a = omega.arrays
    ty, on = np.asarray(a["ev_type"]), np.asarray(a["ev_onset"])
    drop = np.isin(ty, list(types)) & (on >= 0) & (on < inst.T)
    if not drop.any():
        return omega, 0
    keep = ~drop
    new = {}
    for name in a:
        if not name.startswith("ev_") or name in ("ev_key", "ev_key_ptr"):
            continue
        new[name] = np.ascontiguousarray(np.asarray(a[name])[keep])
    ptr, key = np.asarray(a["ev_key_ptr"]), np.asarray(a["ev_key"])
    keys = [key[ptr[i]:ptr[i + 1]] for i in np.flatnonzero(keep)]
    new["ev_key_ptr"] = np.concatenate([[0], np.cumsum([len(k) for k in keys])]).astype(ptr.dtype)
    new["ev_key"] = (np.concatenate(keys) if keys else np.zeros(0)).astype(key.dtype)
    if "V_lead" in a and len(np.asarray(a["V_lead"])) == len(ty):
        new["V_lead"] = np.asarray(a["V_lead"])[keep]
    params = marks.mark_params_from_json(str(a["meta_mark_params"]))
    new |= marks.stored_mark_arrays(inst, new, params)
    for k, v in list(new.items()):
        if k in ARRAY_DTYPES:
            new[k] = np.asarray(v, dtype=ARRAY_DTYPES[k])
    return omega.replace(**new), int(drop.sum())


def run(n, cls, spec, agent_root):
    from shockbench_flow.dynamics.env import rollout, took_fallback
    from shockbench_flow.marks import compute_marks
    from shockbench_flow.oracle.lp import ORACLE_METHOD, build_lp, solve_oracle
    from shockbench_flow_agent.local_eval import NO_ZIP_SHA256
    from shockbench_flow_agent.scoring import _metered_shim, _policy_seed, _world
    from shockbench_flow_agent.shim import load_agent_class, unload_agent

    task, entropy, regime, reps, cache = spec
    t0 = time.perf_counter()
    inst, omega, marks, fallback = _world(task, entropy, n, reps, cache)
    pseed = _policy_seed(entropy, n, NO_ZIP_SHA256)
    om, ndrop = drop_events(inst, omega, CLASSES[cls])
    mk = marks if om is omega else compute_marks(inst, om)
    shim = _metered_shim(load_agent_class(agent_root, f"submission_{Path(agent_root).stem}"), None)
    traj = rollout(inst, shim, om, regime, pseed, marks=mk, fallback=fallback)
    unload_agent()
    res = solve_oracle(build_lp(inst, mk), method=ORACLE_METHOD)
    J_naive = None
    if cls == "base":  # naive on the real omega: the RSS scale (computed here, the dev cache is not usable)
        from shockbench_flow.hosting.tasks import task_generator
        from shockbench_flow.policies.naive_fq import anchor_policy
        from shockbench_flow_agent.local_eval import ANCHOR_REGIME

        _, params = task_generator(task)
        J_naive = rollout(inst, anchor_policy(inst, params, reps), omega, ANCHOR_REGIME, pseed, marks=marks,
                          fallback=fallback).J_cents / 100
    return dict(episode=n, cls=cls, dropped=ndrop, J_agent=traj.J_cents / 100, J_oracle=res.J_cents / 100,
                J_naive=J_naive, omega_hash=omega.hash,
                fallback_weeks=sum(took_fallback(r) for r in traj.records), seconds=round(time.perf_counter() - t0))


def main(task, entropy, eps_spec, agent, n_jobs, classes=None):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from shockbench_flow_agent.scoring import EpisodeSet
    from variants import pick_episodes

    entropy, n_jobs = int(entropy), int(n_jobs)
    if eps_spec.startswith("devpick"):
        eps = pick_episodes(task, entropy, eps_spec, n_jobs)
        es = EpisodeSet.build(task, eps, entropy=entropy, n_jobs=n_jobs)
        ns, spec = [int(n) for n in es.episodes], es._spec
        refs = {int(r["episode"]): r for r in es.references}
    else:  # an explicit list: no EpisodeSet (its reference cache / dev split), naive computed in the base runs
        from shockbench_flow.evaluation.cache import default_cache_dir

        ns, spec, refs = [int(x) for x in eps_spec.split(",")], (task, entropy, "standard", 1000,
                                                                  str(default_cache_dir())), {}
    classes = classes.split(",") if classes else list(CLASSES)
    if "base" not in classes:
        classes = ["base"] + classes
    root = str(Path(agent).resolve())
    out = Path(f"outputs/task-15/voi_{task}_{entropy}_{eps_spec.replace(':', '-').replace(',', '_')}.json")
    old = json.loads(out.read_text()) if out.exists() else []
    done = {(r["episode"], r["cls"]) for r in old}
    jobs = [(n, c) for c in classes for n in ns if (n, c) not in done]
    print(f"episodes {ns}, classes {classes}, {len(jobs)} runs", flush=True)
    rows = old + Parallel(n_jobs=n_jobs, verbose=10)(delayed(run)(n, c, spec, root) for n, c in jobs)
    naive = {r["episode"]: r["J_naive"] for r in rows if r.get("J_naive") is not None}
    for r in rows:
        ref = refs.get(r["episode"])
        r["stratum"] = ref["stratum"] if ref else None
        r["J_naive_ref"] = ref["J_naive_cents"] / 100 if ref else naive.get(r["episode"])
        oracle = [x["J_oracle"] for x in rows if x["episode"] == r["episode"] and x["cls"] == "base"]
        r["J_oracle_ref"] = ref["J_oracle_cents"] / 100 if ref else (oracle[0] if oracle else None)
    out.write_text(json.dumps(rows, indent=1))
    report(rows)


def report(rows):
    by = {(r["episode"], r["cls"]): r for r in rows}
    ns = sorted({r["episode"] for r in rows})
    base = {n: by[(n, "base")] for n in ns if (n, "base") in by}
    print("\nbase check: agent RSS per episode", {n: round((b["J_naive_ref"] - b["J_agent"]) /
                                                            (b["J_naive_ref"] - b["J_oracle_ref"]), 3)
                                                  for n, b in base.items()},
          "oracle reproduces cache:", all(abs(b["J_oracle"] - b["J_oracle_ref"]) < 1 for b in base.values()))
    print(f"\n{'class':14s} {'dropped/ep':>10s} {'dAgent T':>9s} {'dOracle T':>9s} {'ceiling T':>9s} {'ceiling RSS':>11s}"
          "   per episode (ceiling T)")
    for c in CLASSES:
        if c == "base":
            continue
        got = [n for n in ns if (n, c) in by and n in base]
        if not got:
            continue
        dA = np.array([base[n]["J_agent"] - by[(n, c)]["J_agent"] for n in got]) / 1e12
        dO = np.array([base[n]["J_oracle"] - by[(n, c)]["J_oracle"] for n in got]) / 1e12
        span = np.array([base[n]["J_naive_ref"] - base[n]["J_oracle_ref"] for n in got]) / 1e12
        ceil = dA - dO
        drop = np.mean([by[(n, c)]["dropped"] for n in got])
        print(f"{c:14s} {drop:10.1f} {dA.mean():9.3f} {dO.mean():9.3f} {ceil.mean():9.3f} {np.mean(ceil / span):11.3f}"
              f"   {' '.join(f'{x:+.3f}' for x in ceil)}")


if __name__ == "__main__":
    if sys.argv[1] == "report":
        report(json.loads(Path(sys.argv[2]).read_text()))
    else:
        main(*sys.argv[1:])
