"""The numba port boundary: bit-identical kernels of the generator's keyed draws (M4, stream "conformance").

Design §4.1 (27); Q95.

Q95 (the owner's call on the compiled stack): numba speeds up the generator's keyed draws with bit-identical ports of
the seed, bit-generator and normal paths, checked against the pins, numba and numpy pinned together (numba 0.67.0 with
numpy 2.4.5; ``pyproject.toml``). The ports copy NumPy's internals, so they are re-checked on every bump of either:

- ``seed_words``: ``SeedSequence(words).generate_state(n64, uint64)`` for the flat uint32 entropy of
  ``omega.seeds.keyed_sequence`` (the words [E_split's 4 words, n, stream, *key]): NumPy's ``mix_entropy`` into a pool
  of 4 words and ``generate_state`` (``numpy/random/bit_generator.pyx``), in uint32 arithmetic carried in uint64 and
  masked;
- ``pcg64dxsm_state`` and ``next64``: the state of ``PCG64DXSM(SeedSequence(words))`` (``pcg64_set_seed``: two steps of
  the 128-bit LCG with the default multiplier) and its raw 64-bit outputs (``pcg_cm_random_r``: the DXSM output of the
  pre-step state, then the step with the cheap 64-bit multiplier), 128-bit products in two uint64 halves;
- ``standard_normal``: NumPy's ziggurat (``random_standard_normal`` of ``distributions.c``, both rejection branches),
  its tables shipped as package data with NumPy's BSD-3 attribution (``omega._ziggurat``; never imported from numba's
  private modules); the wedge test ``(f[i-1] - f[i]) u + f[i] < exp(-x^2/2)`` fused by the ``llvm.fma`` intrinsic on
  darwin-arm64, where the numpy 2.4.5 wheel fuses it (``fmadd`` in ``_random_standard_normal`` of
  ``numpy/random/_generator.cpython-313-darwin.so``, ``otool -tV``), and unfused elsewhere (``FUSED_WEDGE``);
- ``latent_normals``: stream 13's (U, ncol) block of one ``standard_normal()`` per key (unit, j, which), the loop of
  ``disruption.regime._latent_normals``.

Wiring (the stream's, in ``omega.seeds`` and ``disruption.regime`` only): ``seeds.KERNELS`` (default ``True``) routes
``KeyedStream.uniforms``/``uniform`` (``stream_words``) and ``regime._latent_normals`` (``latent_block``) through these
kernels; ``keyed_sequence`` stays the reference path and the seam that ``tests/_helpers.keys_seen`` and the V2 draw
audit watch, so those two set ``seeds.KERNELS`` False; stream 22's spawned ``seed_sequence`` and
``regime._chain_uniforms`` are not ported. ``seeds`` and ``regime`` import this module lazily, on the first routed
draw, and numba is imported only inside the kernel builder (``kernels``) that the first routed draw calls: never at
module level, guarded or not, so importing ``dynamics.env`` loads no numba (``tests/test_m4_interfaces.py``) and the
package's evidence commands need not install it (``tests/test_m2_v12.py``). The kernels are plain Python functions
here, jitted by the builder (``numba.njit(cache=True)``) and bound to the module names the other kernels call, so they
are cached like module-level functions. After compiling, the builder checks them against NumPy on a fixed set of keys
(``SELF_CHECK_KEYS``, including keys that reach the ziggurat's tail and wedge) and on the first ``SELF_CHECK_NORMALS``
normals of one stream (``SELF_CHECK_STREAM``), which read every entry of the ziggurat's tables; without numba, or if
the check fails, it logs one WARNONCE (loguru's level when registered, else ``warnings.warn``) and the reference path
stays (``AVAILABLE`` False). The JIT cache lives outside the repository (``NUMBA_CACHE_DIR``, set for pytest in
``pyproject.toml`` and listed in ``.env.example``, else ``DEFAULT_CACHE_DIR``), never under ``src/``, in the
subdirectory ``cache_dir()`` named after the tables' digest (``TABLES_DIGEST``): numba keys a cached function by its
own file's stamp and compiles the tables in as constants, so an edit of ``omega._ziggurat`` alone would otherwise keep
serving the old tables (red-team M4 DET-M4-3). Pins are per machine (Q94): kernel-versus-reference equality is checked
on every platform, the pins on the Mac that recorded them.
"""

import hashlib
import importlib.util
import math
import os
import platform
import sys
import threading
import warnings
from pathlib import Path

import numpy as np

from sbfv.omega import _ziggurat as Z


STREAM = "conformance"
NUMBA_IMPORTABLE = importlib.util.find_spec("numba") is not None
AVAILABLE = False  # True once the kernels are built and pass their self-check against NumPy (``kernels``)
CACHE_DIR_VAR = "NUMBA_CACHE_DIR"  # numba's cache directory: outside the repository (pytest-env, .env.example)
DEFAULT_CACHE_DIR = Path.home() / ".cache" / "shockbench-flow" / "numba"  # when NUMBA_CACHE_DIR is unset
# the numpy 2.4.5 darwin-arm64 wheel contracts the wedge test into one fmadd (clang's default fp-contract on arm64);
# the x86-64 wheels (no FMA in their baseline) do not
FUSED_WEDGE = sys.platform == "darwin" and platform.machine() == "arm64"
# keys (unit, j, which) of stream 13 on E_split 0 and n 0 whose normal takes the ziggurat's rare branches, found
# offline from NumPy's raw outputs: the wedge accepted, the wedge rejected (a second draw), the tail (idx 0) accepted at
# once, and the tail rejected twice before it accepts
BRANCH_KEYS = {"wedge": (0, 17, 0), "wedge_reject": (0, 214, 0), "tail": (0, 4210, 0), "tail_reject": (1, 1826, 0)}
# (stream, key) of the builder's self-check, on E_split 0 and n 0 and on E_split 2**128 - 1 and n 1: the first keys
# of stream 13 and the branch keys
SELF_CHECK_KEYS = tuple((13, (x, j, w)) for x in range(2) for j in range(4) for w in (0, 1)) + tuple(
    (13, key) for key in BRANCH_KEYS.values()
)
# (stream, key) on E_split 0 and n 0 of the builder's stream check: its first SELF_CHECK_NORMALS normals, found offline
# from NumPy's raw outputs (and counted by tests/test_m4_conformance.py), accept at once at every ziggurat index but 1
# (KI[1] = 0: idx 1 always takes the wedge), take the wedge test at every index 1..255 and the tail accepted and
# rejected, so they read every entry of KI, WI and FI and both tail constants; a table edit that moves a draw, or the
# raw outputs a draw consumes, moves every later normal of the stream (the per-key normals above read 34 of 256
# indices; red-team M4 DET-M4-3). Coverage is complete at 248,856 normals
SELF_CHECK_STREAM = (13, (2, 0, 0))
SELF_CHECK_NORMALS = 250_000

# ----- constants (uint64 so numba types every operation as unsigned) -------------------------------------------------
_M32 = np.uint64(0xFFFFFFFF)
_S16 = np.uint64(16)
_S32 = np.uint64(32)
_S48 = np.uint64(48)
_S11 = np.uint64(11)
_S8 = np.uint64(8)
_S1 = np.uint64(1)
_ONE = np.uint64(1)
_ZERO = np.uint64(0)
_INIT_A = np.uint64(0x43B0D7E5)
_MULT_A = np.uint64(0x931E8875)
_INIT_B = np.uint64(0x8B51F9DD)
_MULT_B = np.uint64(0x58F38DED)
_MIX_L = np.uint64(0xCA01F9DD)
_MIX_R = np.uint64(0x4973F715)
_POOL = 4
_MUL_HI = np.uint64(2549297995355413924)  # PCG_DEFAULT_MULTIPLIER_HIGH
_MUL_LO = np.uint64(4865540595714422341)  # PCG_DEFAULT_MULTIPLIER_LOW
_CHEAP = np.uint64(0xDA942042E4DD58B5)  # PCG_CHEAP_MULTIPLIER_128
_B255 = np.uint64(0xFF)
_M52 = np.uint64(0x000FFFFFFFFFFFFF)
_TO_DOUBLE = 1.0 / 9007199254740992.0
_KI = np.array(Z.KI_DOUBLE, dtype=np.uint64)
_WI = np.array(Z.WI_DOUBLE, dtype=np.float64)
_FI = np.array(Z.FI_DOUBLE, dtype=np.float64)
_NOR_R = Z.ZIGGURAT_NOR_R
_NOR_INV_R = Z.ZIGGURAT_NOR_INV_R
# SHA-256 of the constants the jitted kernels compile in from ``omega._ziggurat``. numba keys a cached function by the
# stamp of its own file (this one) alone and freezes global arrays into the compiled code, so an edit of the tables
# would keep serving the old ones from the cache: the builder keys the cache directory by this digest (``cache_dir``)
TABLES_DIGEST = hashlib.sha256(
    b"".join(a.tobytes() for a in (_KI, _WI, _FI, np.array([_NOR_R, _NOR_INV_R], dtype=np.float64)))
).hexdigest()


# ----- the kernels as plain Python (jitted by ``kernels``; module names rebound to the jitted functions) ----------
def _hashmix(value, hash_const):
    """NumPy's ``hashmix``: (mixed value, next hash constant), uint32 arithmetic in uint64 masked to 32 bits."""
    value = (value ^ hash_const) & _M32
    hash_const = (hash_const * _MULT_A) & _M32
    value = (value * hash_const) & _M32
    value ^= value >> _S16
    return value, hash_const


def _mix(x, y):
    """NumPy's ``mix``: (MIX_MULT_L x - MIX_MULT_R y) mod 2^32, xor-shifted."""
    result = (_MIX_L * x - _MIX_R * y) & _M32
    return result ^ (result >> _S16)


def _pool(words):
    """NumPy's ``mix_entropy`` of the uint32 ``words`` (no spawn key) into a pool of 4 words (uint64 holding uint32)."""
    mixer = np.zeros(_POOL, dtype=np.uint64)
    hc = _INIT_A
    n = words.shape[0]
    for i in range(_POOL):
        v = np.uint64(words[i]) if i < n else _ZERO
        mixer[i], hc = _hashmix(v, hc)
    for i_src in range(_POOL):
        for i_dst in range(_POOL):
            if i_src != i_dst:
                h, hc = _hashmix(mixer[i_src], hc)
                mixer[i_dst] = _mix(mixer[i_dst], h)
    for i_src in range(_POOL, n):
        for i_dst in range(_POOL):
            h, hc = _hashmix(np.uint64(words[i_src]), hc)
            mixer[i_dst] = _mix(mixer[i_dst], h)
    return mixer


def _seed_words(words, n64, out):
    """``SeedSequence(words).generate_state(n64, uint64)`` into ``out``: uint32 pairs read little-endian (lo, hi)."""
    pool = _pool(words)
    hc = _INIT_B
    for i in range(2 * n64):
        v = (pool[i % _POOL] ^ hc) & _M32
        hc = (hc * _MULT_B) & _M32
        v = (v * hc) & _M32
        v ^= v >> _S16
        if i % 2 == 0:
            out[i // 2] = v
        else:
            out[i // 2] |= v << _S32


def _mul64(a, b):
    """The 128-bit product of two uint64 values as (high, low) halves, from 32-bit limbs."""
    a0, a1 = a & _M32, a >> _S32
    b0, b1 = b & _M32, b >> _S32
    p00, p01, p10, p11 = a0 * b0, a0 * b1, a1 * b0, a1 * b1
    mid = (p00 >> _S32) + (p01 & _M32) + (p10 & _M32)
    return p11 + (p01 >> _S32) + (p10 >> _S32) + (mid >> _S32), (p00 & _M32) | (mid << _S32)


def _step(state, mhi, mlo):
    """One LCG step in place: state = state (mhi, mlo) + inc mod 2^128 (``state``: hi, lo, inc hi, inc lo)."""
    hi, lo = state[0], state[1]
    p_hi, p_lo = _mul64(lo, mlo)
    p_hi = p_hi + hi * mlo + lo * mhi
    new_lo = p_lo + state[3]
    carry = _ONE if new_lo < p_lo else _ZERO
    state[0] = p_hi + state[2] + carry
    state[1] = new_lo


def _pcg64dxsm_state(words):
    """(4,) uint64: state hi, lo, increment hi, lo of ``PCG64DXSM(SeedSequence(words))`` (``pcg64_set_seed``)."""
    seed = np.zeros(4, dtype=np.uint64)
    _seed_words(words, 4, seed)
    state = np.zeros(4, dtype=np.uint64)
    state[2] = (seed[2] << _S1) | (seed[3] >> np.uint64(63))  # inc = (initseq << 1) | 1, initseq = (seed[2], seed[3])
    state[3] = (seed[3] << _S1) | _ONE
    _step(state, _MUL_HI, _MUL_LO)  # state 0, one step
    lo = state[1] + seed[1]  # state += initstate
    carry = _ONE if lo < state[1] else _ZERO
    state[0] = state[0] + seed[0] + carry
    state[1] = lo
    _step(state, _MUL_HI, _MUL_LO)
    return state


def _next64(state):
    """PCG64DXSM's next raw output (``pcg_cm_random_r``): DXSM of the current state, then the cheap-multiplier step."""
    hi, lo = state[0], state[1] | _ONE
    hi ^= hi >> _S32
    hi *= _CHEAP
    hi ^= hi >> _S48
    hi *= lo
    _step(state, _ZERO, _CHEAP)
    return hi


def _next_double(state):
    return np.float64(_next64(state) >> _S11) * _TO_DOUBLE


def _wedge(a, b, c):
    """The wedge test's a b + c, unfused (x86-64); rebound to the fused intrinsic on darwin-arm64 by the builder."""
    return a * b + c


_PY_WEDGE = _wedge


def _standard_normal(state):
    """NumPy's ``random_standard_normal`` on the PCG64DXSM ``state``: the ziggurat with both rejection branches."""
    while True:
        r = _next64(state)
        idx = np.int64(r & _B255)
        r >>= _S8
        sign = r & _ONE
        rabs = (r >> _S1) & _M52
        x = np.float64(rabs) * _WI[idx]
        if sign == _ONE:
            x = -x
        if rabs < _KI[idx]:
            return x
        if idx == 0:
            while True:
                xx = -_NOR_INV_R * math.log1p(-_next_double(state))
                yy = -math.log1p(-_next_double(state))
                if yy + yy > xx * xx:
                    if ((rabs >> _S8) & _ONE) == _ONE:
                        return -(_NOR_R + xx)
                    return _NOR_R + xx
        else:
            if _wedge(_FI[idx - 1] - _FI[idx], _next_double(state), _FI[idx]) < math.exp(-0.5 * x * x):
                return x


def _stream_words(words, n):
    """(n,) uint64 ``generate_state`` words of the flat keyed entropy ``words`` (``KeyedStream.uniforms``)."""
    out = np.zeros(n, dtype=np.uint64)
    _seed_words(words, n, out)
    return out


def _normals(state, out):
    """``out.shape[0]`` successive normals of the PCG64DXSM ``state``: ``Generator.standard_normal(n)``, bit for bit."""
    for i in range(out.shape[0]):
        out[i] = _standard_normal(state)


def _latent_normals(head, stream, n_units, ncol, which):
    """(n_units, ncol) first normals of the keys (unit, j, which) on ``stream`` under the 5 ``head`` words."""
    out = np.empty((n_units, ncol), dtype=np.float64)
    words = np.zeros(9, dtype=np.uint32)
    for i in range(5):
        words[i] = head[i]
    words[5] = stream
    words[8] = which
    for x in range(n_units):
        words[6] = x
        for j in range(ncol):
            words[7] = j
            state = _pcg64dxsm_state(words)
            out[x, j] = _standard_normal(state)
    return out


_KERNEL_NAMES = (  # jitted in this order; each module name is rebound to its jitted function
    "_hashmix",
    "_mix",
    "_pool",
    "_seed_words",
    "_mul64",
    "_step",
    "_pcg64dxsm_state",
    "_next64",
    "_next_double",
    "_standard_normal",
    "_normals",
    "_stream_words",
    "_latent_normals",
)
_PY = {name: globals()[name] for name in _KERNEL_NAMES}  # the plain-Python originals (reference for tests)
_LOCK = threading.Lock()
_STATE: dict[str, object] = {}  # "built": True, or "failed": reason


def _warn_once(message: str) -> None:
    """One WARNONCE: loguru's custom level when the helper registered it, else a ``warnings.warn``."""
    try:
        from loguru import logger

        logger.log("WARNONCE", message)
    except Exception:  # noqa: BLE001 - loguru missing or the level not registered: the standard library's warning
        warnings.warn(message, RuntimeWarning, stacklevel=3)


def _fused_intrinsic():
    """``llvm.fma.f64`` as a numba intrinsic: a b + c rounded once (the darwin-arm64 wheel's fmadd)."""
    from llvmlite import ir
    from numba.core import cgutils, types
    from numba.extending import intrinsic

    @intrinsic
    def fma(typingctx, a, b, c):
        sig = types.float64(types.float64, types.float64, types.float64)

        def codegen(context, builder, signature, args):
            dbl = ir.DoubleType()
            fn = cgutils.get_or_insert_function(builder.module, ir.FunctionType(dbl, [dbl, dbl, dbl]), "llvm.fma.f64")
            return builder.call(fn, args)

        return sig, codegen

    return fma


def cache_dir(base: str | os.PathLike | None = None) -> Path:
    """The kernels' JIT cache directory: ``ziggurat-<first 16 hex of TABLES_DIGEST>`` under ``base``.

    ``base`` is numba's cache directory (``NUMBA_CACHE_DIR``), else ``DEFAULT_CACHE_DIR``. Keyed by the tables'
    digest, so code compiled with other tables is never loaded (red-team M4 DET-M4-3).
    """
    root = Path(base) if base else Path(os.environ.get(CACHE_DIR_VAR) or DEFAULT_CACHE_DIR)
    return root / f"ziggurat-{TABLES_DIGEST[:16]}"


def _self_check() -> str | None:
    """None if the kernels equal NumPy on ``SELF_CHECK_KEYS`` and ``SELF_CHECK_STREAM``, else the reason.

    Per key and root: the seed words, the PCG64DXSM state and the first normal; then the first ``SELF_CHECK_NORMALS``
    normals of one stream, bit for bit (they read every entry of the ziggurat's tables).
    """
    for entropy, episode in ((0, 0), ((1 << 128) - 1, 1)):
        head = tuple((entropy >> (32 * i)) & 0xFFFFFFFF for i in range(4)) + (episode,)
        for stream, key in SELF_CHECK_KEYS:
            words = np.array((*head, stream, *key), dtype=np.uint32)
            ss = np.random.SeedSequence(words)
            if not np.array_equal(_stream_words(words, 3), ss.generate_state(3, np.uint64)):
                return f"seed words differ at {key}"
            bg = np.random.PCG64DXSM(ss)
            st = _pcg64dxsm_state(words)
            ref = bg.state["state"]
            if (int(st[0]) << 64 | int(st[1]), int(st[2]) << 64 | int(st[3])) != (ref["state"], ref["inc"]):
                return f"PCG64DXSM state differs at {key}"
            if _standard_normal(st) != np.random.Generator(bg).standard_normal():
                return f"standard normal differs at {key}"
    words = self_check_words()
    got = np.empty(SELF_CHECK_NORMALS, dtype=np.float64)
    _normals(_pcg64dxsm_state(words), got)
    want = np.random.Generator(np.random.PCG64DXSM(np.random.SeedSequence(words))).standard_normal(SELF_CHECK_NORMALS)
    bad = np.flatnonzero(got.view(np.uint64) != want.view(np.uint64))
    if bad.size:
        return f"standard normals differ on the self-check stream from draw {int(bad[0])}"
    return None


def self_check_words() -> np.ndarray:
    """The flat uint32 entropy words of ``SELF_CHECK_STREAM`` on E_split 0 and n 0."""
    stream, key = SELF_CHECK_STREAM
    return np.array((0, 0, 0, 0, 0, stream, *key), dtype=np.uint32)


def kernels() -> bool:
    """Build the kernels once per process (numba imported here only); True when they are in use (``AVAILABLE``).

    Thread-safe; a failed build (numba missing, a compile error, a self-check mismatch) is remembered, logged once and
    leaves the reference path in place.
    """
    global AVAILABLE
    if _STATE:
        return AVAILABLE
    with _LOCK:
        if _STATE:
            return AVAILABLE
        try:
            import numba
            from numba.core import config

            # numba fixes a function's cache path when it is decorated: the tables' own directory under
            # NUMBA_CACHE_DIR (else DEFAULT_CACHE_DIR, never numba's __pycache__ beside src/), numba's setting restored
            previous = config.CACHE_DIR
            config.CACHE_DIR = str(cache_dir(previous or None))
            try:
                g = globals()
                jit = numba.njit(cache=True, nogil=True)
                if FUSED_WEDGE:
                    g["_wedge"] = _fused_intrinsic()
                else:
                    g["_wedge"] = jit(_PY_WEDGE)
                for name in _KERNEL_NAMES:
                    g[name] = jit(_PY[name])
            finally:
                config.CACHE_DIR = previous
            reason = _self_check()
        except Exception as err:  # noqa: BLE001 - numba missing or a compile error: the reference path stays
            reason = f"{type(err).__name__}: {err}"
        if reason is None:
            AVAILABLE = True
            _STATE["built"] = True
        else:
            g = globals()
            g.update(_PY)
            g["_wedge"] = _PY_WEDGE
            _STATE["failed"] = reason
            _warn_once(f"omega._kernels: numba kernels unavailable ({reason}); keyed draws take NumPy's path (Q95)")
    return AVAILABLE


def _require() -> None:
    if not kernels():
        raise RuntimeError(f"omega._kernels: the numba kernels are unavailable ({_STATE.get('failed')})")


# ----- public entry points (the jitted kernels; RuntimeError when numba is unavailable) ----------------------------
def seed_words(words: np.ndarray, n64: int, out: np.ndarray) -> None:
    """Fill ``out`` (uint64, n64) with ``SeedSequence(words).generate_state(n64, np.uint64)`` (``words`` uint32)."""
    _require()
    _seed_words(np.ascontiguousarray(words, dtype=np.uint32), int(n64), out)


def pcg64dxsm_state(words: np.ndarray) -> np.ndarray:
    """The (4,) uint64 state (state hi/lo, increment hi/lo) of ``PCG64DXSM(SeedSequence(words))``."""
    _require()
    return _pcg64dxsm_state(np.ascontiguousarray(words, dtype=np.uint32))


def next64(state: np.ndarray) -> int:
    """Advance ``state`` in place and return PCG64DXSM's next raw 64-bit output (``random_raw``)."""
    _require()
    return int(_next64(state))


def standard_normal(state: np.ndarray) -> float:
    """NumPy's ``Generator.standard_normal()`` on the PCG64DXSM ``state`` (advanced in place), bit for bit."""
    _require()
    return float(_standard_normal(state))


def latent_normals(head: np.ndarray, stream: int, n_units: int, ncol: int, which: int) -> np.ndarray:
    """(n_units, ncol) standard normals of key (unit, j, which) on ``stream`` under the flat ``head`` words.

    Equal bit for bit to ``regime._latent_normals`` of the same stream (``head`` = E_split's 4 words and n).
    """
    _require()
    return _latent_normals(
        np.ascontiguousarray(head, dtype=np.uint32), int(stream), int(n_units), int(ncol), int(which)
    )


# ----- the routed draws of ``omega.seeds`` and ``disruption.regime`` (None: take the reference path) ---------------
def stream_words(head: tuple[int, ...], stream: int, key, n: int) -> np.ndarray | None:
    """(n,) uint64 ``generate_state`` words of the key (27) (``KeyedStream.uniforms``), or None without the kernels."""
    if not kernels():
        return None
    return _stream_words(np.array((*head, stream, *key), dtype=np.uint32), n)


def latent_block(head: tuple[int, ...], stream: int, n_units: int, ncol: int, which: int) -> np.ndarray | None:
    """``latent_normals`` for ``regime._latent_normals``, or None without the kernels."""
    if not kernels():
        return None
    return _latent_normals(np.array(head, dtype=np.uint32), stream, n_units, ncol, which)
