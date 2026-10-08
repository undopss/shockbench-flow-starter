"""Task 15, step 1: do the early signals predict events on Full? Ground truth from each episode's omega.

    uv run python outputs/task-15/signals.py full 120 4

Per signal type: warning.score of region units (vs any P/M event touching the region, and conflict onsets z_c),
of the dyad unit (vs dyad war onsets and conflicts between its two regions), of chokepoint units (vs closures);
messages.* threads (precision = not withdrawn, lead = stated week - first seen week; recall from ev_lead);
pending_prohibitions (precision = the edge really is prohibited for k at its effective week).
Writes outputs/task-15/signals_<task>_<n>.json.
"""

import json
import math
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from joblib import Parallel, delayed

ENV = {"small": "ShockBench/Small-v0", "full": "ShockBench/Full-v0"}
TYPES = ("tariff", "sanction", "material_outage", "militarised_closure", "regional_conflict", "piracy",
         "energy_shock", "weather_closure", "port_strike")
CHANNELS = ("tariff_formal", "tariff_informal", "tariff_final", "sanction_legal", "ties_threat", "mid_threat")
KS = (4, 8, 12)


def episode(task, ep):
    import gymnasium as gym
    import shockbench_flow_gym  # noqa: F401
    from shockbench_flow.marks import compute_marks

    env = gym.make(ENV[task])
    obs, info = env.reset(options={"episode": ep})
    u = env.unwrapped
    om = u.omega_source(ep) if callable(u.omega_source) else u.omega_source
    inst = u.instance
    marks = compute_marks(inst, om)
    T = inst.T
    B = int(om["meta_burn_in"])
    env.action_space.seed(0)
    warn, threads, pend, t, done = [], {}, {}, 0, False
    while not done:
        t += 1
        warn.append(np.array(obs["warning.score"], dtype=float))
        ids = np.asarray(obs["messages.msg_id"])
        seen = np.asarray(obs["messages.msg_id.observed"], dtype=bool)
        for i in np.flatnonzero(seen):
            m = int(ids[i])
            th = threads.setdefault(m, dict(channel=int(obs["messages.channel"][i]), first=t,
                                            region=int(obs["messages.region"][i]),
                                            tk=int(obs["messages.target_kind"][i]), target=int(obs["messages.target"][i]),
                                            stated=-1, withdrawn=False, kinds=set()))
            kind = int(obs["messages.kind"][i])
            th["kinds"].add(kind)
            if kind == 4:
                th["withdrawn"] = True
            if obs["messages.stated_effective_week.observed"][i]:
                th["stated"] = max(th["stated"], int(obs["messages.stated_effective_week"][i]))
            ch = int(obs["messages.channel"][i])
            th["channels"] = sorted(set(th.get("channels", [])) | {ch})
        pe = np.asarray(obs["pending_prohibitions.edge"])
        ps = np.asarray(obs["pending_prohibitions.edge.observed"], dtype=bool)
        for i in np.flatnonzero(ps):
            key = (int(pe[i]), int(obs["pending_prohibitions.k"][i]), int(obs["pending_prohibitions.effective_week"][i]))
            pend.setdefault(key, t)
        obs, _, te, tr, _ = env.step(env.action_space.sample())
        done = te or tr
    W = np.array(warn)  # (T, U)

    ev = {k: np.asarray(om["ev_" + k]) for k in ("type", "region", "counterpart", "target_kind", "target", "onset",
                                                   "duration", "commodity")}
    lead = np.asarray(om["ev_lead"]).reshape(len(ev["type"]), -1) if len(ev["type"]) else np.zeros((0, 6))
    events, events_all = [], []
    for i in range(len(ev["type"])):
        s = float(ev["onset"][i])
        if s >= T:
            continue
        row = (dict(type=int(ev["type"][i]), region=int(ev["region"][i]), cp=int(ev["counterpart"][i]),
                           tk=int(ev["target_kind"][i]), target=int(ev["target"][i]), week=int(math.floor(s)) + 1,
                           dur=float(ev["duration"][i]),
                           lead=[None if np.isnan(x) else float(x) for x in lead[i]], onset=s))
        events_all.append(row)
        if s >= 0:
            events.append(row)
    zc = np.asarray(om["z_c"])[:, B + 1:B + T + 1]  # (R, T): state in force in week t at column t + B
    zd = np.asarray(om["z_dyad"])[:, B + 1:B + T + 1]
    # a thread is real when a real event of its channel's type, region and target was announced when it appeared
    CH_TYPE = {0: 0, 1: 0, 2: 0, 3: 1, 4: 1, 5: 3}
    for th in threads.values():
        th["kinds"] = sorted(th["kinds"])
        th["real"] = False
        for x in events:
            if x["type"] != CH_TYPE[th["channel"]] or (x["region"], x["tk"], x["target"]) != (th["region"], th["tk"],
                                                                                          th["target"]):
                continue
            shown = [math.ceil(x["onset"] - L) + 1 for L in x["lead"] if L is not None]
            if shown and max(1, min(shown)) <= th["first"] <= max(1, min(shown)) + 12:
                th["real"] = True
                th["onset_week"] = x["week"]
                break
    pend_rows = [dict(edge=e, k=k, week=w, first=f, real=bool(1 <= w <= T and marks.prohibited[w - 1, e, k]))
                 for (e, k, w), f in pend.items()]
    return dict(ep=ep, T=T, W=W.tolist(), events=events, zc=zc.tolist(), zd=zd.tolist(),
                threads=list(threads.values()), pend=pend_rows,
                dyads=np.asarray(om["dyad_regions"]).tolist(), chk=[int(c) for c in inst.chokepoints])


def auc(score, label):
    score, label = np.asarray(score, float), np.asarray(label, bool)
    pos, neg = score[label], score[~label]
    if not len(pos) or not len(neg):
        return float("nan")
    allv = np.concatenate([pos, neg])
    order = np.argsort(allv, kind="mergesort")
    ranks = np.empty(len(order))
    ranks[order] = np.arange(1, len(order) + 1)
    # average ties
    vals = allv[order]
    i = 0
    while i < len(vals):
        j = i
        while j + 1 < len(vals) and vals[j + 1] == vals[i]:
            j += 1
        if j > i:
            ranks[order[i:j + 1]] = (i + j + 2) / 2
        i = j + 1
    return float((ranks[: len(pos)].sum() - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg)))


def unit_labels(e, R):
    """For every signal unit: list of event onset weeks it should predict, by target name."""
    T = e["T"]
    out = defaultdict(list)  # (unit, target) -> onset weeks
    ev = e["events"]
    for m in range(R):
        out[(m, "any_PM_event")] = [x["week"] for x in ev if x["type"] <= 6 and m in (x["region"], x["cp"])]
        out[(m, "regional_conflict")] = [x["week"] for x in ev if x["type"] == 4 and m in (x["region"], x["cp"])]
        zc = np.array(e["zc"][m])
        out[(m, "conflict_onset")] = [t + 1 for t in range(1, T) if zc[t] > 0 and zc[t - 1] == 0]
    for d, (a, b) in enumerate(e["dyads"]):
        zd = np.array(e["zd"][d])
        out[(R + d, "dyad_war_onset")] = [t + 1 for t in range(1, T) if zd[t] > zd[t - 1]]
        out[(R + d, "conflict_between")] = [x["week"] for x in ev if x["type"] == 4 and {x["region"], x["cp"]} == {a, b}]
        out[(R + d, "conflict_in_either")] = [x["week"] for x in ev if x["type"] == 4 and (x["region"] in (a, b))]
    D = len(e["dyads"])
    for ci, c in enumerate(e["chk"]):
        out[(R + D + ci, "closure")] = [x["week"] for x in ev if x["type"] in (3, 7) and x["tk"] == 0 and x["target"] == c]
        out[(R + D + ci, "militarised_closure")] = [x["week"] for x in ev if x["type"] == 3 and x["tk"] == 0
                                                    and x["target"] == c]
    return out


def main(task="full", neps=120, n_jobs=4):
    neps, n_jobs = int(neps), int(n_jobs)
    eps = Parallel(n_jobs=n_jobs, verbose=5)(delayed(episode)(task, n) for n in range(neps))
    out = Path(f"outputs/task-15/signals_{task}_{neps}.json")
    out.write_text(json.dumps(eps))
    report(eps, task)


def report(eps, task):
    U = len(eps[0]["W"][0])
    R = U - len(eps[0]["dyads"]) - len(eps[0]["chk"])
    print(f"{task}: {len(eps)} episodes, {U} warning units ({R} regions, {len(eps[0]['dyads'])} dyads, "
          f"{len(eps[0]['chk'])} chokepoints)")

    # --- events in episodes
    cnt = defaultdict(int)
    for e in eps:
        for x in e["events"]:
            cnt[TYPES[x["type"]]] += 1
    print("\nevents starting inside the episode, per episode:", {k: round(v / len(eps), 2) for k, v in sorted(cnt.items())})

    # --- warnings: pooled per unit kind and target, AUC for horizons K
    print("\nwarning.score -> event onset within K weeks (pooled unit-weeks; AUC 0.5 = useless)")
    print(f"  {'unit kind':10s} {'target':22s} {'K':>3s} {'base rate':>9s} {'AUC':>6s} {'prec@top5%':>10s} {'prec@top1%':>10s}")
    groups = defaultdict(lambda: ([], []))
    for e in eps:
        W = np.array(e["W"])
        T = e["T"]
        labs = unit_labels(e, R)
        for (unit, name), weeks in labs.items():
            kind = "region" if unit < R else ("dyad" if unit < R + len(e["dyads"]) else "chokepoint")
            wk = np.array(weeks, int)
            for K in KS:
                S, Y = groups[(kind, name, K)]
                for t in range(1, T - K + 1):
                    S.append(W[t - 1, unit])
                    Y.append(bool(((wk > t) & (wk <= t + K)).any()))
    res = {}
    for (kind, name, K), (S, Y) in sorted(groups.items()):
        S, Y = np.array(S), np.array(Y)
        a = auc(S, Y)
        p5 = Y[S >= np.quantile(S, 0.95)].mean()
        p1 = Y[S >= np.quantile(S, 0.99)].mean()
        res[f"{kind}/{name}/K{K}"] = dict(base=float(Y.mean()), auc=a, p5=float(p5), p1=float(p1), n=int(len(S)))
        print(f"  {kind:10s} {name:22s} {K:3d} {Y.mean():9.2%} {a:6.3f} {p5:10.2%} {p1:10.2%}")

    # --- lead of warning: how far ahead of an onset does the unit's score rise above its 95% line?
    print("\nwarning lead: share of onsets preceded (1..12 weeks before) by a score above the unit kind's 95% quantile,"
          " and the median weeks between the first such week and the onset")
    allW = np.concatenate([np.array(e["W"]) for e in eps])
    for kind, name in sorted({(k, n) for k, n, _ in groups}):
        hit, leads, nev = 0, [], 0
        for e in eps:
            W = np.array(e["W"])
            labs = unit_labels(e, R)
            for (unit, nm), weeks in labs.items():
                if nm != name:
                    continue
                q = np.quantile(allW[:, unit], 0.95)
                for w in weeks:
                    lo = max(1, w - 12)
                    if w - 1 < lo:
                        continue
                    nev += 1
                    above = [t for t in range(lo, w) if W[t - 1, unit] >= q]
                    if above:
                        hit += 1
                        leads.append(w - above[0])
        if nev:
            print(f"  {kind:10s} {name:22s} onsets {nev:5d}  warned {hit / nev:6.1%}  median lead "
                  f"{np.median(leads) if leads else float('nan'):4.1f} w")

    # --- announcements: recall and lead from ev_lead (real events)
    print("\nreal events starting in the episode: share announced on each channel, median lead (weeks)")
    for ty in range(9):
        evs = [x for e in eps for x in e["events"] if x["type"] == ty]
        if not evs:
            continue
        parts = []
        for c in range(6):
            ls = [x["lead"][c] for x in evs if x["lead"][c] is not None]
            if ls:
                parts.append(f"{CHANNELS[c]} {len(ls) / len(evs):.0%} (lead {np.median(ls):.1f})")
        print(f"  {TYPES[ty]:20s} n={len(evs):5d}  " + ("; ".join(parts) if parts else "never announced"))

    # --- threads seen by the agent: precision by channel set
    print("\nmessage threads seen by an agent (real = matches a real omega event; lead = onset week - first seen)")
    st = defaultdict(lambda: [0, 0, []])
    for e in eps:
        for th in e["threads"]:
            key = "+".join(CHANNELS[c] for c in th["channels"])
            s = st[key]
            s[0] += 1
            s[1] += th["real"]
            if th["real"]:
                s[2].append(th["onset_week"] - th["first"])
    for k, (n, real, ld) in sorted(st.items()):
        print(f"  {k:36s} threads {n:6d} ({n / len(eps):5.1f}/ep)  real {real / n:6.1%}  median lead (real) "
              f"{np.median(ld) if ld else float('nan'):5.1f} w")

    # --- pending prohibitions
    P = [p for e in eps for p in e["pend"] if p["week"] <= e["T"]]
    if P:
        ld = [p["week"] - p["first"] for p in P if p["real"]]
        print(f"\npending_prohibitions entries: {len(P)} ({len(P) / len(eps):.1f}/ep), really prohibited at their week "
              f"{np.mean([p['real'] for p in P]):.1%}, median lead (real) {np.median(ld) if ld else float('nan'):.1f} w")
    Path(f"outputs/task-15/signals_{task}_{len(eps)}_summary.json").write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "report":
        report(json.loads(Path(sys.argv[2]).read_text()), sys.argv[3])
    else:
        main(*sys.argv[1:])
