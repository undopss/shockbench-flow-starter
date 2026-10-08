"""Print the tables of a miss25.py output: uv run python outputs/task-25/report25.py outputs/task-25/miss_<tag>.json"""
import json
import sys

import numpy as np

rows = json.load(open(sys.argv[1]))
n = len(rows)
print(f"{n} episodes: {[r['episode'] for r in rows]}")
print(f"CPU per week: max {max(max(r['cpu']) for r in rows):.2f} s, median {np.median([c for r in rows for c in r['cpu']]):.3f} s")

print("\n== clip: requested vs executed, by slot class (sum over episodes)")
cls = {}
for r in rows:
    for k, (q, e) in r["clip_class"].items():
        a = cls.setdefault(k, [0.0, 0.0]); a[0] += q; a[1] += e
for k, (q, e) in sorted(cls.items()):
    if q > 0:
        print(f"  {k:36s} requested {q / n:14.0f}/ep  executed {e / n:14.0f}/ep  {e / q:7.4f}")
top = {}
for r in rows:
    for s, name, q, e in r["clip_top"]:
        a = top.setdefault(name, [0.0, 0.0]); a[0] += q; a[1] += e
print("  most clipped slots (units/ep):")
for name, (q, e) in sorted(top.items(), key=lambda kv: -(kv[1][0] - kv[1][1]))[:8]:
    print(f"    {name:70s} req {q / n:12.0f} exe {e / n:12.0f} ({e / max(q, 1e-9):.3f})")

print("\n== fuel LP (week-0 prediction vs record), per pool, mean over episodes")
print(f"  {'grid':10s} {'fuel':8s} {'burn/wk':>9s} {'real/pred burn':>14s} {'LP sf wks':>9s} {'sf/burn':>8s} "
      f"{'real short wks':>14s} {'stock bias (wks of burn)':>24s}")
pools = {}
for r in rows:
    for f in r["fuel"]:
        pools.setdefault((f["grid"], f["k"]), []).append(f)
for (g, k), fs in pools.items():
    b = np.mean([f["burn"] for f in fs])
    print(f"  {g:10s} {k:8s} {b:9.0f} {np.mean([f['burn_ratio'] for f in fs]):14.3f} "
          f"{np.mean([f['sf_weeks'] for f in fs]):9.1f} {np.mean([f['sf_over_burn'] for f in fs]):8.3f} "
          f"{np.mean([f['real_short_weeks'] for f in fs]):14.1f} {np.mean([f['stock_bias'] for f in fs]) / max(b, 1e-9):24.2f}")

print("\n== fuel LP, 5 weeks ahead (weeks w..w+4): stock at the end vs real, shortfall vs real (weeks of burn)")
for (g, k), fs in pools.items():
    b = np.mean([f["burn"] for f in fs])
    if "stock4_bias" in fs[0]:
        print(f"  {g:10s} {k:8s} stock bias {np.mean([f['stock4_bias'] for f in fs]) / max(b, 1e-9):8.2f}  "
              f"mae {np.mean([f['stock4_mae'] for f in fs]) / max(b, 1e-9):7.2f}  "
              f"real short - LP short {np.mean([f['short4_bias'] for f in fs]) / max(b, 1e-9):8.2f}")

print("\n== pulse planner: week-0 prediction vs record, per grid (sum over weeks, mean over episodes)")
pp = {}
for r in rows:
    for g, d in r["pp"].items():
        a = pp.setdefault(g, {})
        for k, v in d.items():
            if isinstance(v, list):
                a[k] = [x + y for x, y in zip(a.get(k, [0] * len(v)), v)]
            else:
                a[k] = a.get(k, 0) + v
for g, d in pp.items():
    print(f"  {g:10s} homes pred {d['y_pred'] / n:12.0f} real {d['y_real'] / n:12.0f} | fab E pred {d['E_pred'] / n:9.0f} "
          f"real {d['E_real'] / n:9.0f} draw {d['ehat'] / n:9.0f} | E pred>0 but real<10%: {d['E_pred_pos_real0'] / n:.1f} wks "
          f"| modes hold/fill/fill+line/all/split {d['modes'][:5]}")

print("\n== chip LP: week-0 prediction vs record (sum over weeks, mean over episodes)")
sk = {}
for r in rows:
    for s in r["chip_sink"]:
        a = sk.setdefault((s["sink"], s["k"]), [0.0, 0.0, s["pi"]]); a[0] += s["pred"]; a[1] += s["real"]
tot = 0.0
for (s, k), (p_, r_, pi) in sk.items():
    tot += (r_ - p_) * pi
    if p_ + r_ > 0:
        print(f"  {s:10s} {k:9s} served pred {p_ / n:12.0f} real {r_ / n:12.0f}  miss {(r_ - p_) / n:+11.0f} = {(r_ - p_) * pi / n / 1e9:+8.2f} B USD")
print(f"  total served miss (real - pred) x pi: {tot / n / 1e12:+.4f} T USD/ep")
if "pred5" in rows[0]["chip_sink"][0]:
    print("  5 weeks ahead (sum over windows w..w+4): served pred vs real, demand forecast vs real")
    s5 = {}
    for r in rows:
        for s in r["chip_sink"]:
            a = s5.setdefault((s["sink"], s["k"]), [0.0] * 4 + [s["pi"]])
            for i, key in enumerate(("pred5", "real5", "dem5_pred", "dem5_real")):
                a[i] += s[key]
    tot5 = 0.0
    for (s, k), (p5, r5, dp, dr, pi) in s5.items():
        tot5 += (r5 - p5) * pi
        if p5 + r5 > 0:
            print(f"    {s:10s} {k:9s} served real/pred {r5 / max(p5, 1e-9):6.3f}  demand real/forecast {dr / max(dp, 1e-9):6.3f}")
    print(f"    total 5-week served miss x pi, per window: {tot5 / n / 1e12 / 100:+.4f} T USD (sum over ~100 windows / 100)")
fb = {}
for r in rows:
    for f in r["chip_fab"]:
        a = fb.setdefault(f["fab"], [0.0, 0.0]); a[0] += f["pred"]; a[1] += f["real"]
for f, (p_, r_) in fb.items():
    print(f"  {f:20s} lots started pred {p_ / n:12.0f} real {r_ / n:12.0f}  real/pred {r_ / max(p_, 1e-9):8.2f}")
print(f"  chip-position disposal pred {np.mean([r['chip_disp'][0] for r in rows]):.0f} real {np.mean([r['chip_disp'][1] for r in rows]):.0f} per ep")
