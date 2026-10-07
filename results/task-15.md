Status: running value-of-information test (Full root 0, episodes 0-5)

Plan: measure every early-warning signal type (region/dyad units, messages, pending prohibitions) on 120 Full episodes vs ground truth from omega (base rate, AUC, lead time), then estimate the value of information on Full devpick:2,2,1,1 (remove one event class that starts during the episode from omega; ceiling = how much more mpc_buffer loses to that class than the clairvoyant plan does); build only if the ceiling > 0.17 T USD/episode.

First look (4 episodes): chokepoint warnings vs closures AUC ~0.51 (as on Small); region warnings vs any event in the region ~0.5; tariffs, sanctions and militarised closures are announced (messages) and 60-80% of threads are real.

Note (environment): in this cloud container the Full generator id is 7740c882… while the shipped cache (and the image's own joblib cache from Oct 3) is for 93b801ef… (same package sha 39ec701c95ac, same instance digest, same uv.lock; also not the Python patch version: 3.13.5 gives 7740c882 too). So "Full dev episode 3" here is a different omega (hash dd5333… vs b6ae6e… in the cache), the cached references don't apply and the dev split would have to be re-drawn (slow). The value-of-information test therefore uses Full root 0 episodes 0-5 (harm level not computed), with naive and clairvoyant computed in the script.
