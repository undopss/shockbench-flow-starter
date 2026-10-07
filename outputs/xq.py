"""Experiment queue for the home server: keeps MAX_RUNNING idea tests running and publishes their state for the page.

    ~/secrethon-mantis/.venv/bin/python ~/sbf-jobs/xq.py            # the scheduler loop (start with setsid nohup)
    ~/secrethon-mantis/.venv/bin/python ~/sbf-jobs/xq.py add FILE    # append the experiments of a JSON list to the queue
    ~/secrethon-mantis/.venv/bin/python ~/sbf-jobs/xq.py kill ID     # stop a queued or running experiment

An experiment is one idea against one baseline on one stage:
    {"id": "pulse_twkr_1.5_s1", "title": "Pulse fuel to TW/KR", "idea": "plain-words description",
     "stage": "small20" | "full6" | "full20", "task": "small", "entropy": 123, "episodes": "20",
     "baseline": {"name": "mpc_chip", "agent": "agents/mpc_chip", "params": {}},
     "variant": {"name": "pulse_twkr_1.5", "agent": "agents/mpc_chip", "params": {...}},
     "source": "claude@home" (who queued it), "n_jobs": 2}
Each runs as ``~/sbf-jobs/run`` does (sbfjob.py, so the progress bars work) on outputs/variants.py. When it ends, its
results.json gives the verdict: better (90% paired interval above 0), worse (below 0), or unclear.
State: ~/sbf-jobs/experiments/{queue,running,done}.json; page data: ~/sbf-jobs/www/experiments.json.
"""

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

HOME = Path.home()
REPO = HOME / "secrethon-mantis"
PY = REPO / ".venv" / "bin" / "python"
XDIR = HOME / "sbf-jobs" / "experiments"
WWW = HOME / "sbf-jobs" / "www"
STATUS = WWW / "status"
MAX_RUNNING = int(os.environ.get("XQ_MAX", "2"))


def load(name, default):
    try:
        return json.loads((XDIR / name).read_text())
    except (OSError, ValueError):
        return default


def save(name, data):
    tmp = XDIR / f".{name}.{os.getpid()}.tmp"
    tmp.write_text(json.dumps(data, indent=1, ensure_ascii=False))
    os.replace(tmp, XDIR / name)


def job_status(xid):
    try:
        return json.loads((STATUS / f"xp-{xid}.json").read_text())
    except (OSError, ValueError):
        return None


def start(x):
    vfile = XDIR / "variants" / f"{x['id']}.json"
    vfile.parent.mkdir(parents=True, exist_ok=True)
    spec = {x["baseline"]["name"]: {"agent": x["baseline"]["agent"], "params": x["baseline"].get("params") or {}},
            x["variant"]["name"]: {"agent": x["variant"]["agent"], "params": x["variant"].get("params") or {}}}
    vfile.write_text(json.dumps(spec, indent=1))
    log = HOME / "sbf-logs" / f"xp-{x['id']}.log"
    cmd = [str(PY), "-u", str(HOME / "sbf-jobs" / "sbfjob.py"), f"xp-{x['id']}", "outputs/variants.py", x["task"],
           str(x["entropy"]), str(x["episodes"]), str(vfile), str(x.get("n_jobs", 2))]
    with open(log, "w") as fh:
        p = subprocess.Popen(cmd, cwd=REPO, stdout=fh, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                             start_new_session=True)
    x.update(state="running", pid=p.pid, started=time.time(), log=str(log))
    return x


def finish(x):
    """Read the round's results.json (its path is in the log's last line) into a verdict."""
    x["finished"] = time.time()
    try:
        lines = Path(x["log"]).read_text().splitlines()
        res_path = next(ln.split("results: ", 1)[1].strip() for ln in reversed(lines) if ln.startswith("results: "))
        res = json.loads((REPO / res_path).read_text())["results"]
        b, v = res[x["baseline"]["name"]], res[x["variant"]["name"]]
        x["result"] = {"baseline_rss": b["rss"], "variant_rss": v["rss"], "diff": v["rss"] - b["rss"],
                       "levels": v["levels"], "baseline_levels": b["levels"], "fallbacks": v["fallback_weeks"],
                       "interval": v.get("interval"), "better_share": v.get("better_share")}
        lo, hi = (v.get("interval") or [None, None])
        if lo is not None and lo > 0:
            x["verdict"] = "better"
        elif hi is not None and hi < 0:
            x["verdict"] = "worse"
        else:
            x["verdict"] = "unclear"
        x["state"] = "done"
    except Exception as err:  # noqa: BLE001
        x["state"] = "failed"
        x["verdict"] = "failed"
        x["error"] = f"{type(err).__name__}: {err}"
    return x


def publish(queue, running, done):
    for x in running:
        st = job_status(x["id"])
        if st:
            x["progress"] = {k: st.get(k) for k in ("phase", "done", "total", "last_line", "updated")}
    data = {"generated": time.time(), "max_running": MAX_RUNNING, "queue": queue, "running": running,
            "done": sorted(done, key=lambda d: d.get("finished", 0), reverse=True)}
    tmp = WWW / f".experiments.json.{os.getpid()}.tmp"
    tmp.write_text(json.dumps(data, ensure_ascii=False))
    os.replace(tmp, WWW / "experiments.json")


def alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def loop():
    XDIR.mkdir(parents=True, exist_ok=True)
    while True:
        queue, running, done = load("queue.json", []), load("running.json", []), load("done.json", [])
        inbox = XDIR / "inbox"  # `add` drops files here; only this loop writes queue.json (no lost updates)
        inbox.mkdir(exist_ok=True)
        for f in sorted(inbox.glob("*.json")):
            try:
                queue.extend(json.loads(f.read_text()))
            except (OSError, ValueError):
                continue
            f.unlink()
        still = []
        for x in running:
            st = job_status(x["id"])
            if st and st.get("state") in ("done", "failed") or not alive(x["pid"]):
                done.append(finish(x))
            else:
                still.append(x)
        running = still
        kills = XDIR / "kill"
        if kills.is_dir():
            drop = {f.name for f in kills.iterdir()}
            queue = [x for x in queue if x["id"] not in drop]
            for f in kills.iterdir():
                f.unlink()
        while len(running) < MAX_RUNNING and queue:
            running.append(start(queue.pop(0)))
        save("queue.json", queue)
        save("running.json", running)
        save("done.json", done)
        publish(queue, running, done)
        time.sleep(15)


def add(path):
    XDIR.mkdir(parents=True, exist_ok=True)
    (XDIR / "inbox").mkdir(exist_ok=True)
    ids = {x["id"] for x in load("queue.json", []) + load("running.json", []) + load("done.json", [])}
    new = []
    for x in json.loads(Path(path).read_text()):
        if x["id"] in ids:
            print(f"skip {x['id']}: id already used")
            continue
        x.setdefault("state", "queued")
        x["queued"] = time.time()
        new.append(x)
        print(f"queued {x['id']}")
    tmp = XDIR / "inbox" / f".{time.time_ns()}.tmp"
    tmp.write_text(json.dumps(new))
    os.replace(tmp, XDIR / "inbox" / f"{time.time_ns()}.json")


def kill(xid):
    """Stop a running experiment (the loop then records it as failed); drop a queued one via the inbox."""
    for x in load("running.json", []):
        if x["id"] == xid and alive(x["pid"]):
            os.killpg(os.getpgid(x["pid"]), signal.SIGTERM)
            print(f"stopped {xid}")
            return
    (XDIR / "inbox").mkdir(exist_ok=True)
    (XDIR / "kill").mkdir(exist_ok=True)
    (XDIR / "kill" / xid).touch()
    print(f"marked {xid} to drop from the queue")


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "add":
        add(sys.argv[2])
    elif len(sys.argv) > 2 and sys.argv[1] == "kill":
        kill(sys.argv[2])
    else:
        loop()
