import sys, numpy as np, gymnasium as gym, shockbench_flow_gym
ep = int(sys.argv[1]) if len(sys.argv) > 1 else 0
env = gym.make("ShockBench/Full-v0"); obs, info = env.reset(options={"episode": ep})
st = info["static"]; E = st["edges"]; ids = [n["id"] for n in st["instance"]["nodes"]]
sel = [e for e in range(len(E["id"])) if ids[E["tail"][e]].startswith(sys.argv[2] if len(sys.argv)>2 else "fab_")]
rows = []
done = False
while not done:
    rows.append([obs["graph_now.u"][e] / E["u0"][e] for e in sel])
    obs, r, te, tr, info = env.step({"flows": np.zeros_like(obs["action_mask"], dtype=float)}); done = te or tr
R = np.array(rows)
for j, e in enumerate(sel):
    v = R[:, j]
    print(f"{E['id'][e]:45s} min {v.min():.3f} mean {v.mean():.3f} first<1 {np.argmax(v<0.99) if (v<0.99).any() else '-'} weeks<0.5 {(v<0.5).sum()}  w1 {v[0]:.3f} w52 {v[51]:.3f} w104 {v[-1]:.3f}")
