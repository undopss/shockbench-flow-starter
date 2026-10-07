"""Write EXPERIMENTS.md from the server's experiment history (~/sbf-jobs/www/experiments.json): every finished test."""
import json, sys, time
d = json.load(open(sys.argv[1], encoding="utf-8"))
rows = sorted(d["done"], key=lambda x: x.get("finished") or 0)
out = ["# Experiment log", "", f"Generated {time.strftime('%Y-%m-%d %H:%M')} from the home server's queue (and cloud task branches).",
       "Each row: one idea vs its baseline on the same episodes; diff = RSS(variant) - RSS(baseline); better/worse = the whole",
       "90% paired interval is above/below 0. Stages: small20 (filter) -> full6 (devpick 2,2,1,1) -> full20 (official dev); fresh-* = never-used seeds.", "",
       "| # | finished | verdict | idea | stage | seed | variant RSS | baseline RSS | diff | 90% interval | L1 (calm) | source |",
       "|---|---|---|---|---|---|---|---|---|---|---|---|"]
for i, x in enumerate(rows, 1):
    r = x.get("result") or {}
    iv = r.get("interval") or [None, None]
    f = lambda v, s=False: "-" if v is None else (f"{v:+.4f}" if s else f"{v:.4f}")
    l1 = (r.get("levels") or {}).get("1")
    when = time.strftime("%m-%d %H:%M", time.localtime(x["finished"])) if x.get("finished") else "-"
    out.append(f"| {i} | {when} | **{x.get('verdict')}** | {x.get('title') or x['id']} | {x.get('stage')} | {x.get('entropy')} | "
               f"{f(r.get('variant_rss'))} | {f(r.get('baseline_rss'))} | {f(r.get('diff'), True)} | [{f(iv[0], True)}, {f(iv[1], True)}] | "
               f"{'-' if l1 is None else f'{l1:.3f}'} | {x.get('source', '')} |")
out += ["", "## Ideas (plain words)", ""]
seen = set()
for x in rows:
    t = x.get("title") or x["id"]
    if t in seen or not x.get("idea"):
        continue
    seen.add(t)
    out.append(f"- **{t}:** {x['idea']}")
open(sys.argv[2], "w", encoding="utf-8").write("\n".join(out) + "\n")
print(len(rows), "rows")
