"""The competition layer's trusted side: submissions, the Docker transport and scoring (design §9.4; Q102).

``submission`` checks and unpacks a submission zip without importing it; ``docker`` starts one policy container per
episode with the §9.4 flags and speaks the §9.2 wire to it (``DockerTransport``), or a local child without Docker
(``LocalShimTransport``); ``split`` draws a split's scenarios from its entropy, filled into the harm strata of (44);
``trusted`` plays a submission over a split and scores it with (55)-(56). Nothing here imports participant code, and no
policy process ever receives omega, E_split or a path of the trusted side.
"""
