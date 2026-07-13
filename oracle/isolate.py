"""Process-isolated candidate evaluation (M2 + M3 pre-flight hardening).

Runs each candidate in a separate OS process (optionally inside a Docker
container) with a HARD timeout enforced by SIGKILL from the parent — which kills
ANY runaway candidate, including a bare-`except:` infinite loop that swallows the
in-process SIGALRM timeout. This is the campaign-safe execution path (M3);
untrusted model code never runs in the harness process.

Verdict integrity — TRUSTED WORKER + CLEAN-INTERPRETER SANDBOX (audit A1 + A3):
the candidate runs in a separate `python -E -s <bundle>/sandbox_main.py` process
whose sys.path is ONLY the stdlib-only sandbox bundle (see bundle_dir) — the repo
is not importable, so no `oracle.*`/`tasks.*` module, and hence no verdict
sentinel and no reference/`load_tasks`, is present in that interpreter. A TRUSTED
evaluator (oracle/isolate_worker.py) that NEVER executes candidate code holds the
sentinel and the answer key, computes the reference, compares, classifies, and
frames the verdict. Candidate return values cross the boundary through a safe
JSON codec (oracle/safecodec.py), never pickle. This closes both the frame-walk
forge (A1: the sentinel lives in another process) AND the gc-reachability forge
(A3: the reference is not in the candidate's process to be walked to).

Timeout / blast radius (audit LEN3-3 + A2): the worker runs in its own session;
on timeout the parent SIGKILLs the whole process GROUP (worker + sandbox +
same-group candidate forks). The sandbox shares the worker's group so the parent
kill reaches it. RESIDUAL (audit A2, honest): on the bare-subprocess path a
candidate that deliberately `os.setsid()`s into a NEW session can orphan a child
past the group kill — it cannot forge a verdict, only leak a process. The Docker
path (`docker kill` + `--rm` + `--pids-limit`) has no such residual and is the
recommended containment for the M3 campaign. `close_fds` keeps any orphan from
inheriting the worker->parent pipe, so orphans never stall the parent's reap.

  run_isolated(task_id, source)                 -> subprocess (fast, local)
  run_isolated(task_id, source, lang="js")      -> Node subprocess running
      oracle_js/isolate_worker.mjs (JS candidates; audit TRC-2) with the SAME
      sentinel/env/process-group machinery. The Docker path stays Python-only
      for now (the pinned image ships no Node); lang="js" + image raises.
  run_isolated(task_id, source, image="cg:...") -> Docker (full sandbox: no
      network, memory/cpu/pids caps; the container is hard-killed on timeout)
"""
from __future__ import annotations

import json
import atexit
import functools
import os
import secrets
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from typing import Optional

DEFAULT_TIMEOUT = 20.0  # > the in-process 8s SIGALRM cap; this is the hard backstop


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@functools.lru_cache(maxsize=1)
def bundle_dir() -> str:
    """A throwaway directory the untrusted candidate runs from, holding NOTHING
    that reveals the repo (audit A3 / A-REF-RECOVERY-VIA-SYSPATH). It contains:
      * the stdlib-only sandbox files (sandbox_main.py + copies of safecodec.py,
        candidate_loader.py) as TOP-LEVEL modules (no `oracle` package), and
      * `deps/` — a copy of the venv's third-party packages (tzdata, pytz,
        dateutil, ...), so the candidate can import the datetime libraries it
        legitimately uses WITHOUT the venv `site-packages` path (which, when the
        venv lives inside the repo, is an in-memory string whose prefix reveals
        the repo root — the fourth relocation of the answer-key-recovery forge).
    `sandbox_main` strips every repo-derived sys.path entry and asserts none
    remains, so no oracle/task module and no repo path is reachable in that
    interpreter. Built once per HOST process (lru_cache in the long-lived parent,
    not the per-candidate worker) and removed atexit — fixing the temp-dir leak."""
    import sysconfig
    here = os.path.dirname(os.path.abspath(__file__))
    d = tempfile.mkdtemp(prefix="cg_sandbox_")
    for name in ("sandbox_main.py", "safecodec.py", "candidate_loader.py"):
        shutil.copyfile(os.path.join(here, name), os.path.join(d, name))
    purelib = sysconfig.get_paths().get("purelib")
    deps = os.path.join(d, "deps")
    if purelib and os.path.isdir(purelib):
        # Copy pip packages but never the repo's own source (oracle/tasks live in
        # the tree, not site-packages, but exclude defensively) or bulky caches.
        shutil.copytree(purelib, deps, symlinks=True, ignore=shutil.ignore_patterns(
            "__pycache__", "oracle", "oracle-*", "tasks", "*.dist-info"))
    else:
        os.makedirs(deps, exist_ok=True)
    atexit.register(shutil.rmtree, d, ignore_errors=True)
    return d

# The full row schema every run_isolated return is normalized to, so downstream
# consumers (generation/run_pilot.py::aggregate) never KeyError on a parent-side
# residual outcome like TIMEOUT_KILLED / WORKER_ERROR / PARSE_ERROR (audit
# C-AGG-KEYERROR). `family` is filled by the caller that knows the task.
_ROW_DEFAULTS = {
    "family": None, "happy_pass": False, "oracle_pass": False,
    "n_oracle_mismatch": 0, "n_oracle_raised": 0, "silent_wrong_value": False,
    "diverging": [], "error": "",
}


def _normalize(task_id: str, res: dict) -> dict:
    out = {"task_id": task_id, **_ROW_DEFAULTS}
    out.update(res or {})
    out["task_id"] = task_id
    return out


def _parse(stdout: str, sentinel: str) -> dict:
    """Extract the sentinel-framed verdict. Fail-safe: anything but exactly one
    well-formed frame is an error outcome, never a trusted classification."""
    parts = (stdout or "").split(sentinel)
    if len(parts) == 1:
        return {"outcome": "WORKER_EMPTY", "error": "no framed result in worker output"}
    if len(parts) != 3:
        return {"outcome": "PARSE_ERROR",
                "error": f"sentinel appears {len(parts) - 1} times (expected 2); "
                         f"refusing to trust output"}
    return json.loads(parts[1])


def preflight() -> None:
    """Loud, once-per-campaign check that the candidate sandbox is sound. Raises
    RuntimeError with a clear message if (a) the sandbox interpreter cannot be
    resolved OUTSIDE the repo, or (b) a spawned sandbox can import the answer-key
    package or force a CORRECT verdict for a delegating candidate. Call this at
    campaign startup so a misconfiguration fails LOUDLY here rather than silently
    mis-scoring every candidate as LOAD_ERROR (audit)."""
    interp = getattr(sys, "_base_executable", None) or sys.executable
    if not interp or (os.path.realpath(interp).rstrip(os.sep) + os.sep).startswith(
            os.path.realpath(REPO_ROOT).rstrip(os.sep) + os.sep):
        raise RuntimeError(
            f"CG preflight: sandbox interpreter {interp!r} is inside the repo "
            f"({REPO_ROOT}); create the venv from a base Python OUTSIDE the repo.")
    # A delegating candidate (imports the reference and echoes it) MUST score
    # non-CORRECT, and a probe MUST NOT be able to import the answer key.
    forge = ("def _p(*a,**k):\n"
             " try:\n"
             "  from oracle.task import load_tasks\n"
             "  for t in load_tasks('tasks/pilot'):\n"
             "   if t.entry_point=='stored_before': return t.reference(*a)\n"
             " except Exception: pass\n"
             " return None\n"
             "stored_before=_p\n")
    out = run_isolated("B1_stored_naive_utc_before", forge)["outcome"]
    if out == "CORRECT":
        raise RuntimeError("CG preflight: a delegating candidate scored CORRECT — the "
                           "sandbox can reach the answer key; refusing to run the campaign.")


def run_isolated(task_id: str, source: str, *, timeout: float = DEFAULT_TIMEOUT,
                 image: Optional[str] = None, container_name: Optional[str] = None,
                 lang: str = "python") -> dict:
    """Evaluate one candidate in an isolated process; SIGKILL on timeout.

    lang="python" (default) runs the Python worker; lang="js" runs the Node
    worker (oracle_js/isolate_worker.mjs) under identical result-channel and
    timeout machinery: same per-invocation sentinel frame, same TZ=UTC env,
    same own-session Popen so the whole process group is SIGKILLed on timeout.
    """
    if lang not in ("python", "js"):
        raise ValueError(f"lang must be 'python' or 'js', got {lang!r}")
    sentinel = secrets.token_hex(16)          # unknown to the candidate
    payload = json.dumps({"task_id": task_id, "source": source, "sentinel": sentinel})
    if image:
        if lang != "python":
            # The pinned campaign image ships Python + tzdata only; a Node image
            # (pinned to the same ICU tzdata 2025b) is a separate M3 work item.
            raise ValueError("Docker isolation is Python-only for now; "
                             "run lang='js' as a local Node subprocess")
        name = container_name or f"cg_{task_id[:20]}_{int(time.time()*1000)%100000}"
        cmd = ["docker", "run", "--rm", "-i", "--name", name, "-e", "TZ=UTC",
               "--network=none", "--memory=256m", "--cpus=1", "--pids-limit=256",
               image, "python", "-m", "oracle.isolate_worker"]
    elif lang == "js":
        name = None
        worker = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                              "oracle_js", "isolate_worker.mjs")
        cmd = ["node", worker]
    else:
        name = None
        cmd = [sys.executable, "-m", "oracle.isolate_worker"]

    env = {**os.environ, "TZ": "UTC", "PYTHONHASHSEED": "0", "CG_REPO_ROOT": REPO_ROOT}
    # Build the candidate-sandbox bundle ONCE in this long-lived parent and pass
    # it to the (per-candidate) worker, so it is not rebuilt+leaked per candidate
    # (audit temp-dir leak). Docker builds its own bundle in-container (a host
    # path is invalid there; the container's --rm handles teardown).
    if not image:
        env["CG_BUNDLE"] = bundle_dir()
    # Own session => the whole process group (worker + any candidate-spawned
    # grandchildren) can be SIGKILLed as a unit on timeout.
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE, text=True, env=env,
                         start_new_session=True)
    try:
        out, err = p.communicate(payload, timeout=timeout)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(p.pid, signal.SIGKILL)   # group kill: worker + grandchildren
        except (ProcessLookupError, PermissionError):
            p.kill()
        if name:  # the docker client died, but the container may still run
            subprocess.run(["docker", "kill", name], capture_output=True)
        try:
            p.communicate(timeout=5)           # reap; drain pipes
        except Exception:
            pass
        return _normalize(task_id, {"outcome": "TIMEOUT_KILLED",
                "error": f"hard SIGKILL (process group) after {timeout}s"})
    if p.returncode != 0:
        return _normalize(task_id, {"outcome": "WORKER_ERROR",
                "error": (err or "")[-500:]})
    try:
        return _normalize(task_id, _parse(out, sentinel))
    except Exception as e:
        return _normalize(task_id, {"outcome": "PARSE_ERROR",
                "error": f"{e} :: {(out or '')[-300:]}"})
