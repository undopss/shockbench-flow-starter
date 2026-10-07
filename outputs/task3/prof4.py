import pickle, time, numpy as np
from scipy.optimize import milp, LinearConstraint, Bounds, linprog
c,A,rl,rh,ig,lo,hi=pickle.load(open("outputs/task3/tw_model.pkl","rb"))
t0=time.process_time(); r=milp(c,constraints=LinearConstraint(A,rl,rh),integrality=np.zeros_like(ig),bounds=Bounds(lo,hi)); print("LP relax", f"{time.process_time()-t0:.3f}", r.fun)
t0=time.process_time(); r=milp(c,constraints=LinearConstraint(A,rl,rh),integrality=ig,bounds=Bounds(lo,hi),options={"node_limit":1}); print("node1", f"{time.process_time()-t0:.3f}", r.status, r.fun)
import scipy; print(scipy.__version__)
print("max |A|",abs(A.data).max(),"min",abs(A.data[A.data!=0]).min(), "rhs max", np.nanmax(np.abs(np.r_[rl[np.isfinite(rl)],rh[np.isfinite(rh)]])), "hi max", hi[np.isfinite(hi)].max())
import highspy
