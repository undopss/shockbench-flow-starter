"""Do the early signals come true? Chokepoint warnings vs closures, and announcement threads' fate.

    python outputs/warnings_study.py small 200 2
"""

import sys
from collections import defaultdict

import gymnasium as gym
import numpy as np
import shockbench_flow_gym  # noqa: F401
from joblib import Parallel, delayed

ENV = {"small": "ShockBench/Small-v0", "full": "ShockBench/Full-v0"}
CHANNELS = ["tariff_formal", "tariff_informal", "tariff_final", "sanction_legal", "ties_threat", "mid_threat"]
K = 8  # look-ahead in weeks


def episode(task, ep):
    import shockbench_flow_gym  # noqa: F401 - registers the envs in a joblib worker

    env = gym.make(ENV[task])
    obs, info = env.reset(options={"episode": ep})
    units = info.get("static", {})  # unused; the layout is fixed per task
    env.action_space.seed(0)
    warn, opened, threads, done, t = [], [], {}, False, 0
    while not done:
        t += 1
        warn.append(np.array(obs["warning.score"], dtype=float))
        opened.append(np.array(obs["graph_now.open"], dtype=float))
        ids = np.array(obs["messages.msg_id"])
        seen = np.array(obs["messages.msg_id.observed"], dtype=bool) if "messages.msg_id.observed" in obs else ids >= 0
        for i in np.flatnonzero(seen):
            m = int(ids[i])
            th = threads.setdefault(m, {"channel": int(obs["messages.channel"][i]), "first": t,
                                        "stated": int(obs["messages.stated_effective_week"][i])})
            th["last"] = t
        obs, _, te, tr, _ = env.step(env.action_space.sample())
        done = te or tr
    del units
    return np.array(warn), np.array(opened), threads, t


def auc(score, label):
    pos, neg = score[label], score[~label]
    if not len(pos) or not len(neg):
        return float("nan")
    order = np.argsort(np.concatenate([pos, neg]), kind="mergesort")
    ranks = np.empty(len(order))
    ranks[order] = np.arange(1, len(order) + 1)
    return (ranks[: len(pos)].sum() - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg))


def main(task="small", neps=200, n_jobs=2):
    eps = Parallel(n_jobs=int(n_jobs))(delayed(episode)(task, e) for e in range(int(neps)))
    C = eps[0][1].shape[1]
    first_chk = eps[0][0].shape[1] - C  # the chokepoint units are the last C warning units, in chokepoint order

    # 1) chokepoint warning at week t (chokepoint open now) vs a closure starting within the next K weeks
    S, Y, starts = [], [], 0
    for warn, opened, _, T in eps:
        closed = opened < 1.0
        for c in range(C):
            for t in range(T - K):
                if closed[t, c]:
                    continue
                y = closed[t + 1:t + 1 + K, c].any()
                S.append(warn[t, first_chk + c])
                Y.append(y)
            starts += int((closed[1:, c] & ~closed[:-1, c]).sum())
    S, Y = np.array(S), np.array(Y, dtype=bool)
    print(f"{task}, {neps} episodes: {starts} closure starts; chokepoint-weeks open: {len(S)}, "
          f"of which a closure follows within {K} weeks: {Y.mean():.3%}")
    print(f"warning score as a predictor of that: AUC {auc(S, Y):.3f} (0.5 = useless, 1 = perfect)")
    qs = np.unique(np.quantile(S, [0, 0.5, 0.8, 0.9, 0.95, 0.99, 1.0]))
    print("  score band              weeks   closure follows")
    for lo, hi in zip(qs[:-1], qs[1:]):
        m = (S >= lo) & (S <= hi if hi == qs[-1] else S < hi)
        if m.any():
            print(f"  [{lo:8.3f}, {hi:8.3f}]  {m.sum():8d}   {Y[m].mean():8.2%}")

    # 2) announcement threads: did they reach their stated week while still live (no sign of withdrawal)?
    stats = defaultdict(lambda: [0, 0, 0])  # channel -> [threads, with a stated week in the episode, vanished early]
    for _, _, threads, T in eps:
        for th in threads.values():
            s = stats[CHANNELS[th["channel"]] if 0 <= th["channel"] < len(CHANNELS) else th["channel"]]
            s[0] += 1
            if 0 < th["stated"] <= T:
                s[1] += 1
                s[2] += th["last"] < th["stated"] - 1  # gone from the live list well before its stated week
    print("\nannouncement threads (live list = announced, not effective, not withdrawn)")
    print("  channel            threads  stated week  left the list >1 week before it")
    for ch, (n, ns, early) in sorted(stats.items(), key=lambda kv: str(kv[0])):
        print(f"  {str(ch):18s} {n:7d}  {ns:11d}  {early:7d} ({early / ns if ns else float('nan'):.0%})")


if __name__ == "__main__":
    main(*sys.argv[1:])
