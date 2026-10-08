"""Test runner: play several agent variants on the same episodes and compare each with a baseline, paired.

    uv run python outputs/variants.py <task> <entropy> <episodes> <variants.json> [n_jobs]

    task       small | full
    entropy    an integer root, or "random" (a fresh root, printed so the round can be repeated); 0 is the dev root
    episodes   a count k (episodes 0..k-1), "dev" (the official dev split, root 0 only), a list "3,7,12", or
               "devpick:a,b,c,d" (root 0 only: the first a/b/c/d dev episodes of harm levels 1/2/3/4)
    variants   a JSON file {"name": {"agent": "agents/mpc_chip", "params": {...}}, ...}; the FIRST entry is the
               baseline every other one is compared with. "params" (optional) is written to the copy's params.json,
               so one agent folder serves many variants; without "params" the agent's own params.json is kept
               (before task 25 it was dropped, so {"agent": "agents/mpc_fab3sell"} ran with the code defaults).
    n_jobs     worker processes (default 3)

Each variant is copied to outputs/variants/<round>/<name>/ and played with EpisodeSet.play (the scorer's path). Prints
RSS, RSS per harm level, fallback weeks and the 90% paired interval of (variant - baseline); writes
outputs/variants/<round>/results.json.
"""

import hashlib
import json
import random
import shutil
import sys
import time
from pathlib import Path

import numpy as np
from shockbench_flow_agent.scoring import LEVEL, N_BOOT, EpisodeSet, _boot_stats, _interval


CACHE = Path("outputs/variants/_baseline_cache")


def pick_episodes(task, entropy, spec, n_jobs):
    if spec == "dev":
        return "dev"
    if spec.startswith("devpick:"):
        if entropy != 0:
            raise SystemExit("devpick needs entropy 0 (the dev root)")
        want = [int(x) for x in spec.split(":", 1)[1].split(",")]
        dev = EpisodeSet.build(task, "dev", entropy=0, n_jobs=n_jobs)
        out = []
        for level, k in zip((1, 2, 3, 4), want):
            out += [int(r["episode"]) for r in dev.references if r["stratum"] == level][:k]
        return out
    if "," in spec:
        return [int(x) for x in spec.split(",")]
    return int(spec)


def main(task, entropy, episodes, variants_file, n_jobs="3"):
    n_jobs = int(n_jobs)
    entropy = random.randint(1, 2**31 - 1) if entropy == "random" else int(entropy)
    variants = json.loads(Path(variants_file).read_text())
    names = list(variants)
    round_id = f"{Path(variants_file).stem}_{task}_{entropy}_{time.strftime('%m%d-%H%M')}"
    root = Path("outputs/variants") / round_id
    root.mkdir(parents=True, exist_ok=True)
    print(f"round {round_id}: task {task}, entropy {entropy}, episodes {episodes}, baseline {names[0]}", flush=True)

    t0 = time.time()
    eps = pick_episodes(task, entropy, episodes, n_jobs)
    es = EpisodeSet.build(task, eps, entropy=entropy, n_jobs=n_jobs)
    print(f"references ready in {time.time() - t0:.0f} s ({len(es.references)} episodes)", flush=True)

    res = {}
    for name in names:
        spec = variants[name]
        folder = root / name
        if folder.exists():
            shutil.rmtree(folder)
        shutil.copytree(spec["agent"], folder, ignore=shutil.ignore_patterns("__pycache__", "params.json"))
        if spec.get("params"):
            (folder / "params.json").write_text(json.dumps(spec["params"]))
        elif (Path(spec["agent"]) / "params.json").is_file():  # no "params": the agent's own params.json (task 25)
            shutil.copy(Path(spec["agent"]) / "params.json", folder / "params.json")
        t = time.time()
        cached = None
        if name == names[0]:  # the baseline: played once per (agent files + params, task, root, episodes)
            digest = hashlib.sha256()
            for f in sorted(p for p in folder.rglob("*") if p.is_file() and "__pycache__" not in p.parts):
                digest.update(f.relative_to(folder).as_posix().encode())
                digest.update(f.read_bytes())
            key = f"{task}_{entropy}_{episodes}_{digest.hexdigest()[:16]}".replace(",", "-").replace(":", "-")
            cached = CACHE / f"{key}.json"
        if cached is not None and cached.is_file():
            rows = json.loads(cached.read_text())
            print(f"  baseline {name}: reused {cached.name}", flush=True)
        else:
            rows = es.play(str(folder.resolve()), n_jobs=n_jobs)
            if cached is not None:
                CACHE.mkdir(parents=True, exist_ok=True)
                cached.write_text(json.dumps(rows))
        J = [r["J_policy_cents"] for r in rows]
        table = es.rss(J)
        res[name] = {"J": J, "rss": table["rss"], "levels": table["rss_by_stratum"],
                     "fallback_weeks": sum(r["fallback_weeks"] for r in rows), "seconds": round(time.time() - t),
                     "spec": spec}
        print(f"  played {name} in {res[name]['seconds']} s: RSS {table['rss']:.4f}", flush=True)
        (root / "results.json").write_text(json.dumps({"task": task, "entropy": entropy, "episodes": episodes,
                                                       "results": res}, indent=1))

    base = res[names[0]]
    print(f"\n{task}, entropy {entropy}, {len(base['J'])} episodes; diff = variant - {names[0]}, "
          f"{int(LEVEL * 100)}% paired interval")
    print(f"{'variant':24s} {'RSS':>7s} {'L1':>6s} {'L2':>6s} {'L3':>6s} {'L4':>6s} {'diff':>8s}  interval"
          "               better%  fallb")
    pooled = es.rss(base["J"]).get("pooled", True)
    for name in names:
        r = res[name]
        lv = r["levels"] or {}
        if name == names[0]:
            d, lo, hi, share = 0.0, 0.0, 0.0, float("nan")
        else:
            ba, bb = _boot_stats(es.references, [r["J"], base["J"]], pooled, N_BOOT, 0)
            diff = ba - bb
            iv = _interval(diff, LEVEL)
            lo, hi = iv if iv is not None else (float("nan"), float("nan"))
            d = r["rss"] - base["rss"]
            share = float(np.mean(diff > 0)) * 100
        cells = " ".join(f"{lv[s]:6.3f}" if lv.get(s) is not None else "     -" for s in (1, 2, 3, 4))
        flag = "  <-- better" if lo > 0 else ("  <-- worse" if hi < 0 else "")
        print(f"{name:24s} {r['rss']:7.4f} {cells} {d:+8.4f}  [{lo:+.4f}, {hi:+.4f}]  {share:6.1f}%  "
              f"{r['fallback_weeks']:5d}{flag}")
        if name != names[0]:
            r["interval"] = [lo, hi]
            r["better_share"] = share
    (root / "results.json").write_text(json.dumps({"task": task, "entropy": entropy, "episodes": episodes,
                                                   "results": res}, indent=1))
    print(f"\nresults: {root / 'results.json'}")


if __name__ == "__main__":
    main(*sys.argv[1:])
