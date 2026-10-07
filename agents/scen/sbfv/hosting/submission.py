"""The submission loader and validator, one for the scoring server and the agent kit.

Stdlib only. The server checks and unpacks every submission with it, and the agent kit re-exports it
(``shockbench_flow_agent.submission``) so a participant's local check is the server's.

A submission is a zip holding ``agent.py`` at its root, which defines ``class Agent`` with ``__init__(self,
config=None)`` and ``act(self, observation)``, with any weights beside it. The server never imports participant
code: ``check_zip`` reads the archive's directory and ``agent.py``'s syntax tree
(``ast.parse``, which executes nothing), and ``extract_submission`` writes the files for the policy container to
mount read-only (files 0o644 and directories 0o755 whatever the umask, so the container's uid 65534 reads them and
nobody but the runner's user writes them).

Refused (``SubmissionError.code``):

- ``not_zip`` (not a readable zip), ``zip_too_large`` (the archive over ``max_zip_bytes``);
- ``too_many_files`` (entries over ``max_files``), ``too_large`` (declared or actual uncompressed bytes over
  ``max_total_bytes`` or one file over ``max_file_bytes``), ``ratio`` (a member whose compression ratio exceeds
  ``max_ratio``: a zip bomb), ``size_mismatch`` (a member whose content is longer than its header says);
- ``unsafe_path``: an absolute path, a drive letter, a ``..`` or ``.`` component, a backslash, an empty component,
  a control character, or a name or component over the length limits; ``duplicate``: two members whose names are
  equal ignoring case (a case-insensitive file system would merge them), a file shadowing a directory included;
- ``symlink`` (a member whose Unix mode is a symbolic link), ``special_file`` (a device, FIFO or socket),
  ``encrypted`` (an encrypted member);
- ``no_agent`` (no ``agent.py`` at the root; the message says so when it sits one folder down: zip the folder's
  contents, not the folder), ``agent_not_utf8``, ``agent_syntax`` (``agent.py`` does not parse), ``no_agent_class``
  (no top-level ``Agent`` bound by a class, an assignment or an import), ``no_act`` (a ``class Agent`` without bases
  whose body defines no ``act``).

The limits (``SubmissionLimits()``) are the server's (``shockbench_flow_agent.LIMITS.submission``): 500 MiB unpacked
in all and per file, at most 1,000 files, and an archive no larger than those files stored with their headers
(``max_zip_bytes``). ``max_ratio`` is the local check's guard against a zip bomb: the server checks the canonical zip
it builds from the unpacked folder, which is stored (a ratio of 1).

``agent_warnings`` is a participant's aid, never a refusal: from the same syntax tree it names mistakes that pass the
check but hand every week to the naive rule (an ``__init__`` or ``act`` that cannot take its argument, an observation
indexed by an integer, an import of a package the scoring container lacks: it holds Python 3.13's standard library,
numpy, SciPy and torch (CPU) for participant code, ``IMAGE_PACKAGES``); the kit's
``python -m shockbench_flow_agent.submission`` prints them.
"""

# Sources: the submission format and the agent interface are the owner's (docs/decisions.md Q102); the size limits are
# Q113's (reading 5: "500 MB" read as MiB) and Q117's; the image's packages Q112 (torch) and Q113 (SciPy).

import ast
import hashlib
import os
import shutil
import stat
import sys
import unicodedata
import zipfile
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from sbfv.hosting.limits import (  # noqa: F401 - re-exported: the validator's names since 0.1.0
    MAX_NAME,
    MAX_SUBMISSION_BYTES,
    MAX_SUBMISSION_FILES,
    ZIP_END,
    ZIP_OVERHEAD,
    SubmissionLimits,
    stored_zip_bytes,
)


AGENT_FILE, AGENT_CLASS = "agent.py", "Agent"
CHUNK = 1 << 20  # bytes per read while extracting (a buffer size, not a model value)
MAX_COMPONENT = 255  # characters of one path component (the common file-system limit)
RATIO_FLOOR = 1 << 20  # a member this small (uncompressed bytes) is never refused for its ratio
# the third-party packages the policy container guarantees participant code (shockbench_flow_agent/policy_image; Q112
# torch, Q113 SciPy)
IMAGE_PACKAGES = ("numpy", "scipy", "torch")
_IMPORT_ERRORS = ("ImportError", "ModuleNotFoundError", "Exception", "BaseException")  # a guarded, optional import


# what to do about each refusal (module docstring; the kit's check prints the line of the code it refuses on)
REFUSAL_FIXES = {
    "not_zip": "build the zip with the kit (build_submission) or any zip tool; the file is not a readable zip",
    "zip_too_large": "make the archive smaller (smaller weights, or leave out files agent.py does not read)",
    "too_many_files": "zip fewer files: agent.py and the weights it reads",
    "too_large": "make the unpacked files smaller: the total, and each file, have a limit",
    "ratio": "a member compresses far better than real weights do (a zip bomb): store what agent.py reads as is",
    "size_mismatch": "rebuild the zip: a member holds more bytes than its header says",
    "unsafe_path": "use plain relative names: no absolute path, '..', '.', backslash, control character, long name",
    "duplicate": "rename one of two members whose names are equal ignoring case (or a file named as a directory)",
    "symlink": "replace the symbolic link by the file itself",
    "special_file": "zip regular files and directories only (no device, FIFO or socket)",
    "encrypted": "zip without a password",
    "no_agent": "put agent.py (with class Agent) at the root of the zip: zip the folder's contents, not the folder",
    "agent_not_utf8": "save agent.py as UTF-8",
    "agent_syntax": "fix the syntax error in agent.py (python -m py_compile agent.py shows it)",
    "no_agent_class": "define class Agent at the top level of agent.py (or import or assign it there)",
    "no_act": "give class Agent a method act(self, observation)",
}


class SubmissionError(ValueError):
    """A refused submission; ``code`` names the rule (module docstring), the message says what to fix."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


@dataclass(frozen=True)
class Submission:
    """A checked submission: the archive's SHA-256 and size, its files (names, sizes) and, once extracted, its root.

    The SHA-256 is of the zip's bytes: the scorer stores it and it salts the policy seed.
    """

    sha256: str
    files: tuple[tuple[str, int], ...]  # (member name, uncompressed bytes), directories left out, archive order
    total_bytes: int
    zip_bytes: int = 0  # the archive's size in bytes
    root: Path | None = None  # the extraction directory (``extract_submission``), else None


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(CHUNK):
            h.update(chunk)
    return h.hexdigest()


def _check_name(name: str) -> PurePosixPath:
    """The member name as a relative POSIX path, or ``unsafe_path``."""
    bad = f"member {name!r}"
    if not name or len(name) > MAX_NAME:
        raise SubmissionError("unsafe_path", f"{bad}: an empty name or one over {MAX_NAME} characters")
    if "\\" in name:
        raise SubmissionError("unsafe_path", f"{bad}: a backslash (use '/' as the separator)")
    if any(unicodedata.category(ch) == "Cc" for ch in name):
        raise SubmissionError("unsafe_path", f"{bad}: a control character")
    if name.startswith("/") or (len(name) > 1 and name[1] == ":"):
        raise SubmissionError("unsafe_path", f"{bad}: an absolute path")
    parts = name.rstrip("/").split("/")
    for part in parts:
        if part in ("", ".", ".."):
            raise SubmissionError("unsafe_path", f"{bad}: an empty, '.' or '..' component")
        if len(part) > MAX_COMPONENT:
            raise SubmissionError("unsafe_path", f"{bad}: a component over {MAX_COMPONENT} characters")
    return PurePosixPath(*parts)


def _kind(info: zipfile.ZipInfo) -> str:
    """'dir', 'file', or the refusal code of a symlink or special file (Unix mode bits, when the archive has them)."""
    mode = info.external_attr >> 16
    fmt = stat.S_IFMT(mode)
    if fmt == stat.S_IFLNK:
        return "symlink"
    if fmt not in (0, stat.S_IFREG, stat.S_IFDIR):
        return "special_file"
    return "dir" if info.is_dir() or fmt == stat.S_IFDIR else "file"


def _members(zf: zipfile.ZipFile, limits: SubmissionLimits) -> list[tuple[zipfile.ZipInfo, PurePosixPath, str]]:
    """Every member with its checked path and kind; raises on the first refused one."""
    infos = zf.infolist()
    if len(infos) > limits.max_files:
        raise SubmissionError("too_many_files", f"{len(infos)} entries, at most {limits.max_files}")
    out, seen, dirs, total = [], {}, set(), 0
    for info in infos:
        path = _check_name(info.filename)
        kind = _kind(info)
        if kind in ("symlink", "special_file"):
            raise SubmissionError(kind, f"member {info.filename!r}: only regular files and directories are allowed")
        if info.flag_bits & 0x1:
            raise SubmissionError("encrypted", f"member {info.filename!r} is encrypted")
        key = str(path).casefold()
        if key in seen:
            raise SubmissionError(
                "duplicate", f"members {seen[key]!r} and {info.filename!r} (names equal ignoring case)"
            )
        seen[key] = info.filename
        if kind == "file":
            if info.file_size > limits.max_file_bytes:
                raise SubmissionError(
                    "too_large", f"{info.filename!r}: {info.file_size} bytes, at most {limits.max_file_bytes}"
                )
            total += info.file_size
            if info.file_size > RATIO_FLOOR and info.file_size > limits.max_ratio * max(info.compress_size, 1):
                raise SubmissionError("ratio", f"{info.filename!r}: compression ratio over {limits.max_ratio:g}")
        dirs.update(str(p).casefold() for p in path.parents if str(p) != ".")
        out.append((info, path, kind))
    if total > limits.max_total_bytes:
        raise SubmissionError("too_large", f"{total} bytes uncompressed, at most {limits.max_total_bytes}")
    for info, path, kind in out:
        if kind == "file" and str(path).casefold() in dirs:
            raise SubmissionError("duplicate", f"file {info.filename!r} is also a directory of another member")
    return out


def _check_agent(source: bytes) -> None:
    """``agent.py``'s static check: UTF-8, parses, binds a top-level ``Agent``; a base-less class defines ``act``."""
    try:
        text = source.decode("utf-8")
    except UnicodeDecodeError as err:
        raise SubmissionError("agent_not_utf8", f"{AGENT_FILE} is not UTF-8 ({err.reason})") from None
    try:
        tree = ast.parse(text, filename=AGENT_FILE)
    except (SyntaxError, ValueError, RecursionError, MemoryError) as err:
        raise SubmissionError("agent_syntax", f"{AGENT_FILE} does not parse: {err}") from None
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == AGENT_CLASS:
            methods = {n.name for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
            if not node.bases and "act" not in methods:
                raise SubmissionError(
                    "no_act", f"class {AGENT_CLASS} in {AGENT_FILE} defines no act(self, observation)"
                )
            return
        targets = []
        if isinstance(node, ast.Assign):
            targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            targets = [node.target.id]
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            targets = [a.asname or a.name.split(".")[0] for a in node.names]
        if AGENT_CLASS in targets:
            return
    raise SubmissionError("no_agent_class", f"{AGENT_FILE} binds no top-level {AGENT_CLASS} (class Agent: ...)")


def _positional(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> tuple[list[str], bool]:
    """(names of the positional parameters, whether it takes ``*args``)."""
    return [a.arg for a in (*fn.args.posonlyargs, *fn.args.args)], fn.args.vararg is not None


def _guarded(handlers: list[ast.ExceptHandler]) -> bool:
    """Whether a ``try`` catches a failed import (an optional import: ``except ImportError``, a bare ``except``)."""
    for h in handlers:
        names = h.type.elts if isinstance(h.type, ast.Tuple) else [h.type]
        if h.type is None or any(isinstance(n, ast.Name) and n.id in _IMPORT_ERRORS for n in names):
            return True
    return False


def _imported(tree: ast.AST) -> list[str]:
    """Top-level names of the absolute imports in ``tree``, in order, outside a ``try`` that catches their failure."""
    out: list[str] = []

    def visit(node: ast.AST, guarded: bool) -> None:
        if isinstance(node, ast.Import):
            out.extend(a.name.partition(".")[0] for a in node.names if not guarded)
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module and not guarded:
                out.append(node.module.partition(".")[0])
        elif isinstance(node, ast.Try | ast.TryStar):
            for child in node.body:
                visit(child, guarded or _guarded(node.handlers))
            for child in (*node.handlers, *node.orelse, *node.finalbody):
                visit(child, guarded)
            return
        for child in ast.iter_child_nodes(node):
            visit(child, guarded)

    visit(tree, False)
    return out


def _local_modules(files: Iterable[str]) -> set[str]:
    """The top-level module names a submission's own files provide: ``x.py``, and ``x/`` for any file under it."""
    out = set()
    for f in files:
        first, sep, _rest = str(f).replace("\\", "/").partition("/")
        if sep:
            out.add(first)
        elif first.endswith(".py"):
            out.add(first[:-3])
    return out


def missing_imports(source: bytes, files: Iterable[str] = ()) -> list[str]:
    """The packages ``agent.py`` imports that the scoring container lacks (module docstring), in order, once each.

    An import is fine when it names the standard library (``sys.stdlib_module_names``), one of ``IMAGE_PACKAGES``, or
    a module of the submission itself (``files``: its paths, as ``Submission.files`` lists them); relative imports and
    imports inside a ``try`` that catches ``ImportError`` are not read. Empty when ``agent.py`` does not parse.
    """
    try:
        tree = ast.parse(source.decode("utf-8"), filename=AGENT_FILE)
    except (UnicodeDecodeError, SyntaxError, ValueError, RecursionError, MemoryError):
        return []
    known = set(sys.stdlib_module_names) | set(IMAGE_PACKAGES) | _local_modules(files) | {"__future__"}
    return list(dict.fromkeys(n for n in _imported(tree) if n not in known))


def agent_warnings(source: bytes, files: Iterable[str] = ()) -> list[str]:
    """Mistakes in ``agent.py`` that pass ``check_zip`` but make ``Agent(config)`` or ``act`` fail every week.

    Read from the syntax tree (nothing is imported): an import of a package the scoring container lacks
    (``missing_imports``, with ``files`` the submission's paths so its own modules count), then, in a base-less
    top-level ``class Agent``, an ``__init__`` without a parameter for ``config``, an ``act`` without one for the
    observation, and ``observation[<int>]`` inside ``act`` (the observation is a dict keyed by strings). Empty when
    ``agent.py`` does not parse.
    """
    try:
        tree = ast.parse(source.decode("utf-8"), filename=AGENT_FILE)
    except (UnicodeDecodeError, SyntaxError, ValueError, RecursionError, MemoryError):
        return []
    out = [
        f"agent.py imports {name}, which the scoring container does not have: it holds Python 3.13's standard "
        "library, numpy, scipy and torch (CPU) only, and the submission's own modules; the import fails there and "
        "naive plays every week (score 0)"
        for name in missing_imports(source, files)
    ]
    for node in tree.body:
        if not (isinstance(node, ast.ClassDef) and node.name == AGENT_CLASS and not node.bases):
            continue
        fns = {n.name: n for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
        if "__init__" in fns:
            names, star = _positional(fns["__init__"])
            if len(names) < 2 and not star:
                out.append(
                    "Agent.__init__ takes no config: the runner calls Agent(config), which raises TypeError, so naive "
                    "plays every week (score 0); write def __init__(self, config=None)"
                )
        if "act" in fns:
            names, star = _positional(fns["act"])
            if len(names) < 2 and not star:
                out.append("act takes no observation: write def act(self, observation)")
            elif len(names) >= 2:
                obs = names[1]
                ints = sorted(
                    {
                        n.slice.value
                        for n in ast.walk(fns["act"])
                        if isinstance(n, ast.Subscript)
                        and isinstance(n.value, ast.Name)
                        and n.value.id == obs
                        and isinstance(n.slice, ast.Constant)
                        and type(n.slice.value) is int
                    }
                )
                if ints:
                    out.append(
                        f"act indexes {obs}[{ints[0]}]: the observation is a dict of numpy arrays keyed by strings "
                        f"({obs}['stock.qty'], ...), so this raises KeyError and naive plays that week"
                    )
    return out


def check_zip(zip_path: str | Path, limits: SubmissionLimits = SubmissionLimits()) -> Submission:
    """Check a submission zip without extracting it or importing anything (module docstring).

    Raises:
        SubmissionError: on the first rule the archive breaks.

    """
    path = Path(zip_path)
    try:
        size = path.stat().st_size
    except OSError as err:
        raise SubmissionError("not_zip", f"{path}: {err.strerror}") from None
    if size > limits.max_zip_bytes:
        raise SubmissionError("zip_too_large", f"{size} bytes, at most {limits.max_zip_bytes}")
    if not zipfile.is_zipfile(path):
        raise SubmissionError("not_zip", f"{path.name} is not a zip archive")
    try:
        with zipfile.ZipFile(path) as zf:
            members = _members(zf, limits)
            names = {str(p): info for info, p, kind in members if kind == "file"}
            if AGENT_FILE not in names:
                nested = sorted(n for n in names if PurePosixPath(n).name == AGENT_FILE)
                hint = f"; found {nested[0]!r}: zip the folder's contents, not the folder" if nested else ""
                raise SubmissionError("no_agent", f"no {AGENT_FILE} at the root of the zip{hint}")
            _check_agent(_read(zf, names[AGENT_FILE], limits.max_file_bytes))
    except (zipfile.BadZipFile, zipfile.LargeZipFile, NotImplementedError, EOFError) as err:
        raise SubmissionError("not_zip", f"{path.name}: {err}") from None
    files = tuple((str(p), info.file_size) for info, p, kind in members if kind == "file")
    return Submission(_sha256(path), files, sum(n for _f, n in files), size)


def _read(zf: zipfile.ZipFile, info: zipfile.ZipInfo, cap: int) -> bytes:
    """A member's content, refusing more bytes than its header declares or than ``cap``."""
    out = bytearray()
    with zf.open(info) as f:
        while chunk := f.read(CHUNK):
            out += chunk
            if len(out) > min(info.file_size, cap):
                raise SubmissionError("size_mismatch", f"{info.filename!r} holds more bytes than its header says")
    return bytes(out)


def _extract(zf: zipfile.ZipFile, root: Path, limits: SubmissionLimits) -> None:
    """Write every member under ``root`` (``extract_submission``); modes set explicitly, whatever the umask."""
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    written = 0
    os.chmod(root, 0o755)
    for info, path, kind in _members(zf, limits):
        target = root.joinpath(*path.parts)
        for parent in reversed([target, *target.parents] if kind == "dir" else list(target.parents)):
            if parent == root or not parent.is_relative_to(root):
                continue
            if not parent.exists():
                parent.mkdir()
                os.chmod(parent, 0o755)
            if parent.is_symlink() or not parent.is_dir():
                raise SubmissionError("unsafe_path", f"member {info.filename!r} leaves the extraction directory")
        if kind == "dir":
            continue
        n = 0
        fd = os.open(target, flags, 0o644)
        os.fchmod(fd, 0o644)
        with os.fdopen(fd, "wb") as out, zf.open(info) as f:
            while chunk := f.read(CHUNK):
                n += len(chunk)
                written += len(chunk)
                if n > info.file_size or written > limits.max_total_bytes:
                    raise SubmissionError("size_mismatch", f"{info.filename!r} holds more than its header says")
                out.write(chunk)


def extract_submission(
    zip_path: str | Path, dest: str | Path, limits: SubmissionLimits = SubmissionLimits()
) -> Submission:
    """Check the zip (``check_zip``) and extract it into ``dest``, a directory that must not exist or be empty.

    Files are written 0o644 and directories 0o755 (readable by the container's uid 65534), never through a symlink
    (``O_NOFOLLOW``, ``O_EXCL``), each member streamed and stopped at its declared size, the total at
    ``max_total_bytes``.

    Raises:
        SubmissionError: as ``check_zip``, or ``size_mismatch`` when a member holds more than its header declares.
        FileExistsError: if ``dest`` exists and is not an empty directory.

    """
    sub = check_zip(zip_path, limits)
    root = Path(dest)
    if root.exists() and (not root.is_dir() or any(root.iterdir())):
        raise FileExistsError(f"{root}: the extraction directory must be new or empty")
    root.mkdir(mode=0o755, parents=True, exist_ok=True)
    root = root.resolve()
    try:
        with zipfile.ZipFile(zip_path) as zf:
            _extract(zf, root, limits)
    except (zipfile.BadZipFile, EOFError, SubmissionError) as err:
        for child in root.iterdir():  # the directory was new or empty: everything in it is ours
            shutil.rmtree(child) if child.is_dir() and not child.is_symlink() else child.unlink()
        if isinstance(err, SubmissionError):
            raise
        raise SubmissionError("not_zip", f"{Path(zip_path).name}: {err}") from None
    return Submission(sub.sha256, sub.files, sub.total_bytes, sub.zip_bytes, root)


SKIPPED = ("__pycache__", ".DS_Store", ".git", ".ipynb_checkpoints", "__MACOSX")  # never packed by build_submission
APPLEDOUBLE = "._"  # macOS resource-fork companions (``._agent.py``), never packed either
ZIP_EPOCH = (1980, 1, 1, 0, 0, 0)  # the zip format's earliest timestamp: every member gets it, so builds repeat


def build_submission(
    src_dir: str | Path, zip_path: str | Path, *, exclude: tuple[str, ...] = (), compress: bool = False
) -> Path:
    """Zip the files of ``src_dir`` (``agent.py`` at the root) into ``zip_path``, byte for byte repeatable.

    Members are the regular files under ``src_dir`` in sorted relative-path order, ``/``-separated, each with the
    timestamp ``ZIP_EPOCH`` and mode 0o644; ``SKIPPED`` names, AppleDouble ``._*`` files and the relative paths in
    ``exclude`` are left out, and symlinks are refused (the validator would refuse them too). Stored by default, so
    the bytes, and the SHA-256 that salts the policy seed, follow from the files alone; ``compress=True``
    deflates (smaller weights), whose bytes may depend on the zlib build. The result is not checked: call
    ``check_zip``.

    Raises:
        SubmissionError: ``symlink`` if ``src_dir`` holds a symbolic link.

    """
    src = Path(src_dir)
    files = []
    for path in sorted(src.rglob("*")):
        rel = path.relative_to(src)
        if any(part in SKIPPED or part.startswith(APPLEDOUBLE) for part in rel.parts) or rel.as_posix() in exclude:
            continue
        if path.is_symlink():
            raise SubmissionError("symlink", f"{rel.as_posix()}: a symbolic link cannot be submitted")
        if path.is_file():
            files.append((rel.as_posix(), path))
    out = Path(zip_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    method = zipfile.ZIP_DEFLATED if compress else zipfile.ZIP_STORED
    with zipfile.ZipFile(out, "w", compression=method) as zf:
        for name, path in files:
            zi = zipfile.ZipInfo(name, date_time=ZIP_EPOCH)
            zi.create_system, zi.external_attr, zi.compress_type = 3, (stat.S_IFREG | 0o644) << 16, method
            zf.writestr(zi, path.read_bytes())
    return out
