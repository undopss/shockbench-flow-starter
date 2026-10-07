"""Evaluation (design §6.3, §7, §9.5, §10; milestone M4): the episode runner, its results and timings, V24 conformance.

``runner`` fills the strata and plays every baseline with its replay (53) and oracle bound; ``results`` holds the frozen
rows and the RSS and separation tables; ``timings`` the per-step times (Q13 inputs); ``conformance`` the stored-action
records and their replay (V24); ``ladders`` the ladder checks of §2.6 and §7.4 and ``pilot`` the pilot, V15 and
(59) (M5). The seal with its MAC is M6.
"""
