"""At week W of Full ep 0 (gym), show what binds in the chip LP: fab starts vs cap, OSAT use vs thr, sink service vs demand."""
import importlib.util, sys, json, numpy as np, gymnasium as gym, shockbench_flow_gym
from shockbench_flow_agent import agent_config
W = int(sys.argv[1]); params = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}
ep = int(sys.argv[3]) if len(sys.argv) > 3 else 0
agent_dir = sys.argv[4] if len(sys.argv) > 4 else "agents/mpc_chip"
s = importlib.util.spec_from_file_location("m", f"{agent_dir}/agent.py"); m = importlib.util.module_from_spec(s); s.loader.exec_module(m)
m.PARAMS |= params
env = gym.make("ShockBench/Full-v0"); obs, info = env.reset(options={"episode": ep})
cfg = agent_config(info["static"], info["policy_seed"], env.unwrapped.layout, obs)
ag = m.Agent(cfg); ch = ag.chips
ids = [n["id"] for n in info["static"]["instance"]["nodes"]]; com = cfg["static"]["commodities"]["id"]
store = {}
orig = m._chips.linprog
def lp(*a, **k):
    r = orig(*a, **k); store.update(res=r, c=a[0], bounds=k["bounds"], A_ub=k["A_ub"], b_ub=k["b_ub"]); return r
m._chips.linprog = lp
while int(obs["week"][0]) < W:
    obs, *_ = env.step(ag.act(obs))
a = ag.act(obs)
res = store["res"]; x = res.x
week = int(obs["week"][0]); H = max(1, min(ch.H, ch.T - week + 1))
S, P = len(ch.lp_slots), len(ch.pos); nF = len(ch.fabs)
pairs = [(oi, pi) for oi, o in enumerate(ch.osats) for pi in range(len(o["pairs"]))]
off_I = S * H; off_d = off_I + P * H; off_f = off_d + P * H; off_o = off_f + nF * H; off_s = off_o + len(pairs) * H
nJ = len(ch.sinks); off_m = off_s + nJ * H
hi = store["bounds"][:, 1]
print(f"week {week} H {H} obj {res.fun:.4e}")
print("FABS: starts per week t=0..H-1 (mean over window) vs cap; wafer stock")
for fi, f in enumerate(ch.fabs):
    st = x[off_f + fi * H: off_f + fi * H + H]; cap = hi[off_f + fi * H]
    print(f"  {ids[f['node']]:20s} cap {cap:8.0f} mean start {st.mean():8.0f} ({st.mean()/max(cap,1):4.0%}) first8 {np.round(st[:8]).astype(int)}  "
          f"marg(ub) {res.upper.marginals[off_f + fi*H: off_f+fi*H+H].mean():.3g}")
print("OSATS: use vs thr")
for oi, o in enumerate(ch.osats):
    qs = [q for q, (oo, _p) in enumerate(pairs) if oo == oi]
    use = sum(x[off_o + q * H: off_o + q * H + H] for q in qs)
    thr = obs["graph_now.osat.thr_eff"][o["pos"]]
    print(f"  {ids[cfg['layout']['osats'][o['pos']]]:10s} thr {thr:9.0f} mean use {use.mean():9.0f} ({use.mean()/max(thr,1):4.0%})")
print("SINKS: served vs demand (window sums)")
for j, sk in enumerate(ch.sinks):
    sv = x[off_s + j * H: off_s + j * H + H]; dm = hi[off_s + j * H: off_s + j * H + H]
    print(f"  {ids[ch.pos[sk['pos']]['node']]:9s} {com[ch.pos[sk['pos']]['k']]:9s} served {sv.sum():10.0f} demand {dm.sum():10.0f} ({sv.sum()/max(dm.sum(),1):4.0%})  t>=12: {sv[12:].sum()/max(dm[12:].sum(),1):4.0%}")
print("MATERIALS lifts (mean/wk) vs supply cap; stock end")
nM = len(ch.materials)
for mi, mpos in enumerate(ch.materials):
    lift = x[off_m + mi * H: off_m + mi * H + H]
    print(f"  {ids[ch.pos[mpos]['node']]:14s} lift {lift.mean():9.0f} hi {hi[off_m+mi*H]:9.0f} I0->end {x[off_I+mpos*H]:10.0f} {x[off_I+mpos*H+H-1]:10.0f}")
