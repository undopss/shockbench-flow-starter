"""The policy container's entry point: warm imports, then the agent kit's shim, which signals the ready line (Q102).

Standard library only, and importing nothing of ``sbfv``: the image copies this one file to
``/opt/sbf/launch.py`` (``shockbench_flow_agent/policy_image/Dockerfile``), and a local run starts it by path
(``hosting.docker.LocalShimTransport``). Usage: ``python launch.py [SUBMISSION_DIR]`` (default ``/submission``), with
the environment variables

- ``SBF_SHIM_MODULE``: the kit's shim, a module that speaks the §9.2 wire on stdin and stdout when run as
  ``python -m <module> <submission_dir>``;
- ``SBF_KIT_PATH`` (optional): directories put first on ``sys.path``, ``os.pathsep``-separated (the image's
  ``/opt/sbf/lib``; interpreters started with ``-I`` ignore ``PYTHONPATH``).

It imports NumPy and the shim's package (the shim itself when it is a package, as the kit's ``shockbench_flow_agent``
is: ``python -m`` of a package runs its ``__main__`` after importing it, so the kit's imports happen here), registers
the module ``READY_HOOK`` whose ``ready()`` writes ``READY_LINE`` once on a private copy of stdout, then runs the shim
as ``__main__`` exactly as ``python -m`` would (``runpy.run_module(..., alter_sys=True)``, ``sys.argv`` = [module,
submission]).

The shim calls ``sys.modules[READY_HOOK].ready()`` once it has imported the submission's ``agent.py`` and done its
own first-use work (``shockbench_flow_agent.shim.warm_up``), and before it reads the Reset
(``shockbench_flow_agent.shim.serve_submission``). The ready line tells the trusted side that the container, the
interpreter, the kit (warmed) and the submission's module are up, so that all of that is charged to the start-up
budget and to no week, a metered one included (Q113; ``hosting.docker.ReadyTransport``), as M3's rule charges a
child's imports and unpickling to its start-up. Without it, ``docker run -i``'s client, which reads the Reset from
the pipe at once, would let the import of ``agent.py`` count against week 1 in a container and against the start-up
budget in a local child. The ready line is a transport-level line that the runner consumes before the wire starts,
never a Reply. A submission that fails to import never signals: the shim exits (status 2), and the runner sees a
closed channel at start-up. Exit status 3: the shim module is not found or does not import.
"""

import importlib
import importlib.util
import os
import runpy
import sys
import types


READY_LINE = b'{"type":"ready","sbf_launcher":1}\n'  # never a valid Reply: it has no episode, nonce or action
READY_HOOK = "sbf_ready"  # the module the kit's shim calls ``ready()`` on (its own READY_HOOK, kept equal by a test)
DEFAULT_SUBMISSION = "/submission"


class _Ready:
    """``ready()``: write ``READY_LINE`` on the descriptor ``fd`` (a copy of stdout) once, then close it."""

    def __init__(self, fd: int) -> None:
        self.fd: int | None = fd

    def __call__(self) -> None:
        if self.fd is None:
            return
        fd, self.fd = self.fd, None
        try:
            view = memoryview(READY_LINE)
            while view:
                view = view[os.write(fd, view) :]
        finally:
            os.close(fd)


def main(argv: list[str]) -> int:
    """Run the shim named by ``SBF_SHIM_MODULE`` on the submission directory ``argv[1]`` (module docstring)."""
    for entry in reversed([p for p in os.environ.get("SBF_KIT_PATH", "").split(os.pathsep) if p]):
        if entry not in sys.path:
            sys.path.insert(0, entry)
    shim = os.environ.get("SBF_SHIM_MODULE", "")
    submission = argv[1] if len(argv) > 1 else DEFAULT_SUBMISSION
    import numpy  # noqa: F401 - warm: its import counts against the start-up budget, not week 1

    try:
        package = shim.rpartition(".")[0]
        if package:
            importlib.import_module(package)
        spec = importlib.util.find_spec(shim) if shim else None
        if spec is not None and spec.submodule_search_locations is not None:
            importlib.import_module(shim)  # a package: warm its imports (module docstring)
        found = spec is not None
    except ImportError:
        found = False
    if not found:
        sys.stderr.write(f"launch: shim module {shim!r} not found (SBF_SHIM_MODULE, SBF_KIT_PATH)\n")
        return 3
    sys.stdout.flush()
    hook = types.ModuleType(READY_HOOK, "The launcher's ready signal (hosting/launch.py).")
    hook.ready = _Ready(os.dup(1))  # the shim moves fd 1 aside; this copy stays the wire's stdout
    sys.modules[READY_HOOK] = hook
    sys.argv = [shim, submission]
    runpy.run_module(shim, run_name="__main__", alter_sys=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
