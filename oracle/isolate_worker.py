"""TRUSTED evaluator worker (M3 pre-flight audit A1 + A3 fixes).

Evaluates ONE candidate and prints its EvalResult as a sentinel-framed JSON line.
The critical property: this process NEVER executes candidate code, and holds the
answer key. It spawns the candidate in a CLEAN interpreter
(`python -E -s <bundle>/sandbox_main.py`, see oracle/isolate.py::bundle_dir) that
has neither the verdict sentinel nor any `oracle.*`/`tasks.*` module — hence no
reference / `load_tasks` — in its memory or on its path. Each candidate call is
proxied over a dedicated fd pair; the reference computation, comparison, and
outcome classification all happen HERE. Therefore the candidate can neither reach
the verdict channel (closing the frame-walk forge, audit A1) nor recover the
answer key by walking live objects (closing the gc-reachability forge, audit A3).

  echo '{"task_id":"...","source":"...","sentinel":"..."}' | python -m oracle.isolate_worker
"""
from __future__ import annotations

import json
import os
import json
import select
import struct
import subprocess
import sys
import time
from functools import lru_cache

from .run_oracle import (CANDIDATE_TIMEOUT_S, EvalResult, LOAD_ERROR,
                         evaluate_callable)

TIMEOUT_KILLED = "TIMEOUT_KILLED"   # matches oracle/isolate.py's parent-side outcome


# Length-prefixed JSON framing over the worker<->sandbox pipes (twin of the
# helpers in oracle/sandbox_main.py, which runs in the clean interpreter).
def write_msg(fd: int, obj) -> None:
    data = json.dumps(obj).encode()
    os.write(fd, struct.pack(">I", len(data)) + data)


def _read_exact(fd: int, n: int) -> bytes:
    buf = b""
    while len(buf) < n:
        chunk = os.read(fd, n - len(buf))
        if not chunk:
            return b""
        buf += chunk
    return buf


_MAX_FRAME = 64 * 1024 * 1024   # audit B-N2: reject an oversized header fast


def read_msg(fd: int):
    hdr = _read_exact(fd, 4)
    if len(hdr) < 4:
        return None
    (n,) = struct.unpack(">I", hdr)
    if n > _MAX_FRAME:              # a candidate can't make the worker read gigabytes
        return None
    body = _read_exact(fd, n)
    if len(body) < n:
        return None
    return json.loads(body.decode())


@lru_cache(maxsize=1)
def _task_index(pilot_dir: str):
    from .task import load_tasks
    return {t.id: t for t in load_tasks(pilot_dir)}


class SandboxHang(BaseException):
    """A candidate call exceeded its per-call budget in the sandbox. A
    BaseException so it propagates PAST evaluate_callable (which catches only
    Exception/CandidateTimeout/SystemExit) up to main(), which classifies the
    whole task TIMEOUT_KILLED — preserving the pre-fix hang contract."""


class _SandboxError(Exception):
    """The candidate RAISED in the sandbox (-> cand_raised / latent crash)."""


# A candidate that returned an out-of-domain value (Decimal, bytes, huge int, ...)
# is a WRONG VALUE, not a crash: the comparator must see an object that fails
# equality, so the outcome matches the in-process path (mismatch, audit
# C-VALUE-CRASH-RELABEL). canon() reduces this to a unique ("repr", ...) form
# that never equals a real reference output.
class _UnencodableValue:
    def __init__(self, why: str):
        self.why = why
    def __repr__(self):
        return f"<unencodable-candidate-output: {self.why}>"


class RemoteCandidate:
    """Callable proxy: each call runs in the untrusted sandbox child and returns
    its (safe-decoded) result. Owns its own per-call timeout via select() (the
    in-process SIGALRM is disabled for the remote path). Raises _SandboxError if
    the candidate raised, returns a mismatch sentinel if its output was
    unencodable, or raises SandboxHang if it exceeded the budget / the sandbox
    stopped responding (an unrecoverable stuck state)."""

    def __init__(self, req_fd: int, resp_fd: int, timeout: float = CANDIDATE_TIMEOUT_S):
        self._req, self._resp, self._timeout = req_fd, resp_fd, timeout

    def __call__(self, *args):
        from .safecodec import decode, encode
        try:
            write_msg(self._req, {"cmd": "call", "args": [encode(a) for a in args]})
        except OSError:
            raise SandboxHang("sandbox request pipe closed")
        ready, _, _ = select.select([self._resp], [], [], self._timeout)
        if not ready:
            raise SandboxHang(f"candidate exceeded {self._timeout}s")
        resp = read_msg(self._resp)
        if resp is None:                      # sandbox died / EOF: unrecoverable
            raise SandboxHang("sandbox closed during candidate call")
        if resp.get("ok"):
            return decode(resp["value"])
        if resp.get("kind") == "unencodable":  # wrong VALUE, not a crash
            return _UnencodableValue(resp.get("error", "unencodable"))
        raise _SandboxError(resp.get("error", "candidate error"))


def _spawn_sandbox(source: str, entry_point: str):
    """Start the untrusted candidate in a CLEAN interpreter; return (proc, req_wfd, resp_rfd).

    The candidate runs `python -E -s <bundle>/sandbox_main.py` (audit
    A3-GC-ANSWERKEY): -E/-s ignore PYTHON* env + user-site, and only the bundle
    dir (stdlib-only sandbox files) is on sys.path — the repo is not, so NO
    oracle/task module and hence no reference / answer key is present in that
    interpreter's memory or importable. The candidate cannot reach the verdict
    channel (it lives in this worker process) and cannot recover the reference.
    """
    # Reuse the parent-built bundle (passed via env) so it is not rebuilt per
    # candidate; only rebuild if absent (the Docker in-container worker).
    from .isolate import REPO_ROOT, bundle_dir
    bundle = os.environ.get("CG_BUNDLE") or bundle_dir()
    # Compute the repo root locally (do NOT rely on an inherited env var — the
    # Docker path does not propagate the host env into the container; audit MAJOR),
    # so the sandbox's strip+fail-closed assert always runs.
    repo_root = os.environ.get("CG_REPO_ROOT") or REPO_ROOT
    req_r, req_w = os.pipe()          # worker -> sandbox
    resp_r, resp_w = os.pipe()        # sandbox -> worker
    src_r, src_w = os.pipe()          # worker -> sandbox (source, one-shot)
    # Minimal env: NO inherited PYTHONPATH (would re-add the repo), only what the
    # sandbox needs. CG_REPO_ROOT lets the sandbox strip+assert away every
    # repo-derived sys.path entry before running the candidate.
    env = {"TZ": "UTC", "PYTHONHASHSEED": "0", "PATH": os.environ.get("PATH", ""),
           "CG_REPO_ROOT": repo_root,
           "CG_REQ_FD": str(req_r), "CG_RESP_FD": str(resp_w),
           "CG_SRC_FD": str(src_r), "CG_ENTRY": entry_point}
    # Launch with the venv's BASE interpreter (outside the repo) rather than the
    # in-repo venv python, so sys.prefix/sys.executable never reveal the repo root
    # (audit: the 5th answer-key carrier). The bundle's deps/ supplies the
    # venv-pinned third-party libs, so base-vs-venv doesn't change scoring.
    interp = getattr(sys, "_base_executable", None) or sys.executable
    # -S (not just -s): skip site.py ENTIRELY, so base-interpreter editable-install
    # MetaPathFinders (a .pth that would make a `pip install -e .`'d sibling — or
    # this repo — importable) are never loaded, and base site-packages is not
    # auto-added (audit meta_path carrier). -E ignores PYTHON* env. The candidate
    # gets stdlib + the bundle + the bundle's pinned deps/ (added by _seal).
    devnull = open(os.devnull, "wb")
    proc = subprocess.Popen(
        [interp, "-E", "-S", os.path.join(bundle, "sandbox_main.py")],
        stdin=subprocess.DEVNULL, stdout=devnull, stderr=devnull, cwd=bundle,
        env=env, close_fds=True, pass_fds=(req_r, resp_w, src_r))
    os.close(req_r); os.close(resp_w); os.close(src_r)
    # Length-frame the source (audit B-2: a >pipe-buffer source must not truncate).
    import struct
    body = source.encode()
    os.write(src_w, struct.pack(">I", len(body)) + body)
    os.close(src_w)
    return proc, req_w, resp_r


def main() -> int:
    os.environ["TZ"] = "UTC"
    if hasattr(time, "tzset"):
        time.tzset()
    sys.path.insert(0, ".")

    req = json.loads(sys.stdin.read())
    sentinel = req.get("sentinel")
    task = _task_index(req.get("pilot_dir", "tasks/pilot"))[req["task_id"]]

    proc, req_w, resp_r = _spawn_sandbox(req["source"], task.entry_point)
    try:
        # Wait for the sandbox's load status. Give it slightly more than the
        # sandbox's own import-time SIGALRM cap so an import-time hang is reported
        # as a clean load failure rather than racing this select.
        ready, _, _ = select.select([resp_r], [], [], CANDIDATE_TIMEOUT_S + 2.0)
        load = read_msg(resp_r) if ready else None
        if not ready:
            r = EvalResult(task.id, task.family, TIMEOUT_KILLED, False, False,
                           error=f"candidate did not load within {CANDIDATE_TIMEOUT_S}s")
        elif not load or not load.get("loaded"):
            r = EvalResult(task.id, task.family, LOAD_ERROR, False, False,
                           error=(load or {}).get("error", "sandbox failed to load candidate"))
        else:
            # Same classification logic as in-process, but fn is the remote proxy:
            # the candidate runs only in the sandbox; ref/compare/classify are here.
            # time_limit_s=0 disables the SIGALRM cap (RemoteCandidate owns timing).
            r = evaluate_callable(task, RemoteCandidate(req_w, resp_r), time_limit_s=0)
    except SandboxHang as e:                  # candidate hung -> whole task killed
        r = EvalResult(task.id, task.family, TIMEOUT_KILLED, False, False, error=str(e))
    finally:
        # The sandbox shares THIS worker's process group (so the parent's
        # timeout killpg reaches it too); we must NOT killpg here or we would
        # SIGKILL ourselves before writing the verdict. Kill just the sandbox
        # process. A hung sandbox is left for the parent's group-SIGKILL. Note
        # (audit A2 residual): a candidate that deliberately setsid+forks can
        # still orphan a child on the bare path; the campaign runs candidates
        # under the Docker path (--pids-limit, --rm) for guaranteed teardown.
        try:
            write_msg(req_w, {"cmd": "stop"})
        except OSError:
            pass
        try:
            proc.kill()
            proc.wait(timeout=2)
        except Exception:
            pass
        for fd in (req_w, resp_r):
            try:
                os.close(fd)
            except OSError:
                pass

    body = json.dumps({
        "task_id": r.task_id, "family": r.family, "outcome": r.outcome,
        "happy_pass": r.happy_pass, "oracle_pass": r.oracle_pass,
        "n_oracle_mismatch": r.n_oracle_mismatch, "n_oracle_raised": r.n_oracle_raised,
        "silent_wrong_value": r.silent_wrong_value,
        "diverging": r.diverging_inputs[:5], "error": r.error,
    })
    line = f"{sentinel}{body}{sentinel}\n" if sentinel else f"{body}\n"
    os.write(1, line.encode())
    os._exit(0)


if __name__ == "__main__":
    sys.exit(main())
