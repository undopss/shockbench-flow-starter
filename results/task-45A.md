Status: Full root done; J reproduction done (equal with pp_scen_K 0; with K 8 J moves because policy_seed follows the code sha); gap map + sbf check running

# Task 45A — stack leaners on mpc_final, root 995215227

## 2. Full, root 995215227, 20 episodes (4 jobs)

```
full, entropy 995215227, episodes 20, baseline final
references ready in 1417 s (20 episodes)
  played final in 432 s: RSS 0.8613
  played ovf in 442 s: RSS 0.8618
  played ties4 in 430 s: RSS 0.8603
  played ovf_ties4 in 477 s: RSS 0.8611

full, entropy 995215227, 20 episodes; diff = variant - final, 90% paired interval
variant                      RSS     L1     L2     L3     L4     diff  interval               better%  fallb
final                     0.8613  0.888  0.881  0.763  0.753  +0.0000  [+0.0000, +0.0000]     nan%      0
ovf                       0.8618  0.887  0.885  0.762  0.752  +0.0005  [-0.0003, +0.0012]    85.9%      0
ties4                     0.8603  0.887  0.880  0.763  0.750  -0.0010  [-0.0020, -0.0001]     4.2%      0  <-- worse
ovf_ties4                 0.8611  0.886  0.881  0.763  0.761  -0.0002  [-0.0016, +0.0011]    41.4%      0
```
References for this new root took 1417 s. Wall per variant ~430-480 s.
