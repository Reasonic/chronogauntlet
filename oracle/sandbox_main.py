"""Clean-interpreter candidate sandbox entry (audit A3-GC-ANSWERKEY fix).

This file is NOT imported as part of the `oracle` package. It is copied into a
throwaway BUNDLE directory (see oracle/isolate.py::_bundle_dir) alongside copies
of `safecodec.py` and `candidate_loader.py`, and launched as:

    python -I  <bundle>/sandbox_main.py          (cwd=<bundle>, minimal env)

It is launched as `python -E -s <bundle>/sandbox_main.py` with a minimal env, and
BEFORE any other import it strips every sys.path entry under `CG_REPO_ROOT`
(including the venv `site-packages` when the venv lives inside the repo — the one
in-memory string that otherwise reveals the repo root) and asserts none remains.
Third-party datetime libs the candidate legitimately uses (tzdata, pytz,
dateutil) are served from the bundle's self-contained `deps/` copy, not the repo.
Result: NO `oracle.*`/`tasks.*` module and no repo path is present in this
interpreter's memory or on its path, so a candidate cannot recover the answer key
by importing, by walking live objects (`gc.get_objects()`, module `__file__`), or
by re-adding a recovered path to sys.path. The only remaining route — guessing
the reference's absolute filesystem path — is documented out of scope in
THREAT_MODEL.md.

Because the answer key is unreachable, the candidate cannot forge a CORRECT
verdict even though it shares this process with the code that writes call-results
back to the trusted worker: the worker classifies each returned value against the
reference it alone holds, so a fabricated result only misreports the candidate's
own output (which a wrong candidate does anyway) and can never match an unknown
reference. The verdict sentinel and the worker's real stdout live in the separate
trusted worker process and are not inherited here.

Protocol (length-prefixed JSON) over fds named in the environment:
  CG_SRC_FD  : the candidate source (length-framed blob), read once.
  CG_REQ_FD  : worker -> sandbox   {"cmd":"call","args":[<enc>,...]} | {"cmd":"stop"}
  CG_RESP_FD : sandbox -> worker   {"loaded":bool,...} once, then per call
               {"ok":true,"value":<enc>} | {"ok":false,"kind":"raised"|"unencodable","error":str}
"""
import json
import os
import struct
import sys


def _seal():
    """Remove/deny EVERY in-memory carrier of the repo root before the candidate
    runs, so it cannot recover the answer key without a filesystem path read.

    Carriers the four prior forges + the fifth audit found: sys.path (the venv
    site-packages when the venv is in the repo), os.environ['CG_REPO_ROOT'], the
    interpreter identity (sys.prefix/executable = <repo>/.venv/...), and this
    module's own globals. The load-bearing fix is that the worker launches this
    with a Python interpreter OUTSIDE the repo (the venv's base interpreter), so
    sys.prefix/executable never point into the repo. Here we additionally pop the
    env carrier, keep the repo root ONLY as a local (discarded on return — no
    module global, un-frame-walkable), add the bundle's self-contained deps copy,
    strip any repo-derived sys.path entry, and FAIL CLOSED if the interpreter or
    any surviving path is still under the repo (a launch-with-in-repo-python
    misconfiguration -> loud error, never a silent leak)."""
    repo = os.environ.pop("CG_REPO_ROOT", "")
    bundle = os.path.dirname(os.path.abspath(__file__))
    deps = os.path.join(bundle, "deps")
    if os.path.isdir(deps) and deps not in sys.path:
        sys.path.insert(1, deps)                 # venv-pinned third-party libs, no repo
    if not repo:
        return
    def _real(p):
        try:
            return os.path.realpath(p).rstrip(os.sep) + os.sep
        except Exception:
            return ""
    rr = _real(repo)
    under = lambda p: bool(p) and _real(p).startswith(rr) if rr else False
    sys.path[:] = [p for p in sys.path if not under(p or ".")]
    # Scrub repo-derived entries from carriers the sys.path strip misses (audit):
    # os.environ['PATH'] (holds <repo>/.venv/bin under `source activate`), and any
    # sys.meta_path finder that resolves under the repo (an editable-install
    # finder — belt-and-suspenders on top of -S, which already prevents them).
    if os.environ.get("PATH"):
        os.environ["PATH"] = os.pathsep.join(
            p for p in os.environ["PATH"].split(os.pathsep) if not under(p))

    def _finder_under_repo(f):
        mod = sys.modules.get(getattr(type(f), "__module__", ""), None)
        return under(getattr(mod, "__file__", "") or "")
    sys.meta_path[:] = [f for f in sys.meta_path if not _finder_under_repo(f)]
    for probe in (sys.prefix, sys.exec_prefix, sys.executable,
                  getattr(sys, "base_prefix", ""), getattr(sys, "_base_executable", ""),
                  *sys.path):
        if under(probe):
            raise SystemExit(
                f"CG-SANDBOX-MISCONFIG: repo reachable in-memory via {probe!r}; the "
                f"candidate sandbox must be launched with a Python interpreter OUTSIDE "
                f"the repo (the venv's base interpreter).")
    # Fail closed if the answer-key packages are importable by ANY route (a
    # `pip install -e .` of this repo into the base interpreter, a surviving
    # finder, ...): refuse rather than let a candidate `import oracle.task`.
    import importlib.util
    for pkg in ("oracle", "tasks"):
        try:
            spec = importlib.util.find_spec(pkg)
        except (ImportError, ValueError, AttributeError):
            spec = None
        if spec is not None:
            raise SystemExit(f"CG-SANDBOX-MISCONFIG: answer-key package {pkg!r} is "
                             f"importable in the candidate sandbox; refusing to run.")


_seal()

import safecodec          # bundle-local copy (top-level, not oracle.safecodec)
import candidate_loader    # bundle-local copy


def _write_msg(fd, obj):
    data = json.dumps(obj).encode()
    os.write(fd, struct.pack(">I", len(data)) + data)


def _read_exact(fd, n):
    buf = b""
    while len(buf) < n:
        chunk = os.read(fd, n - len(buf))
        if not chunk:
            return b""
        buf += chunk
    return buf


def _read_msg(fd):
    hdr = _read_exact(fd, 4)
    if len(hdr) < 4:
        return None
    (n,) = struct.unpack(">I", hdr)
    body = _read_exact(fd, n)
    if len(body) < n:
        return None
    return json.loads(body.decode())


def _read_blob(fd):
    hdr = _read_exact(fd, 4)
    if len(hdr) < 4:
        return b""
    (n,) = struct.unpack(">I", hdr)
    return _read_exact(fd, n)


def main():
    os.environ["TZ"] = "UTC"
    import time
    if hasattr(time, "tzset"):
        time.tzset()
    # Pin tzdata the SAME way oracle.tzconfig does, but WITHOUT importing the repo
    # (which would re-expose the answer key): an empty tz search path makes
    # zoneinfo fall back to the importable, version-pinned `tzdata` pip package,
    # so a candidate's ZoneInfo resolves DST/offset rules from IANA 2025b exactly
    # like the reference.
    import zoneinfo
    zoneinfo.reset_tzpath(to=[])

    req_fd = int(os.environ["CG_REQ_FD"])
    resp_fd = int(os.environ["CG_RESP_FD"])
    src_fd = int(os.environ["CG_SRC_FD"])
    entry_point = os.environ["CG_ENTRY"]

    source = _read_blob(src_fd).decode("utf-8", "replace")
    os.close(src_fd)

    # Seal stdout/stderr for the candidate's whole lifetime: its prints reach
    # nothing (the worker's real stdout is in another process anyway).
    dn = os.open(os.devnull, os.O_WRONLY)
    os.dup2(dn, 1)
    os.dup2(dn, 2)

    fn, err = candidate_loader.load_candidate(source, entry_point)
    if fn is None:
        _write_msg(resp_fd, {"loaded": False, "error": err})
        return 0
    _write_msg(resp_fd, {"loaded": True})

    while True:
        req = _read_msg(req_fd)
        if req is None or req.get("cmd") == "stop":
            break
        try:
            args = tuple(safecodec.decode(a) for a in req["args"])
        except Exception as e:
            _write_msg(resp_fd, {"ok": False, "kind": "raised",
                                 "error": f"bad-args: {type(e).__name__}: {e}"})
            continue
        try:
            out = fn(*args)
        except BaseException as e:                # candidate raised (incl. SystemExit)
            _write_msg(resp_fd, {"ok": False, "kind": "raised",
                                 "error": f"{type(e).__name__}: {e}"})
            continue
        try:
            enc = safecodec.encode(out)
        except BaseException as e:                # UnsafeType / RecursionError / huge-int
            _write_msg(resp_fd, {"ok": False, "kind": "unencodable",
                                 "error": f"{type(e).__name__}: {e}"})
            continue
        _write_msg(resp_fd, {"ok": True, "value": enc})
    return 0


if __name__ == "__main__":
    sys.exit(main())
