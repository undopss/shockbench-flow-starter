"""Task 42, step 1: what are the announcement messages worth on Full dev 20 for mpc_best?

    uv run python outputs/task-42/msg42.py full 0 dev agents/mpc_best 4 [classes]
    uv run python outputs/task-42/msg42.py report outputs/task-42/msg42_full_0_dev.json

Two parts, one run per (episode, class):
- class "base": plays the agent exactly as the scorer does (same policy seed and naive fallback) and logs every message
  thread it sees (channel, kinds, region, target, k, first seen week, stated week, withdrawn). Each thread is matched to
  omega's ground truth: a real event of the channel's type, region and target whose announcement week on that channel
  equals the thread's first week (else a decoy). Lead = onset week - first seen week.
- every other class: the events of those types whose onset is inside the episode are dropped from omega (task 15's
  voi.py: their messages go with them, decoys stay), the agent is replayed and the clairvoyant LP solved. The ceiling
  of perfect foresight on the class = (J_agent - J_agent(-class)) - (J_oracle - J_oracle(-class)): how much more the
  agent loses to it than the clairvoyant plan. In RSS points with the official level weights:
  rss(J_agent - ceiling) - rss(J_agent) on the same EpisodeSet (linear in J).
Writes outputs/task-42/msg42_<task>_<entropy>_<eps>.json.
"""

import json
import math
import sys
import time
from pathlib import Path

import numpy as np
from joblib import Parallel, delayed

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "task-15"))
from voi import drop_events  # noqa: E402

TYPES = ("tariff", "sanction", "material_outage", "militarised_closure", "regional_conflict", "piracy",
         "energy_shock", "weather_closure", "port_strike")
CHANNELS = ("tariff_formal", "tariff_informal", "tariff_final", "sanction_legal", "ties_threat", "mid_threat")
CH_TYPE = {0: 0, 1: 0, 2: 0, 3: 1, 4: 1, 5: 3}
CLASSES = {
    "base": (),
    "tariff": (0,),
    "sanction": (1,),
    "mil_closure": (3,),
    "announced": (0, 1, 3),
    "unannounced": (2, 4, 5, 6, 7, 8),
}
LOG = []


def recording(cls):
    class Rec(cls):
        def act(self, obs):
            if "messages.msg_id" in obs:
                seen = np.asarray(obs["messages.msg_id.observed"], dtype=bool)
                rows = []
                for i in np.flatnonzero(seen):
                    g = lambda f: int(obs["messages." + f][i])  # noqa: E731
                    st = int(obs["messages.stated_effective_week"][i]) if obs[
                        "messages.stated_effective_week.observed"][i] else -1
                    kk = int(obs["messages.k"][i]) if obs["messages.k.observed"][i] else -1
                    rows.append((g("msg_id"), g("channel"), g("kind"), g("region"), g("target_kind"), g("target"), kk,
                                 g("announced_week"), st))
                LOG.append((int(obs["t"]) if "t" in obs else len(LOG) + 1, rows))
            return super().act(obs)
    return Rec


def threads_of(log):
    th = {}
    for t, rows in log:
        for mid, ch, kind, reg, tk, tgt, k, ann, st in rows:
            x = th.setdefault(mid, dict(id=mid, channels=set(), kinds=set(), region=reg, tk=tk, target=tgt, k=k,
                                        first=t, announced=ann, stated=-1, withdrawn_week=None))
            x["channels"].add(ch)
            x["kinds"].add(kind)
            x["announced"] = min(x["announced"], ann)
            if st >= 0:
                x["stated"] = max(x["stated"], st)
            if kind == 4 and x["withdrawn_week"] is None:
                x["withdrawn_week"] = t
    return th


def ground_truth(inst, om, th):
    T = inst.T
    ev = {k: np.asarray(om["ev_" + k]) for k in ("type", "region", "counterpart", "target_kind", "target", "onset",
                                                   "duration", "commodity")}
    n = len(ev["type"])
    lead = np.asarray(om["ev_lead"]).reshape(n, -1) if n else np.zeros((0, 6))
    events = []
    for i in range(n):
        s = float(ev["onset"][i])
        if not 0 <= s < T:
            continue
        shown = {c: math.ceil(s - lead[i, c]) + 1 for c in range(6) if not np.isnan(lead[i, c])}
        events.append(dict(type=TYPES[int(ev["type"][i])], tcode=int(ev["type"][i]), region=int(ev["region"][i]),
                           tk=int(ev["target_kind"][i]), target=int(ev["target"][i]), week=int(math.floor(s)) + 1,
                           dur=float(ev["duration"][i]), k=int(ev["commodity"][i]), shown=shown, thread=None))
    for x in th.values():
        x["channels"], x["kinds"] = sorted(x["channels"]), sorted(x["kinds"])
        x["real"], x["onset_week"], x["lead"] = False, None, None
        for e in events:
            if e["tcode"] != CH_TYPE[x["channels"][0]] or (e["region"], e["tk"], e["target"]) != (
                    x["region"], x["tk"], x["target"]):
                continue
            first = min(max(1, e["shown"][c]) for c in x["channels"] if c in e["shown"]) if any(
                c in e["shown"] for c in x["channels"]) else None
            if first is not None and first == x["first"] and e["thread"] is None:
                x["real"], x["onset_week"], x["lead"], x["dur"] = True, e["week"], e["week"] - x["first"], e["dur"]
                e["thread"] = x["id"]
                break
    return list(th.values()), events


def run(n, cls, spec, agent_root, refs):
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
    cls_ = load_agent_class(agent_root, f"submission_{Path(agent_root).stem}")
    LOG.clear()
    shim = _metered_shim(recording(cls_) if cls == "base" else cls_, None)
    traj = rollout(inst, shim, om, regime, pseed, marks=mk, fallback=fallback)
    unload_agent()
    out = dict(episode=n, cls=cls, dropped=ndrop, J_agent=traj.J_cents / 100,
               fallback_weeks=sum(took_fallback(r) for r in traj.records))
    if cls == "base":
        out["J_oracle"] = refs[n]["J_oracle_cents"] / 100
        th, events = ground_truth(inst, omega, threads_of(LOG))
        out["threads"], out["events"] = th, events
    else:
        res = solve_oracle(build_lp(inst, mk), method=ORACLE_METHOD)
        out["J_oracle"] = None if res.J_cents is None else res.J_cents / 100
    out["seconds"] = round(time.perf_counter() - t0)
    return out


def episode_set(task, entropy, eps_spec, n_jobs):
    from shockbench_flow_agent.scoring import EpisodeSet
    from variants import pick_episodes

    eps = pick_episodes(task, entropy, eps_spec, n_jobs)
    return EpisodeSet.build(task, eps, entropy=entropy, n_jobs=n_jobs)


def main(task, entropy, eps_spec, agent, n_jobs, classes=None):
    entropy, n_jobs = int(entropy), int(n_jobs)
    es = episode_set(task, entropy, eps_spec, n_jobs)
    refs = {int(r["episode"]): r for r in es.references}
    ns = sorted(refs)
    classes = classes.split(",") if classes else list(CLASSES)
    if "base" not in classes:
        classes = ["base"] + classes
    root = str(Path(agent).resolve())
    out = Path(f"outputs/task-42/msg42_{task}_{entropy}_{eps_spec.replace(':', '-').replace(',', '_')}.json")
    old = json.loads(out.read_text()) if out.exists() else []
    done = {(r["episode"], r["cls"]) for r in old if r.get("J_agent") is not None}
    rows = [r for r in old if (r["episode"], r["cls"]) in done]
    jobs = [(n, c) for c in classes for n in ns if (n, c) not in done]
    print(f"episodes {ns}, classes {classes}, {len(jobs)} runs", flush=True)

    def safe(n, c):
        try:
            return run(n, c, es._spec, root, refs)
        except Exception as err:  # keep the batch going; the row says what failed
            return dict(episode=n, cls=c, error=repr(err)[:300], J_agent=None, J_oracle=None)

    for r in Parallel(n_jobs=n_jobs, verbose=10, return_as="generator_unordered")(delayed(safe)(n, c) for n, c in jobs):
        rows.append(r)
        out.write_text(json.dumps(rows, indent=1, default=str))
    report(rows, es)


def report(rows, es=None):
    if es is None:
        es = episode_set("full", 0, "dev", 4)
    refs = {int(r["episode"]): r for r in es.references}
    ns = [int(r["episode"]) for r in es.references]
    by = {(r["episode"], r["cls"]): r for r in rows if r.get("J_agent") is not None and r.get("J_oracle") is not None}
    bad = [(r["episode"], r["cls"], r.get("error", "oracle not solved")) for r in rows
           if r.get("J_agent") is None or r.get("J_oracle") is None]
    if bad:
        print("left out (failed runs):", bad)
    base = {n: by[(n, "base")] for n in ns if (n, "base") in by}
    Jb = [base[n]["J_agent"] * 100 for n in ns]
    rss0 = es.rss(Jb)["rss"]
    print(f"\nbase: mpc_best RSS {rss0:.4f} on {len(ns)} episodes, fallback weeks "
          f"{sum(b['fallback_weeks'] for b in base.values())}")

    # --- threads
    lvl = {n: refs[n]["stratum"] for n in ns}
    print("\nmessage threads seen by the agent (real = matched to a real event; lead = onset week - first seen week)")
    print(f"  {'channels':34s} {'threads':>7s} {'/ep':>5s} {'real':>6s} {'lead med':>8s} {'range':>9s}"
          f" {'withdrawn':>9s} {'with stated':>11s}")
    from collections import defaultdict
    st = defaultdict(list)
    for n in ns:
        for x in base[n]["threads"]:
            st["+".join(CHANNELS[c] for c in x["channels"])].append(x)
    for k, xs in sorted(st.items()):
        real = [x for x in xs if x["real"]]
        ld = [x["lead"] for x in real]
        print(f"  {k:34s} {len(xs):7d} {len(xs) / len(ns):5.1f} {len(real) / len(xs):6.1%} "
              f"{(np.median(ld) if ld else float('nan')):8.1f} {(f'{min(ld)}..{max(ld)}' if ld else '-'):>9s}"
              f" {np.mean([x['withdrawn_week'] is not None for x in xs]):9.1%}"
              f" {np.mean([x['stated'] >= 0 for x in xs]):11.1%}")
    # per thread: is the decoy withdrawn before the stated/onset week?  lead of mid_threat by target kind
    mids = [x for n in ns for x in base[n]["threads"] if 5 in x["channels"]]
    if mids:
        print(f"\n  mid_threat threads: target kinds {dict(zip(*np.unique([x['tk'] for x in mids], return_counts=True)))}"
              f", real leads {sorted(x['lead'] for x in mids if x['real'])}")
    # events with / without any message
    print("\nevents starting inside the episode (dev 20): count, share with a message thread the agent saw first")
    ev = defaultdict(lambda: [0, 0, []])
    for n in ns:
        for e in base[n]["events"]:
            s = ev[e["type"]]
            s[0] += 1
            if e["thread"] is not None:
                s[1] += 1
                s[2].append(e["week"] - min(max(1, w) for w in e["shown"].values()))
    for k, (cnt, msg, ld) in sorted(ev.items()):
        print(f"  {k:20s} {cnt:4d} ({cnt / len(ns):4.1f}/ep)  with a message {msg / cnt:6.1%}  "
              f"lead med {np.median(ld) if ld else float('nan'):5.1f} w")

    # --- ceilings
    print(f"\nceiling of perfect foresight per class (T USD/ep; RSS points with the level weights, "
          f"= rss(J_agent - ceiling) - rss(J_agent))")
    print(f"  {'class':12s} {'dropped/ep':>10s} {'dAgent T':>9s} {'dOracle T':>9s} {'ceiling T':>9s} {'RSS pts':>8s}"
          f" {'L1':>7s} {'L2':>7s} {'L3':>7s} {'L4':>7s}   per episode (ceiling T)")
    for c in CLASSES:
        if c == "base":
            continue
        if not all((n, c) in by for n in ns):
            miss = [n for n in ns if (n, c) not in by]
            if len(miss) == len(ns):
                continue
            print(f"  {c}: missing episodes {miss}, counted as ceiling 0")
        dA = np.array([base[n]["J_agent"] - by[(n, c)]["J_agent"] if (n, c) in by else 0 for n in ns])
        dO = np.array([base[n]["J_oracle"] - by[(n, c)]["J_oracle"] if (n, c) in by else 0 for n in ns])
        ceil = dA - dO
        pts = es.rss([J - x * 100 for J, x in zip(Jb, ceil)])["rss"] - rss0
        per_lvl = []
        for s in (1, 2, 3, 4):
            cs = np.array([x if lvl[n] == s else 0 for n, x in zip(ns, ceil)])
            per_lvl.append(es.rss([J - x * 100 for J, x in zip(Jb, cs)])["rss"] - rss0)
        drop = np.mean([by[(n, c)]["dropped"] for n in ns if (n, c) in by])
        print(f"  {c:12s} {drop:10.1f} {dA.mean() / 1e12:9.3f} {dO.mean() / 1e12:9.3f} {ceil.mean() / 1e12:9.3f}"
              f" {pts:+8.4f} " + " ".join(f"{p:+7.4f}" for p in per_lvl) +
              "   " + " ".join(f"{x / 1e12:+.3f}" for x in ceil))
    print("  (episodes in order", ns, "levels", [lvl[n] for n in ns], ")")


if __name__ == "__main__":
    if sys.argv[1] == "report":
        report(json.loads(Path(sys.argv[2]).read_text()))
    else:
        main(*sys.argv[1:])
